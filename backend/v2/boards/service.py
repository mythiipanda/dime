import math
import unicodedata
from collections import defaultdict
from typing import Annotated, Any, Literal

import duckdb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared import store
from v2.boards.metrics import METRICS, Metric


Season = Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
PlayerId = Annotated[int, Field(strict=True, gt=0)]
MetricId = Annotated[str, Field(min_length=1, max_length=80)]
router = APIRouter(prefix="/boards", tags=["boards"])
SALARY_SEASON = "2026-27"


class FillBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season: Season = "2025-26"
    player_ids: list[PlayerId] = Field(max_length=50)
    metric_ids: list[MetricId] = Field(max_length=30)


class SeedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    season: Season = "2025-26"
    metric_id: MetricId
    n: int = Field(default=10, strict=True, ge=1, le=25)
    min_gp: int | None = Field(default=None, strict=True, ge=0)
    min_mpg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    position: Literal["G", "F", "C"] | None = Field(
        default=None, description="At least one warehouse boxscore start at this position in the selected season.")


def _name(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def _read(con, table: str, season: str) -> tuple[list[dict], str, list]:
    sql = f'SELECT * FROM "{table}" WHERE "_season" = ?'
    cursor = con.execute(sql, [season])
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()], sql, [season]


def _citation(metric: Metric | None, season: str, sql: str | None,
              params: list, row: dict | None, player_id: int) -> dict:
    row = row or {}
    salary = metric is not None and metric.unit == "usd"
    return {
        "table": metric.table if metric else None,
        "column": metric.column if metric else None,
        "season": SALARY_SEASON if salary else season,
        "sql": sql, "params": params,
        "source": row.get("_source"), "fetched_at": row.get("_fetched_at"),
        "row_key": ({"player": row.get("player"), "team": row.get("team"),
                     "_season": SALARY_SEASON, "_entity": row.get("_entity"),
                     "resolved_player_id": player_id} if salary else
                    {"PLAYER_ID": player_id, "_season": season, "_entity": row.get("_entity")}),
        **({"salary_vintage": {"season": SALARY_SEASON, "fetched_at": row.get("_fetched_at")}} if salary else {}),
    }


def _value(metric: Metric, raw: Any) -> float | int | None:
    if not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return None
    # NBA and BRef percentage fields are fractions; TM_TOV_PCT is per 100 possessions.
    return raw * 100 if metric.unit == "pct" and metric.column != "TM_TOV_PCT" else raw


def _fill(con, season: str, player_ids: list[int] | None, metric_ids: list[str],
          base_read: tuple | None = None) -> dict:
    reads = {"silver_player_season": base_read or _read(con, "silver_player_season", season)}
    base = reads["silver_player_season"][0]
    by_player: dict[int, list[dict]] = defaultdict(list)
    names: dict[str, set[int]] = defaultdict(set)
    for row in base:
        pid = row["PLAYER_ID"]
        if pid is None:
            continue
        by_player[pid].append(row)
        if row.get("PLAYER"):
            names[_name(row["PLAYER"])].add(pid)
    ids = list(dict.fromkeys(player_ids)) if player_ids is not None else sorted(by_player)
    for metric_id in dict.fromkeys(metric_ids):
        metric = METRICS.get(metric_id)
        if metric and metric.table not in reads:
            reads[metric.table] = _read(con, metric.table, SALARY_SEASON if metric.unit == "usd" else season)
    indexes = {}
    for table, (rows, _, _) in reads.items():
        index: dict[Any, list[dict]] = defaultdict(list)
        for row in rows:
            key = _name(row["player"]) if table == "silver_cap_players" else row["PLAYER_ID"]
            index[key].append(row)
        indexes[table] = index
    players, cells = {}, {}
    for pid in ids:
        identity_rows = by_player.get(pid, [])
        identity = identity_rows[0] if len(identity_rows) == 1 else None
        players[str(pid)] = {"name": identity.get("PLAYER") if identity else None,
                             "team": identity.get("TEAM") if identity else None}
        cells[str(pid)] = {}
        for metric_id in dict.fromkeys(metric_ids):
            metric = METRICS.get(metric_id)
            row, reason, sql, params = None, None, None, []
            if metric is None:
                reason = "unknown_metric"
            else:
                _, sql, params = reads[metric.table]
                if not identity_rows:
                    reason = "unknown_player"
                elif identity is None:
                    reason = "ambiguous_player_rows"
                else:
                    key = _name(identity["PLAYER"]) if metric.unit == "usd" else pid
                    matches = indexes[metric.table].get(key, [])
                    if metric.unit == "usd" and not key:
                        reason = "unmatched_salary_name"
                    elif metric.unit == "usd" and len(names[key]) != 1:
                        reason = "ambiguous_salary_name"
                    elif len(matches) > 1:
                        reason = "ambiguous_salary_rows" if metric.unit == "usd" else "ambiguous_metric_rows"
                    elif not matches:
                        reason = "unmatched_salary_name" if metric.unit == "usd" else "no_metric_row"
                    else:
                        row = matches[0]
            value = _value(metric, row.get(metric.column)) if row is not None else None
            if row is not None and value is None:
                reason = "missing_or_nonfinite_value"
            citation = _citation(metric, season, sql, params, row, pid)
            if metric and metric.unit == "usd":
                citation["identity_resolution"] = {
                    "method": "NFC_casefold_whitespace_full_name_exact",
                    "name": identity.get("PLAYER") if identity else None,
                    "player_id": pid,
                    "table": "silver_player_season",
                    "sql": reads["silver_player_season"][1],
                    "params": reads["silver_player_season"][2],
                }
            cells[str(pid)][metric_id] = {"value": value, "citation": citation, **({"reason": reason} if reason else {})}
    return {"ok": True, "cells": cells, "players": players}


@router.get("/metrics")
def metrics():
    return {"ok": True, "metrics": [metric.public() for metric in METRICS.values()]}


@router.post("/fill")
def fill(body: FillBody):
    if not body.player_ids:
        return {"ok": True, "cells": {}, "players": {}}
    try:
        with store.connect(read_only=True) as con:
            return _fill(con, body.season, body.player_ids, body.metric_ids)
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Boards warehouse unavailable") from exc


@router.post("/seed")
def seed(body: SeedBody):
    metric = METRICS.get(body.metric_id)
    if metric is None:
        raise HTTPException(status_code=422, detail="unknown_metric")
    try:
        with store.connect(read_only=True) as con:
            base_read = _read(con, "silver_player_season", body.season)
            eligible = [row["PLAYER_ID"] for row in base_read[0]
                        if (body.min_gp is None or (row.get("GP") is not None and row["GP"] >= body.min_gp))
                        and (body.min_mpg is None or (row.get("MPG") is not None and row["MPG"] >= body.min_mpg))]
            filters = {"min_gp": body.min_gp, "min_mpg": body.min_mpg,
                       "sql": base_read[1], "params": base_read[2]}
            if body.position is not None:
                sql = ('SELECT DISTINCT "PLAYER_ID" FROM "silver_boxscores" '
                       'WHERE "_season" = ? AND upper(trim("position")) = ?')
                params = [body.season, body.position]
                positional_ids = {row[0] for row in con.execute(sql, params).fetchall()}
                eligible = [pid for pid in eligible if pid in positional_ids]
                filters["position"] = {"value": body.position, "table": "silver_boxscores", "sql": sql, "params": params}
            result = _fill(con, body.season, eligible, [body.metric_id], base_read)
            ranked = [(int(pid), cell[body.metric_id]["value"]) for pid, cell in result["cells"].items()
                      if cell[body.metric_id]["value"] is not None]
            ranked.sort(key=lambda item: (-item[1] if metric.higher_is_better else item[1], item[0]))
            ids = [pid for pid, _ in ranked[:body.n]]
            return {"ok": True, "player_ids": ids, "filters": filters,
                    "cells": {str(pid): result["cells"][str(pid)] for pid in ids},
                    "players": {str(pid): result["players"][str(pid)] for pid in ids}}
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Boards warehouse unavailable") from exc
