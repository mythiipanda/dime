import math
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Annotated, Any

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


@dataclass
class SeasonData:
    reads: dict
    indexes: dict
    identities: dict
    name_sources: dict


def _load(con, season: str, metric_ids: list[str]) -> SeasonData:
    available = {row[0] for row in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", ["main"]).fetchall()}
    reads = {table: _read(con, table, season)
             for table in ("silver_player_season", "silver_advanced") if table in available}
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
    identities = {}
    name_sources: dict[str, list[dict]] = defaultdict(list)
    for table in ("silver_player_season", "silver_advanced"):
        name_column, team_column = (("PLAYER", "TEAM") if table == "silver_player_season"
                                    else ("PLAYER_NAME", "TEAM_ABBREVIATION"))
        for pid, rows in indexes.get(table, {}).items():
            if pid is None:
                continue
            identity = identities.setdefault(pid, {"name": None, "team": None, "spellings": set()})
            for row in rows:
                if row.get(name_column):
                    spelling = _name(row[name_column])
                    identity["spellings"].add(spelling)
                    name_sources[spelling].append({
                        "player_id": pid, "name": row[name_column], "table": table,
                        "sql": reads[table][1], "params": reads[table][2],
                        "source": row.get("_source"), "fetched_at": row.get("_fetched_at"),
                        "row_key": {"PLAYER_ID": pid, "_season": season, "_entity": row.get("_entity")},
                    })
            if len(rows) == 1:
                identity["name"] = identity["name"] or rows[0].get(name_column)
                identity["team"] = identity["team"] or rows[0].get(team_column)
    return SeasonData(reads, indexes, identities, name_sources)


def _salary(data: SeasonData, pid: int) -> tuple[dict | None, str | None, dict]:
    spellings = sorted(data.identities[pid]["spellings"])
    matches = [row for name in spellings for row in data.indexes["silver_cap_players"].get(name, [])]
    matched_names = sorted({_name(row["player"]) for row in matches})
    sources = [source for name in matched_names or spellings for source in data.name_sources[name]]
    collisions = [source for name in matched_names
                  if len({ref["player_id"] for ref in data.name_sources[name]}) > 1
                  for source in data.name_sources[name]]
    own_source = next((ref for ref in sources if ref["player_id"] == pid), None)
    resolution = {
        "method": "NFC_casefold_whitespace_full_name_exact",
        "player_id": pid, "spellings": spellings, "matched_names": matched_names,
        "sources": sources, "collisions": collisions,
        "table": own_source["table"] if own_source else None,
        "sql": own_source["sql"] if own_source else None,
        "params": own_source["params"] if own_source else [],
    }
    if collisions:
        return None, "ambiguous_salary_name", resolution
    if len(matches) > 1:
        return None, "ambiguous_salary_rows", resolution
    if not matches:
        return None, "unmatched_salary_name", resolution
    return matches[0], None, resolution


def _fill(con, season: str, player_ids: list[int] | None, metric_ids: list[str],
          data: SeasonData | None = None) -> dict:
    data = data or _load(con, season, metric_ids)
    ids = list(dict.fromkeys(player_ids)) if player_ids is not None else sorted(data.identities)
    players, cells = {}, {}
    for pid in ids:
        identity = data.identities.get(pid)
        players[str(pid)] = {"name": identity["name"] if identity else None,
                             "team": identity["team"] if identity else None}
        cells[str(pid)] = {}
        for metric_id in dict.fromkeys(metric_ids):
            metric = METRICS.get(metric_id)
            row, reason, sql, params = None, None, None, []
            resolution = None
            if metric is None:
                reason = "unknown_metric"
            else:
                _, sql, params = data.reads[metric.table]
                if identity is None:
                    reason = "unknown_player"
                elif metric.unit == "usd":
                    row, reason, resolution = _salary(data, pid)
                else:
                    matches = data.indexes[metric.table].get(pid, [])
                    if len(matches) > 1:
                        reason = "ambiguous_metric_rows"
                    elif not matches:
                        reason = "no_metric_row"
                    else:
                        row = matches[0]
            value = _value(metric, row.get(metric.column)) if row is not None else None
            if row is not None and value is None:
                reason = "missing_or_nonfinite_value"
            citation = _citation(metric, season, sql, params, row, pid)
            if resolution is not None:
                citation["identity_resolution"] = resolution
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
            data = _load(con, body.season, [body.metric_id])
            source_read = data.reads[metric.table]
            filters = {"min_gp": body.min_gp, "min_mpg": body.min_mpg,
                       "table": metric.table, "sql": source_read[1], "params": source_read[2]}
            if metric.unit == "usd":
                eligible = {ref["player_id"] for row in source_read[0]
                            for ref in data.name_sources.get(_name(row["player"]), [])}
                qualification_tables = ("silver_player_season", "silver_advanced")
            else:
                eligible = {row["PLAYER_ID"] for row in source_read[0] if row["PLAYER_ID"] is not None}
                qualification_tables = (metric.table,)
            if body.min_gp is not None or body.min_mpg is not None:
                qualified = set()
                for pid in eligible:
                    for table in qualification_tables:
                        rows = data.indexes.get(table, {}).get(pid, [])
                        if not rows:
                            continue
                        if len(rows) == 1:
                            row = rows[0]
                            minutes = row.get("MIN" if table == "silver_advanced" else "MPG")
                            gp = row.get("GP")
                            if ((body.min_gp is None or (gp is not None and gp >= body.min_gp))
                                    and (body.min_mpg is None or (minutes is not None and minutes >= body.min_mpg))):
                                qualified.add(pid)
                        break
                eligible = qualified
                filters["qualification"] = [{"table": table, "sql": data.reads[table][1],
                                             "params": data.reads[table][2]} for table in qualification_tables if table in data.reads]
            result = _fill(con, body.season, sorted(eligible), [body.metric_id], data)
            ranked = [(int(pid), cell[body.metric_id]["value"]) for pid, cell in result["cells"].items()
                      if cell[body.metric_id]["value"] is not None]
            ranked.sort(key=lambda item: (-item[1] if metric.higher_is_better else item[1], item[0]))
            ids = [pid for pid, _ in ranked[:body.n]]
            return {"ok": True, "player_ids": ids, "filters": filters,
                    "cells": {str(pid): result["cells"][str(pid)] for pid in ids},
                    "players": {str(pid): result["players"][str(pid)] for pid in ids}}
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="Boards warehouse unavailable") from exc
