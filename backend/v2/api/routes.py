from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import re
import subprocess
import marshal
import time
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from v2.projects.service import ProjectStore
from v2.conversations import ConversationStore
from v2.api.sse import encode_raw, with_heartbeat
from shared.config import runtime_v2_mode
from shared.rate_limit import check_sql_rerun, client_ip

router = APIRouter()
_BACKEND = Path(__file__).resolve().parents[2]
_PROJECTS = ProjectStore(
    os.environ.get("DIME_PROJECT_STORE", str(_BACKEND / "data" / "v2-projects.sqlite3"))
)
_CONVERSATIONS = ConversationStore(os.environ.get(
    "DIME_CONVERSATION_STORE", str(_BACKEND / "data" / "v2-conversations.sqlite3")))

def _imported_module_code_sha256() -> str:
    code = __loader__.get_code(__name__) if __loader__ is not None else None
    if code is None:
        raise RuntimeError("routes module has no loader code identity")
    return hashlib.sha256(marshal.dumps(code)).hexdigest()

_LOADED_MODULE_CODE_SHA256 = _imported_module_code_sha256()

def _projects_enabled() -> bool:
    return runtime_v2_mode() in {"on", "action_loop"}

def _require_projects() -> None:
    if not _projects_enabled():
        raise HTTPException(status_code=404, detail="not found")

def _revision() -> str:
    configured = os.environ.get("DIME_REVISION")
    if configured:
        return configured
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_BACKEND.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"

def _executable_sha256() -> str:
    digest = hashlib.sha256()
    for root in (_BACKEND / "app", _BACKEND / "v2", _BACKEND / "analyst"):
        for path in sorted(root.rglob("*")):
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise ValueError("executable source tree cannot contain symlinks")
            if path.is_file() and path.suffix in {".py", ".md", ".mjs", ".json"}:
                digest.update(path.relative_to(_BACKEND).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()

@lru_cache(maxsize=1)
def runtime_warehouse_identity() -> dict[str, str]:
    from shared import store
    identity = store.warehouse_identity()
    return {"warehouse_id": identity["warehouse_id"],
            "sha256": identity["warehouse_sha256"],
            "sha256_derivation": store.WAREHOUSE_SHA256_DERIVATION}

@dataclass(frozen=True)
class RuntimeAssetManifest:
    revision: str
    executable_sha256: str
    module_sha256: Mapping[str, str]
    warehouse: Mapping[str, str]
    semantic_baseline: Mapping[str, str]
    prompt_sha256: Mapping[str, str]
    typed_argument_assets: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "executable_sha256": self.executable_sha256,
            "module_sha256": dict(self.module_sha256),
            "warehouse": dict(self.warehouse),
            "semantic_baseline": dict(self.semantic_baseline),
            "prompt_sha256": dict(self.prompt_sha256),
            "typed_argument_assets": dict(self.typed_argument_assets),
        }

def _loaded_behavior_sha256(module: ModuleType, config: Mapping[str, object]) -> str:
    code_hash = getattr(module, "_LOADED_MODULE_CODE_SHA256", None)
    if not isinstance(code_hash, str) or len(code_hash) != 64:
        raise RuntimeError("module lacks import-time code identity")
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(code_hash.encode() + b"\0" + encoded).hexdigest()

def _typed_argument_asset_hashes() -> dict[str, str]:
    paths = {
        "provider_schema_manifest": _BACKEND / "v2/schema_snapshots/manifest.json",
        "behavior_losses": _BACKEND / "v2/schema_snapshots/behavior_losses.json",
        "capability_manifest": _BACKEND / "v2/capability_snapshots/manifest.json",
        "capability_source": _BACKEND / "v2/capability_snapshots/catalog.source.json",
        "capability_compiled": _BACKEND / "v2/capability_snapshots/catalog.compiled.json",
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()}

@lru_cache(maxsize=1)
def runtime_asset_manifest() -> RuntimeAssetManifest:
    from analyst import product_session
    analyst = _BACKEND / "analyst"
    modules = {"routes": _loaded_behavior_sha256(__import__(__name__, fromlist=["x"]), {}),
               "product_session": product_session._LOADED_MODULE_CODE_SHA256}
    for name in ("worker.mjs", "runtime.mjs", "python-tools.mjs", "package-lock.json", "configuration.py", "python_tools.py", "sources.py"):
        modules[name] = hashlib.sha256((analyst / name).read_bytes()).hexdigest()
    return RuntimeAssetManifest(
        revision=_revision(), executable_sha256=_executable_sha256(),
        module_sha256=MappingProxyType(modules),
        warehouse=MappingProxyType(dict(runtime_warehouse_identity())),
        semantic_baseline=__import__(
            "v2.semantic_baseline", fromlist=["SEMANTIC_BASELINE"]
        ).SEMANTIC_BASELINE,
        prompt_sha256=MappingProxyType({"pi_runtime": modules["runtime.mjs"]}),
        typed_argument_assets=MappingProxyType(_typed_argument_asset_hashes()),
    )

def _require_matching_warehouse_derivation(
        expected: Mapping[str, object], observed_dict: Mapping[str, object]) -> None:
    from shared import store
    recorded = expected.get("warehouse")
    if not isinstance(recorded, Mapping):
        raise RuntimeError("expected asset manifest has no warehouse identity")
    observed_warehouse = observed_dict["warehouse"]
    if not isinstance(observed_warehouse, Mapping):
        raise RuntimeError("observed asset manifest has no warehouse identity")
    observed_derivation = observed_warehouse["sha256_derivation"]
    if recorded.get("sha256_derivation") == observed_derivation:
        return
    raise RuntimeError(
        "expected asset manifest records warehouse sha256 derivation "
        f"{recorded.get('sha256_derivation')!r}; this build derives "
        f"{observed_derivation!r}; re-record the manifest, a manifest "
        "written under another derivation is incompatible and its sha256 "
        f"cannot be compared against {store.WAREHOUSE_SHA256_DERIVATION}")

def preflight_runtime_assets(expected_path: str | Path | None = None) -> RuntimeAssetManifest:
    configured = expected_path or os.environ.get("DIME_EXPECTED_ASSET_MANIFEST")
    if not configured:
        raise RuntimeError("DIME_EXPECTED_ASSET_MANIFEST is required")
    manifest_path = Path(configured).resolve()
    executable_roots = ((_BACKEND / "app").resolve(), (_BACKEND / "v2").resolve())
    if any(manifest_path.is_relative_to(root) for root in executable_roots):
        raise RuntimeError("expected asset manifest must be external to executable roots")
    expected = json.loads(manifest_path.read_text())
    required = {"revision", "executable_sha256", "module_sha256",
                "warehouse", "semantic_baseline", "prompt_sha256",
                "typed_argument_assets"}
    if set(expected) != required:
        raise RuntimeError("expected asset manifest has wrong fields")
    observed = runtime_asset_manifest()
    observed_dict = observed.as_dict()
    _require_matching_warehouse_derivation(expected, observed_dict)
    if expected != observed_dict:
        import logging
        _log = logging.getLogger(__name__)

        substantive_keys = {"executable_sha256", "module_sha256", "warehouse",
                           "semantic_baseline", "prompt_sha256",
                           "typed_argument_assets"}
        substantive_drift = {
            k: {"expected": expected.get(k), "observed": observed_dict.get(k)}
            for k in substantive_keys
            if expected.get(k) != observed_dict.get(k)
        }
        if substantive_drift:
            _log.error("startup asset SUBSTANTIVE mismatch: %s", substantive_drift)
            raise RuntimeError(
                "startup asset manifest substantive mismatch: "
                f"{sorted(substantive_drift)}")

        _log.warning(
            "startup asset revision label mismatch: expected %s, observed %s",
            expected.get("revision"), observed_dict.get("revision"),
        )
    return observed

@router.get("/revision")
def revision() -> dict:

    return runtime_asset_manifest().as_dict()

def _models_catalog() -> dict:

    from shared.providers import models_catalog

    return models_catalog()

@router.get("/models")
def models() -> dict:
    return _models_catalog()

@router.get("/health")
def health() -> dict:
    catalog = _models_catalog()
    return {"ok": True, "providers": catalog["available"]}

@router.get("/healthz")
def healthz() -> Response:
    from shared import store
    try:
        con = store.connect(read_only=True)
    except Exception:
        return Response(
            content=json.dumps({"ok": False, "reason": "warehouse_unreachable"}),
            media_type="application/json", status_code=503)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "silver_team_ratings" not in tables:
            return Response(
                content=json.dumps({"ok": False, "reason": "ratings_table_missing"}),
                media_type="application/json", status_code=503)
        count = con.execute("SELECT COUNT(*) FROM silver_team_ratings").fetchone()[0]
    except Exception:
        return Response(
            content=json.dumps({"ok": False, "reason": "ratings_unreadable"}),
            media_type="application/json", status_code=503)
    finally:
        try:
            con.close()
        except Exception:
            pass
    if not count:
        return Response(
            content=json.dumps({"ok": False, "reason": "ratings_table_empty"}),
            media_type="application/json", status_code=503)
    return Response(
        content=json.dumps({"ok": True}),
        media_type="application/json", status_code=200)

_DATASETS_TABLES = {
    "standings": "silver_standings",
    "leaders": "silver_leaders_pts",
    "injuries": "silver_injuries",
    "player_gamelogs": "silver_player_gamelogs",
    "team_games": "silver_team_games",
    "scoreboard": "silver_scoreboard",
    "shots": "silver_shots",
    "lineups": "silver_lineups",
    "on_off": "silver_on_off",
    "wowy": "silver_wowy",
    "four_factors": "silver_four_factors",
    "hustle": "silver_hustle_player",
    "combine": "silver_combine",
    "ratings": "silver_team_ratings",
    "playoffs": "silver_playoffs",
    "playoff_gamelogs": "silver_playoff_gamelogs",
    "draft": "silver_hist_draft",
    "raptor": "silver_raptor_player",
    "player_seasons": "silver_hist_player_seasons",
}

_DATASETS_FRESHNESS_TTL_S = 300
_DATASETS_FRESHNESS_CACHE = {"at": 0.0, "payload": None}

def _datasets_freshness_payload() -> dict:
    from shared import store
    from shared.freshness import table_data_through

    con = store.connect()
    try:
        tables = [r[0] for r in
                  con.execute("SHOW TABLES").fetchall()]
        rows = []
        for t in sorted(tables):
            if not t.startswith("silver_"):
                continue
            cols = [r[1] for r in
                    con.execute(f"PRAGMA table_info({t})").fetchall()]
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            last = None
            if "_fetched_at" in cols:
                last = con.execute(
                    f"SELECT MAX(_fetched_at) FROM {t}").fetchone()[0]
            rows.append({"table": t, "rows": n, "last_fetch": last,
                         "data_through": table_data_through(con, t, cols)})
    finally:
        con.close()
    return {"ok": True, "rows": rows}

@router.get("/datasets/freshness")
def datasets_freshness() -> dict:
    now = time.monotonic()
    cached = _DATASETS_FRESHNESS_CACHE
    if cached["payload"] is not None and now - cached["at"] < _DATASETS_FRESHNESS_TTL_S:
        return cached["payload"]
    payload = _datasets_freshness_payload()
    cached["payload"] = payload
    cached["at"] = now
    return payload

def _pinned_rows(rows: list[dict], pin: list[str]) -> list[dict]:
    pinned = []
    for r in rows:
        keyed = {k: r[k] for k in pin if k in r}
        keyed.update({k: v for k, v in r.items() if k not in keyed})
        pinned.append(keyed)
    return pinned

def _sample_tier_rows(rows: list[dict]) -> list[dict]:
    from shared.tools._core import sample_tier

    for r in rows:
        tier, est = sample_tier(r.get("MIN"))
        r["SAMPLE_TIER"] = tier
        r["EST_POSS"] = est
        if tier == "small" and not r.get("SAMPLE"):
            r["SAMPLE"] = "small: under ~100 possessions"
    return rows

def _datasets_envelope(table: str, season: str, frame: object, cached: bool) -> dict:
    import polars as pl

    assert isinstance(frame, pl.DataFrame)
    meta = {"season": season, "rows": frame.height, "cached": cached}
    if frame.height and "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    rows = frame.to_dicts()
    if table.startswith("silver_leaders_"):
        stat_col = table.rsplit("_", 1)[-1].upper()
        if stat_col == "FG":
            stat_col = "FG_PCT"
        rows = _pinned_rows(rows, ["RANK", "PLAYER", "TEAM", stat_col, "GP", "MIN"])
    if table == "silver_standings":
        rows = _pinned_rows(rows, ["TeamCity", "TeamName", "Conference", "Record",
                                   "WINS", "LOSSES", "WinPCT", "PlayoffRank",
                                   "ClinchIndicator"])
    if table == "silver_lineups":
        rows = _sample_tier_rows(rows)
    return {"data": rows, "meta": meta}

def _datasets_fetch_live(
    name: str, season: str, player_id: int, team_id: int,
    game_id: str, game_date: str, stat: str, ids: str = "",
):
    from shared.sources import espn, nba_stats

    if name == "standings":
        return nba_stats.standings(season)
    if name == "leaders":
        from shared.tools import clamp_stat

        try:
            stat = clamp_stat(stat)
        except ValueError:
            stat = "PTS"
        return nba_stats.leaders(stat, season)
    if name == "injuries":
        return espn.injuries(season)
    if name == "player_gamelogs" and player_id:
        return nba_stats.player_gamelog(player_id, season)
    if name == "team_games" and team_id:
        return nba_stats.team_gamelog(team_id, season)
    if name == "scoreboard" and game_date:
        return nba_stats.scoreboard(game_date, season)
    if name == "shots" and player_id:
        return nba_stats.shot_chart(player_id, season, team_id)
    if name == "lineups" and team_id:
        return nba_stats.lineups(team_id, season)
    if name in ("on_off", "four_factors") and player_id and team_id:
        from shared.sources import pbpstats

        if name == "on_off":
            return pbpstats.on_off(player_id, team_id, season)
        return pbpstats.four_factors(player_id, team_id, season)
    if name == "combine":
        return nba_stats.combine(season)
    if name == "ratings":
        return nba_stats.team_ratings(season)
    if name == "playoffs":
        return nba_stats.playoff_results(season)
    if name == "wowy" and team_id and ids:
        from shared.sources import pbpstats

        parsed = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        return pbpstats.wowy(parsed, team_id, season)
    if name == "hustle":
        return nba_stats.hustle("player", season)
    return None

def _wowy_dataset(season: str, player_a: str, player_b: str, team_id: int, fmt: str):
    import polars as pl
    from shared.tools.player import get_wowy

    res = get_wowy.invoke(
        {"player_a": player_a, "player_b": player_b, "team_id": team_id, "season": season}
    )
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "wowy failed")}
    rows = res.get("rows", [])
    if fmt == "csv":
        df = pl.DataFrame(rows)
        return Response(df.write_csv(), media_type="text/csv")
    return {"ok": True, "data": rows, "verdict": res.get("verdict"), "meta": res.get("meta")}

def _clamp_leaders_stat(stat: str) -> str:
    from shared.tools import clamp_stat

    try:
        return clamp_stat(stat)
    except ValueError:
        return "PTS"

def _dataset_entity(player_id: int, team_id: int, game_id: str, game_date: str, ids: str) -> str:
    if player_id:
        return f"player:{player_id}"
    if team_id:
        return f"team:{team_id}"
    if game_id:
        return f"game:{game_id}"
    if game_date:
        return f"date:{game_date}"
    if ids:
        return f"wowy:{ids}"
    return ""

def _failed_live_response(live, entity_scoped: bool, entity: str, table: str, season: str) -> dict:
    from shared import store

    stale = None
    if entity_scoped and entity:
        stale = store.read_frame(table, "_entity = ?", [entity])
    if stale is not None and stale.height > 0:
        out = _datasets_envelope(table, season, stale, True)
        out["ok"] = True
        out["meta"]["stale"] = True
        out["meta"]["live_error"] = live.error or "empty upstream response"
        out["meta"]["live_source"] = live.meta.source
        return out
    return {"ok": False, "error": live.error,
            "source": live.meta.source,
            "detail": "live source failed and no cached rows for this entity"}

def _sort_frame_by_game_date(frame):
    import polars as pl

    for fmt_s in ("%b %d, %Y", "%Y-%m-%d"):
        try:
            frame = frame.with_columns(
                pl.col("GAME_DATE").str.strptime(
                    pl.Date, fmt_s, strict=False).alias("_d"))
            if frame["_d"].null_count() < frame.height:
                frame = frame.sort("_d", descending=True,
                                   nulls_last=True).drop("_d")
            else:
                frame = frame.drop("_d")
                continue
            break
        except Exception:
            if "_d" in frame.columns:
                frame = frame.drop("_d")
            continue
    return frame

@router.get("/datasets/{name}")
def dataset(
    name: str,
    season: str = Query("2025-26"),
    player_id: int = Query(0),
    team_id: int = Query(0),
    game_id: str = Query(""),
    game_date: str = Query(""),
    stat: str = Query("PTS"),
    ids: str = Query(""),
    player_a: str = Query(""),
    player_b: str = Query(""),
    fmt: str = Query("json"),
):
    import polars as pl

    if name == "wowy" and (player_a or ids):
        return _wowy_dataset(season, player_a or ids, player_b, team_id, fmt)

    if name not in _DATASETS_TABLES:
        return {"ok": False, "error": f"unknown dataset, pick one of {sorted(_DATASETS_TABLES)}"}
    from shared import store

    table = _DATASETS_TABLES[name]
    if name == "leaders":
        stat = _clamp_leaders_stat(stat)
        table = f"silver_leaders_{stat.lower()}"
    entity_scoped = name in ("player_gamelogs", "team_games", "shots", "scoreboard", "lineups", "on_off", "wowy", "four_factors")
    entity = _dataset_entity(player_id, team_id, game_id, game_date, ids)
    frame = store.read_frame(table, "_season = ?", [season])
    if name == "leaders" and frame.height > 0:
        from shared.tools import clamp_stat

        stat_col = clamp_stat(stat)
        if stat_col in frame.columns:
            frame = frame.sort(stat_col, descending=True, nulls_last=True)
    if entity_scoped:

        if entity:
            frame = store.read_frame(
                table, "_season = ? AND _entity = ?", [season, entity])
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _datasets_fetch_live(name, season, player_id, team_id, game_id, game_date, stat, ids)
        if live is None:
            return {"ok": False, "error": "missing id param for this dataset"}
        if not live.ok:
            return _failed_live_response(live, entity_scoped, entity, table, season)
        store.save_frame(table, live, entity)
        if entity_scoped:
            frame = store.read_frame(
                table, "_fetched_at = ?", [live.meta.fetched_at]
            )
        else:
            frame = store.read_frame(table, "_season = ?", [season])
    if (name in ("player_gamelogs", "team_games", "playoff_gamelogs")
            and frame.height > 0 and "GAME_DATE" in frame.columns):
        frame = _sort_frame_by_game_date(frame)
    if name in ("player_gamelogs", "team_games", "playoff_gamelogs") and frame.height > 0:

        from shared.tools.gamelog import dedupe_game_log_frame

        frame = dedupe_game_log_frame(frame)
    if fmt == "csv":
        return Response(frame.write_csv(), media_type="text/csv")
    if fmt == "parquet":
        buf = io.BytesIO()
        frame.write_parquet(buf)
        return Response(buf.getvalue(), media_type="application/octet-stream")
    out = _datasets_envelope(table, season, frame, cached)
    out["ok"] = True
    return out

@router.get("/threads")
def threads(client: str = Query("")) -> dict:
    from shared import store

    return {"threads": store.list_threads(owner=client[:80])}

@router.get("/threads/{thread_id}/runs")
def thread_runs(thread_id: str, client: str = Query("")) -> dict:
    from shared import store

    return {"runs": store.list_runs(thread_id, owner=client[:80])}

def _export_table_lines(t: dict) -> list[str]:
    lines = [f"Source table: {t.get('tool', '?')}"]
    meta = t.get("meta") if isinstance(t.get("meta"), dict) else {}
    source = meta.get("source")
    fetched_at = meta.get("fetched_at")
    season = meta.get("season")
    identity = [
        f"source {source}" if source else "",
        f"season {season}" if season else "",
        f"fetched {str(fetched_at)[:10]}" if fetched_at else "",
    ]
    if any(identity):
        lines.append("Evidence: " + ", ".join(filter(None, identity)))
    limits = [meta.get("qualification"), meta.get("coverage")]
    warnings = meta.get("warnings")
    if isinstance(warnings, list):
        limits.extend(str(item) for item in warnings if str(item).strip())
    for limit in limits:
        if isinstance(limit, str) and limit.strip():
            lines.append(f"Limit: {limit}")
    return lines

@router.get("/threads/{thread_id}/export")
def thread_export(thread_id: str, client: str = Query("")):
    from shared import store

    runs = store.list_runs(thread_id, owner=client[:80])
    lines = [f"# Dime analysis thread {thread_id}", ""]
    for r in reversed(runs):
        lines.append(f"## Q: {r['question']}")
        lines.append("")
        lines.append(r["answer"] or "")
        lines.append("")
        for t in r["tables"] if isinstance(r["tables"], list) else []:
            if not isinstance(t, dict):
                continue
            lines.extend(_export_table_lines(t))
        lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")

class CreateBranchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread: str = Field(min_length=1, max_length=80)
    client: str = Field(min_length=1, max_length=80)
    parent_sequence: int = Field(ge=1)
    branch_id: str | None = Field(default=None, max_length=64)

    @field_validator("thread", "client")
    @classmethod
    def reject_blank_identity(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("thread and client must be non-empty")
        return value

    @field_validator("branch_id")
    @classmethod
    def reject_blank_branch(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("branch id must be non-empty when present")
        return value

def _branch_identity(thread: str, client: str) -> tuple[str, str]:
    if not thread.strip() or not client.strip():
        raise HTTPException(status_code=400, detail="thread and client required")
    return client.strip()[:80], thread.strip()[:80]

@router.post("/v2/branches", status_code=201)
def create_branch(body: CreateBranchBody) -> dict:
    _require_projects()
    owner, thread = _branch_identity(body.thread, body.client)
    try:
        branch = _CONVERSATIONS.create_branch(
            owner, thread, body.parent_sequence, branch_id=body.branch_id)
    except ValueError as exc:
        message = str(exc)
        if "duplicate branch" in message:
            raise HTTPException(status_code=409, detail=message)
        raise HTTPException(status_code=400, detail=message)
    return branch.model_dump(mode="json")

@router.get("/v2/branches")
def list_branches(thread: str = Query(""), client: str = Query("")) -> dict:
    _require_projects()
    owner, name = _branch_identity(thread, client)
    branches = _CONVERSATIONS.list_branches(owner, name)
    return {"branches": [item.model_dump(mode="json") for item in branches]}

@router.get("/v2/branches/{branch_id}")
def get_branch(branch_id: str, thread: str = Query(""),
               client: str = Query("")) -> dict:
    _require_projects()
    owner, name = _branch_identity(thread, client)
    branch = _CONVERSATIONS.get_branch(owner, name, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="branch not found")
    evidence = _CONVERSATIONS.branch_evidence(owner, name, branch.branch_id)
    reuses = _CONVERSATIONS.branch_reuses(owner, name, branch.branch_id)
    return {"branch": branch.model_dump(mode="json"),
            "evidence_count": len(evidence),
            "reused_count": len(reuses)}

class SqlRerunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = ""

@router.post("/sql/rerun")
async def sql_rerun(request: Request, body: SqlRerunBody) -> dict:
    check_sql_rerun(client_ip(request))
    from shared.tools.league import rerun_sql

    sql = (body.sql or "").strip()
    if not sql:
        return {"ok": False, "error": "sql required", "rows": {}}
    if len(sql) > 8000:
        return {"ok": False, "error": "sql too long", "rows": {}}
    out = await rerun_sql(sql)
    if not out.get("ok"):
        return {"ok": False, "error": out.get("error", "rerun failed"),
                "rows": {}}
    return {"ok": True, "rows": {
        "columns": out["columns"], "rows": out["rows"],
        "ms": out.get("ms", 0), "capped": out.get("capped", False),
    }}

@router.get("/resolve")
def resolve(q: str = Query("")) -> dict:
    from shared.tools import resolve_entity

    return resolve_entity.invoke({"query": q[:80]})

class TradeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_a: str = ""
    players_a: str | list[str] = ""
    team_b: str = ""
    players_b: str | list[str] = ""
    season: str = "2025-26"

    @field_validator("players_a", "players_b")
    @classmethod
    def normalize_players(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ", ".join(item.strip() for item in value if item.strip())
        return value

@router.post("/trade/check")
def trade_check(body: TradeBody) -> dict:
    from shared.tools import get_trade_check

    return get_trade_check.invoke({
        "team_a": body.team_a, "players_a": body.players_a,
        "team_b": body.team_b, "players_b": body.players_b,
        "season": body.season,
    })

CARDS_DIR = _BACKEND / "data" / "cards"
_DEBATE_FILE_RE = re.compile(r"^debate_[A-Za-z0-9]+_vs_[A-Za-z0-9]+_[0-9]+\.html$")

@router.get("/debate-card")
def debate_card(
    a: str = Query(""),
    b: str = Query(""),
    season: str = Query("2025-26"),
) -> dict:
    from shared.tools import get_debate_card
    from shared.tools._core import InvalidSeasonError, clamp_season

    qa = (a or "").strip()[:80]
    qb = (b or "").strip()[:80]
    if not qa or not qb:
        return {"ok": False, "error": "two player names required"}
    try:
        clamped = clamp_season(season)
    except InvalidSeasonError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        res = get_debate_card.invoke({"a": qa, "b": qb, "season": clamped})
    except Exception:
        return {"ok": False, "error": "debate card failed"}
    if not isinstance(res, dict) or not res.get("ok"):
        err = res.get("error", "debate card failed") if isinstance(res, dict) else "debate card failed"
        return {"ok": False, "error": err}
    rows = res.get("rows", {}) if isinstance(res.get("rows"), dict) else {}
    raw_path = str(rows.get("path", ""))
    basename = os.path.basename(raw_path)
    players = rows.get("players", [qa, qb])
    return {
        "ok": True,
        "path": basename,
        "players": players,
        "url": f"/api/debate-card/file?name={basename}",
        "rows": {
            "path": basename,
            "players": players,
            "url": f"/api/debate-card/file?name={basename}",
        },
        "meta": {"season": clamped},
    }

@router.get("/debate-card/file")
def debate_card_file(name: str = Query("")) -> FileResponse:
    if not _DEBATE_FILE_RE.fullmatch(name or ""):
        raise HTTPException(status_code=400, detail="invalid file name")
    target = CARDS_DIR / name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(
        target,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )

@router.get("/today")
async def today(season: str = Query("2025-26")):
    from shared.tools.today import get_today

    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None, lambda: get_today.invoke({"season": season}))
    return json.loads(res) if isinstance(res, str) else res

@router.get("/watchlist")
async def watchlist(season: str = Query("2025-26")):
    from shared.tools.watchlist import get_watchlist

    res = get_watchlist.invoke({"season": season})
    return json.loads(res) if isinstance(res, str) else res

class WatchlistBody(BaseModel):
    entity_type: str
    entity_id: str
    season: str = "2025-26"

@router.post("/watchlist")
async def watchlist_add(body: WatchlistBody):
    from shared.tools.watchlist import add_watchlist_item

    res = add_watchlist_item.invoke({
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "season": body.season,
    })
    return json.loads(res) if isinstance(res, str) else res

@router.delete("/watchlist")
async def watchlist_remove(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
):
    from shared.tools.watchlist import remove_watchlist_item

    res = remove_watchlist_item.invoke({
        "entity_type": entity_type,
        "entity_id": entity_id,
    })
    return json.loads(res) if isinstance(res, str) else res

@router.get("/movers")
async def movers(
    season: str = Query("2025-26"),
    days: int = Query(7, ge=1, le=30),
):
    from shared.tools.league import get_leaderboard_deltas
    from shared.tools.today import normalize_movers

    res = get_leaderboard_deltas.invoke({"season": season, "days": days})
    out = json.loads(res) if isinstance(res, str) else res
    return normalize_movers(out, season)

@router.get("/briefing")
async def briefing(season: str = Query("2025-26")):
    from shared.tools.today import get_morning_briefing

    res = get_morning_briefing.invoke({"season": season})
    return json.loads(res) if isinstance(res, str) else res

def public_evidence_table(item):
    return {"tool": item.capability, "rows": item.rows, "meta": {
        "source": item.source,
        "source_as_of": item.as_of.isoformat() if item.as_of else None,
        "observed_at": item.observed_at.isoformat(), "season": item.season,
        "as_of": item.as_of.isoformat() if item.as_of else None,
        "qualification": item.qualification, "coverage": item.coverage,
        "warnings": item.warnings,
    }}

class CreateProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=2000)

    @field_validator("goal")
    @classmethod
    def reject_blank_goal(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project goal must be non-empty")
        return value

@router.post("/projects", status_code=201)
def create_project(body: CreateProjectBody) -> dict:
    _require_projects()
    return _PROJECTS.create(body.goal).model_dump(mode="json")

@router.get("/projects")
def list_projects() -> dict:
    _require_projects()
    return {"projects": [item.model_dump(mode="json") for item in _PROJECTS.list()]}

@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    _require_projects()
    project = _PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project.model_dump(mode="json")

from v2.contracts import ConversationTurn

class QuickAnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, max_length=256)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    thread: str | None = Field(default=None, min_length=1, max_length=80)
    client: str | None = Field(default=None, min_length=1, max_length=80)
    diagnostics: bool = False

    @field_validator("q")
    @classmethod
    def reject_blank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must be non-empty")
        return value

    @field_validator("model")
    @classmethod
    def reject_blank_model(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("model must be non-empty when present")
        return value

    @field_validator("thread", "client")
    @classmethod
    def reject_blank_identity(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("thread and client must be non-empty when present")
        return value

    @model_validator(mode="after")
    def require_complete_conversation_identity(self):
        if self.thread is not None and self.client is None:
            raise ValueError("thread and client must be provided together")
        return self

@router.post("/v2/chat/stream")
async def chat_stream_post(request: Request, body: QuickAnswerBody):
    return await _guarded_chat_stream(request, body)

@router.get("/v2/chat/stream")
async def chat_stream_get(
    request: Request,
    q: str = Query(""),
    model: str | None = Query(None),
    thread: str | None = Query(None),
    client: str | None = Query(None),
    diagnostics: bool = Query(False),
):

    conversation_client = (
        (client or request.headers.get("x-dime-client") or None)
        if thread is not None
        else client
    )
    return await _guarded_chat_stream(
        request,
        QuickAnswerBody(
            q=q,
            model=model,
            thread=thread,
            client=conversation_client,
            diagnostics=diagnostics,
        ),
    )

async def _guarded_chat_stream(request: Request, body: QuickAnswerBody):
    if not _chat_allowed(_client_ip(request)):
        return _rate_limited_stream()
    response = await quick_answer_stream(body)
    response.body_iterator = with_heartbeat(response.body_iterator)
    return response

_CHAT_HITS: dict[str, list[float]] = defaultdict(list)

def _chat_allowed(ip: str) -> bool:
    from shared.config import settings

    now = time.time()
    window = [t for t in _CHAT_HITS[ip] if now - t < 60]
    _CHAT_HITS[ip] = window
    if len(window) >= settings.chat_rate_per_minute:
        return False
    window.append(now)
    return True

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

def _rate_limited_stream():
    from fastapi.responses import StreamingResponse
    from v2.api.events import Failure
    from v2.api.sse import encode_event

    async def limited():
        chunk = encode_event(Failure(
            kind="rate_limited", message="rate limited, retry soon"))
        if chunk is not None:
            yield chunk
        yield encode_raw("error", {"message": "rate limited, retry soon"})
        yield encode_raw("graph_end", {})

    return StreamingResponse(limited(), media_type="text/event-stream")

def _pi_sources_dir() -> Path:
    return Path(os.environ.get("DIME_PI_SOURCES_DIR", str(_BACKEND / "data" / "pi-sources")))


@router.get("/v2/runs/{run_id}/sources")
def run_sources(run_id: str, thread: str = Query(""), client: str = Query("")):
    _require_projects()
    owner, name = _branch_identity(thread, client)
    from analyst.sources import read_sources
    try:
        return read_sources(_CONVERSATIONS, _pi_sources_dir(), owner, name, run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="not found")


async def quick_answer_stream(body: QuickAnswerBody):
    _require_projects()
    import shutil
    import sys
    import uuid
    from fastapi.responses import StreamingResponse
    from shared import store
    from analyst.configuration import resolve_product_model, worker_environment
    from analyst.product_session import stream_product_session
    from v2.api.events import Failure, GraphEnd
    from v2.api.sse import encode_event

    run_id = f"run-{uuid.uuid4().hex}"
    try:
        descriptor = resolve_product_model(body.model)
        node = shutil.which("node")
        if node is None:
            raise ValueError("Node runtime unavailable")
    except (ValueError, OSError):
        async def error():
            yield encode_event(Failure(kind="configuration", message="Dime model configuration is unavailable."))
            yield encode_event(GraphEnd())
        return StreamingResponse(error(), media_type="text/event-stream",
                                 headers={"X-Dime-Run-Id": run_id})

    stream = stream_product_session(q=body.q, model=descriptor, node=node,
        python=sys.executable, env=worker_environment(), warehouse=store.DB_PATH.resolve(),
        private_root=Path(os.environ.get("DIME_PI_PRIVATE_DIR", str(_BACKEND / "data" / "pi-private"))),
        sources_dir=_pi_sources_dir(), conversations=_CONVERSATIONS, store=store,
        client=body.client if body.thread else None, thread=body.thread, history=body.history,
        run_id=run_id)
    async def generate():
        from shared.config import settings
        try:
            async with asyncio.timeout(settings.dime_v2_run_timeout_s):
                async for chunk in stream:
                    yield chunk
        except TimeoutError:
            yield encode_event(Failure(kind="timeout", message="The run timed out before finishing."))
            yield encode_event(GraphEnd())
        finally:
            await stream.aclose()
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Dime-Run-Id": run_id})
