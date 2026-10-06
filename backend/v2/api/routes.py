from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import marshal
import time
from collections import defaultdict
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
    return runtime_v2_mode() == "on"


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
    for root in (_BACKEND / "app", _BACKEND / "v2"):
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("executable source tree cannot contain symlinks")
            if path.is_file() and path.suffix in {".py", ".md"}:
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
            "sha256": identity["warehouse_sha256"]}


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
    from v2.adapters import models
    prompts = models.bind_provider_route_prompts()
    expected_routes = set(models._PROVIDER_ROUTE_PROMPT_NAMES)
    if set(prompts) != expected_routes or expected_routes != {
            "intake", "requirement_review", "planner", "synthesizer",
            "repair", "semantic_verifier"}:
        raise RuntimeError("provider prompt registry is incomplete or has extra routes")
    for module in (__import__(__name__, fromlist=["x"]), models):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(_BACKEND):
            raise RuntimeError("runtime module resolved outside the backend root")
    return RuntimeAssetManifest(
        revision=_revision(), executable_sha256=_executable_sha256(),
        module_sha256=MappingProxyType({
            "routes": _loaded_behavior_sha256(
                __import__(__name__, fromlist=["x"]),
                {"provider_routes": sorted(models._PROVIDER_ROUTE_PROMPT_NAMES)}),
            "models": _loaded_behavior_sha256(
                models, {"provider_route_prompt_names":
                         models._PROVIDER_ROUTE_PROMPT_NAMES}),
        }),
        warehouse=MappingProxyType(dict(runtime_warehouse_identity())),
        semantic_baseline=__import__(
            "v2.semantic_baseline", fromlist=["SEMANTIC_BASELINE"]
        ).SEMANTIC_BASELINE,
        prompt_sha256=MappingProxyType({
            route: hashlib.sha256(prompt.encode()).hexdigest()
            for route, prompt in prompts.items()
        }),
        typed_argument_assets=MappingProxyType(_typed_argument_asset_hashes()),
    )


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
        pin = ["RANK", "PLAYER", "TEAM", stat_col, "GP", "MIN"]
        pinned = []
        for r in rows:
            keyed = {k: r[k] for k in pin if k in r}
            keyed.update({k: v for k, v in r.items() if k not in keyed})
            pinned.append(keyed)
        rows = pinned
    if table == "silver_standings":


        pin = ["TeamCity", "TeamName", "Conference", "Record",
               "WINS", "LOSSES", "WinPCT", "PlayoffRank",
               "ClinchIndicator"]
        pinned = []
        for r in rows:
            keyed = {k: r[k] for k in pin if k in r}
            keyed.update({k: v for k, v in r.items() if k not in keyed})
            pinned.append(keyed)
        rows = pinned
    if table == "silver_lineups":
        from shared.tools._core import sample_tier

        for r in rows:
            tier, est = sample_tier(r.get("MIN"))
            r["SAMPLE_TIER"] = tier
            r["EST_POSS"] = est
            if tier == "small" and not r.get("SAMPLE"):
                r["SAMPLE"] = "small: under ~100 possessions"
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
        from shared.tools.player import get_wowy

        res = get_wowy.invoke(
            {"player_a": player_a or ids, "player_b": player_b, "team_id": team_id, "season": season}
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "wowy failed")}
        rows = res.get("rows", [])
        if fmt == "csv":
            df = pl.DataFrame(rows)
            return Response(df.write_csv(), media_type="text/csv")
        return {"ok": True, "data": rows, "verdict": res.get("verdict"), "meta": res.get("meta")}

    if name not in _DATASETS_TABLES:
        return {"ok": False, "error": f"unknown dataset, pick one of {sorted(_DATASETS_TABLES)}"}
    from shared import store

    table = _DATASETS_TABLES[name]
    if name == "leaders":
        from shared.tools import clamp_stat

        try:
            stat = clamp_stat(stat)
        except ValueError:
            stat = "PTS"
        table = f"silver_leaders_{stat.lower()}"
    entity_scoped = name in ("player_gamelogs", "team_games", "shots", "scoreboard", "lineups", "on_off", "wowy", "four_factors")
    entity = ""
    if player_id:
        entity = f"player:{player_id}"
    elif team_id:
        entity = f"team:{team_id}"
    elif game_id:
        entity = f"game:{game_id}"
    elif game_date:
        entity = f"date:{game_date}"
    elif ids:
        entity = f"wowy:{ids}"
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
        store.save_frame(table, live, entity)
        if entity_scoped:
            frame = store.read_frame(
                table, "_fetched_at = ?", [live.meta.fetched_at]
            )
        else:
            frame = store.read_frame(table, "_season = ?", [season])
    if (name in ("player_gamelogs", "team_games", "playoff_gamelogs")
            and frame.height > 0 and "GAME_DATE" in frame.columns):


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
            lines.append(f"Source table: {t.get('tool', '?')}")
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
        if (self.thread is None) != (self.client is None):
            raise ValueError("thread and client must be provided together")
        return self


def _output_line(result, status) -> str:
    binding = status.binding
    if binding.requirement_kind == "calculation":
        calculation = next(item for item in result.draft.calculations
                           if item.calculation_id == binding.calculation_id)
        value = str(calculation.result)
        unit = calculation.unit or "unitless"
        subject = ""
    else:
        raw = binding.value
        value = ("true" if raw.value else "false") if raw.kind == "boolean" else str(raw.value)
        unit = (binding.unit.value if binding.unit.kind == "declared" else "unitless")
        subject = (f" [{binding.subject_entity_type}:{binding.subject_entity_id}]"
                   if binding.subject_entity_id is not None else "")
    return f"{status.output_id}{subject} = {value} ({unit})"


LIVE_SOURCE_NAMES = {
    "nba_api": "the NBA's live feed",
    "basketball_reference": "Basketball Reference",
    "espn": "ESPN",
}

LIVE_SOURCE_LINES = {
    "live_only": ("These figures came from {sources}{when}, not from the figures "
                  "I had saved, so they can differ from numbers you saw earlier."),
    "mixed": ("Some of these figures were refreshed from {sources}{when}; the "
              "rest came from the figures I had saved."),
}

UNTRACED_SUFFIX = " could not be traced to the source data."


def _live_source_line(result) -> str | None:
    sources: set[str] = set()
    from_saved_figures = False
    as_of = None
    for envelope in result.execution.evidence:
        identity = envelope.source_identity
        if identity is None:
            continue
        if identity.kind == "live":
            sources.add(identity.source)
        else:
            from_saved_figures = True
            if identity.kind == "composite":
                sources.update(identity.live_sources)
        if envelope.as_of is not None and (as_of is None or envelope.as_of > as_of):
            as_of = envelope.as_of
    if not sources:
        return None
    names = [name for source, name in LIVE_SOURCE_NAMES.items() if source in sources]
    names += sorted(sources - LIVE_SOURCE_NAMES.keys())
    story = "mixed" if from_saved_figures else "live_only"
    return LIVE_SOURCE_LINES[story].format(
        sources=", ".join(names), when=f" on {as_of}" if as_of else "")


def _claim_prose(result) -> list[str]:
    from v2.runtime.models import withheld_claim_indices

    withheld = withheld_claim_indices(result.gaps)
    claims = [item for item in result.verified_claims
              if item.claim_index not in withheld]
    if not claims:
        return []
    internal = _internal_identifier_rx(result)
    lines: list[str] = []
    for item in claims:
        prose = _publishable_prose(item.claim.text, internal)
        if prose is None:
            lines.extend(_label_lines(result, item.claim.output_bindings))
        else:
            lines.append(prose)
    return list(dict.fromkeys(lines))


_SCRUB_REFERRAL = "the data"
_SCRUB_COVERAGE_LIMIT = 0.6


def _scrub_digits(m: re.Match[str]) -> str:
    digits = m.group(0)
    if len(digits) == 4 and 1900 <= int(digits) <= 2100:
        return digits
    return ""


_PROSE_SCRUB_RULES: tuple[
    tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    (re.compile(
        r"\[[a-z_]{2,20}:\s*(?=[A-Za-z0-9_.\-]*\d)[A-Za-z0-9_.\-]{1,64}\]",
        re.IGNORECASE), ""),
    (re.compile(
        r"\b(?:evidence|evidence_id|node|node_id|claim|claim_index|"
        r"requirement|requirement_id|calculation|calculation_id|capability|"
        r"selector|row_selector|subject_selector|resolve|row-scan|"
        r"web_search|web_fetch)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_.:\-]{1,96}[\"']?"), _SCRUB_REFERRAL),
    (re.compile(
        r"\b(?:player|player_id|team|team_id|entity|entity_id|subject|"
        r"subject_id|output|output_id|domain)\b"
        r"\s*=\s*[\"']?[A-Za-z0-9_.:\-]{1,96}[\"']?"), _SCRUB_REFERRAL),
    (re.compile(
        r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\s*:\s*[A-Za-z0-9_.\-]{1,96}\b",
        re.IGNORECASE), _SCRUB_REFERRAL),
    (re.compile(
        r"\b[a-z][a-z0-9_]{1,20}\s*:\s*"
        r"(?=[A-Za-z0-9_.\-]*(?:[_\-.][A-Za-z0-9_.\-]*|[0-9]{3,}))"
        r"[A-Za-z0-9_.\-]{1,96}\b"), _SCRUB_REFERRAL),
    (re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", re.IGNORECASE),
     _SCRUB_REFERRAL),
    (re.compile(
        r"\b(?:rows?|lines?|columns?|cells?|season_line|matches|meta|values)\b"
        r"(?:\s*\[\s*\d*\s*\]|\s*\[\s*\]|\.[A-Za-z_][A-Za-z0-9_]*)+",
        re.IGNORECASE), _SCRUB_REFERRAL),
    (re.compile(r"\d{4,}"), _scrub_digits),
)


_PROSE_TIDY_RULES: tuple[tuple["re.Pattern[str]", str], ...] = (
    (re.compile(r"[(\[{]\s*[)\]}]"), ""),
    (re.compile(r"\bthe the\b", re.IGNORECASE), "the"),
    (re.compile(r" +([.,;:!?])"), r"\1"),
    (re.compile(r"[ \t]{2,}"), " "),
)

_PROSE_EDGE_RX = re.compile(r"^[\s,;:.\-]+|[\s,;:\-]+$")

_IDENTIFIER_SHAPE_RX = re.compile(r"[_\-.:\d]")
_BINDING_INTERNAL_FIELDS = (
    "evidence_id", "node_id", "selector", "row_selector", "subject_selector",
    "subject_entity_id", "requirement_id", "calculation_id", "domain")


def _internal_identifiers(result) -> set[str]:
    identifiers = {envelope.evidence_id for envelope in result.execution.evidence}
    identifiers |= {envelope.capability for envelope in result.execution.evidence}
    identifiers |= {node.id for node in result.execution.plan.nodes}
    for item in result.verified_claims:
        identifiers |= set(item.claim.evidence_ids)
        if item.claim.calculation_id is not None:
            identifiers.add(item.claim.calculation_id)
        for binding in item.claim.output_bindings:
            identifiers |= {
                getattr(binding, field) for field in _BINDING_INTERNAL_FIELDS
                if getattr(binding, field, None) is not None}
    return {value for value in identifiers if _IDENTIFIER_SHAPE_RX.search(value)}


def _internal_identifier_rx(result) -> "re.Pattern[str] | None":
    identifiers = sorted(_internal_identifiers(result), key=len, reverse=True)
    if not identifiers:
        return None
    return re.compile("|".join(
        rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])"
        for value in identifiers))


def _publishable_prose(
        text: str, internal: re.Pattern[str] | None) -> str | None:
    original = text
    covered = 0
    for pattern, replacement in _PROSE_SCRUB_RULES:
        covered += sum(len(match.group(0))
                       for match in pattern.finditer(text))
        text = pattern.sub(replacement, text)
    for pattern, replacement in _PROSE_TIDY_RULES:
        text = pattern.sub(replacement, text)
    text = _PROSE_EDGE_RX.sub("", text)
    if text[:1].islower():
        text = text[:1].upper() + text[1:]
    if not text or covered >= _SCRUB_COVERAGE_LIMIT * len(original):
        return None
    if internal is not None and internal.search(text):
        return None
    return text


def _label_lines(result, bindings) -> list[str]:
    keys = {(binding.requirement_kind, binding.requirement_id,
             binding.output_id) for binding in bindings}
    return [_output_line(result, status) for status in result.output_statuses
            if status.status == "complete"
            and (status.requirement_kind, status.requirement_id,
                 status.output_id) in keys]


def _prose_covered_output_ids(result) -> set[str]:
    from v2.runtime.models import withheld_claim_indices
    verified = list(getattr(result, "verified_claims", None) or [])
    if not verified:
        return set()
    try:
        withheld = withheld_claim_indices(getattr(result, "gaps", None) or [])
    except Exception:
        withheld = set()
    try:
        internal = _internal_identifier_rx(result)
    except Exception:
        internal = None
    draft_claims = list(
        getattr(getattr(result, "draft", None), "claims", None) or [])
    covered: set[str] = set()
    for item in verified:
        index = getattr(item, "claim_index", None)
        if index in withheld:
            continue
        claim = getattr(item, "claim", None)
        text = getattr(claim, "text", None)
        if not isinstance(text, str) or not text:
            continue
        try:
            prose = _publishable_prose(text, internal)
        except Exception:
            continue
        if prose is None:
            continue
        for binding in (getattr(claim, "output_bindings", None) or []):
            output_id = getattr(binding, "output_id", None)
            if isinstance(output_id, str) and output_id:
                covered.add(output_id)
        for binding in (getattr(item, "output_bindings", None) or []):
            output_id = getattr(binding, "output_id", None)
            if isinstance(output_id, str) and output_id:
                covered.add(output_id)
        if isinstance(index, int) and 0 <= index < len(draft_claims):
            for binding in (
                    getattr(draft_claims[index], "output_bindings", None)
                    or []):
                output_id = getattr(binding, "output_id", None)
                if isinstance(output_id, str) and output_id:
                    covered.add(output_id)
    return covered


def _answer_text(result) -> str:
    published = {
        item.output_id for item in result.output_statuses
        if item.status == "complete"
    }
    stated = _prose_covered_output_ids(result)
    lines = _claim_prose(result) or list(dict.fromkeys(
        _output_line(result, item) for item in result.output_statuses
        if item.status == "complete"))
    source_line = _live_source_line(result)
    if source_line is not None:
        lines.append(source_line)
    gap_messages = {
        "source_conflict": "Available sources conflict for some requested outputs.",
        "unsupported_claim": "Some requested outputs were not supported.",
        "execution_failure": "Some requested data was unavailable.",
        "synthesis_incomplete": "Some requested outputs could not be published.",
        "judge_unavailable": "I couldn't double-check this answer, so treat the details with extra care.",
    }
    kinds = []
    for gap in result.gaps:
        if gap.kind.value not in kinds:
            kinds.append(gap.kind.value)
    try:
        from v2.runtime.loop import JUDGE_UNAVAILABLE_BRANCHES as _judge_branches
    except Exception:
        _judge_branches = frozenset()
    if any(getattr(gap, "message", None) in _judge_branches
           for gap in result.gaps) and "judge_unavailable" not in kinds:
        kinds.append("judge_unavailable")
    all_complete = bool(result.output_statuses) and all(
        item.status == "complete" for item in result.output_statuses)
    requested_ids = {item.output_id for item in result.output_statuses}
    fully_covered = bool(result.output_statuses) and requested_ids <= (published | stated)
    unverified_output_ids = [
        item.output_id for item in result.output_statuses
        if item.status != "complete" and item.output_id not in published
        and item.output_id not in stated]
    for kind in kinds:
        if kind == "missing_evidence" and all_complete:
            continue
        if kind in ("missing_evidence", "synthesis_incomplete") and fully_covered:
            continue
        if kind == "missing_evidence":
            if unverified_output_ids:
                lines.append(
                    "Some requested outputs could not be verified: "
                    + ", ".join(unverified_output_ids) + ".")
            else:
                lines.extend(
                    gap.message for gap in result.gaps
                    if gap.kind.value == "missing_evidence")
            continue
        lines.append(gap_messages[kind])
    lines += list(dict.fromkeys(
        f"{item.output_id} could not be verified ({item.status})."
        for item in result.output_statuses
        if item.status != "complete" and item.output_id not in published
        and item.output_id not in stated))
    return "\n".join(lines) or "I could not verify a publishable answer from the available data."


def _output_display_name(output_id: str, definitions=None) -> str:
    definition = (definitions or {}).get(output_id)
    if definition:
        head = definition.split(":", 1)[0].strip()
        if head and len(head) <= 64:
            return head
    humanized = output_id.replace("_", " ").strip()
    if humanized and humanized == humanized.lower():
        return humanized.upper()
    return humanized or output_id


def _envelope_definitions(result, evidence_id: str) -> dict:
    try:
        for item in result.execution.evidence:
            if getattr(item, "evidence_id", None) == evidence_id:
                return dict(getattr(item, "metric_definitions", None) or {})
    except Exception:
        return {}
    return {}


def _public_gaps(result) -> list[dict]:
    return [{"kind": gap.kind.value, "blocks": list(gap.blocks)}
            for gap in result.gaps]


def _status_subject(task) -> tuple[str, str]:
    entities = getattr(task, "entities", None) or []
    names: list[str] = []
    for entity in list(entities)[:2]:
        name = str(getattr(entity, "display_name", None)
                   or getattr(entity, "id", "") or "").strip()
        if name:
            names.append(name)
    season_obj = getattr(task, "season", None)
    season = getattr(season_obj, "value", season_obj)
    season = str(season).strip() if isinstance(season, str) and str(season).strip() else ""
    if names:
        base = " and ".join(names)
        return (base[:80], season)
    phrases: list[str] = []
    for req in getattr(task, "requirements", None) or []:
        desc = str(getattr(req, "description", "") or "").strip()
        if desc:
            phrases.append(" ".join(desc.split()[:5]))
    topic = phrases[0] if phrases else ""
    if not topic:
        goal = str(getattr(task, "goal", "") or "")
        stop = {"who", "what", "which", "when", "where", "how", "led", "lead",
                "leads", "league", "the", "a", "an", "in", "for", "of", "is",
                "are", "was", "were", "top", "list", "show", "give", "tell",
                "me", "please", "find", "get", "name"}
        words = [w.strip("?.,;:!") for w in goal.split()]
        kept = [w for w in words if w and w.lower() not in stop]
        topic = " ".join((kept or words)[:5]).strip()
    if not topic:
        topic = "the numbers"
    return (topic[:80], season)


def _status_lines(task) -> list[str]:
    if task is None:
        return []
    base_raw, season_raw = _status_subject(task)
    base = base_raw.strip()
    season = season_raw.strip()
    lines: list[str] = []
    if base:
        if season and season not in base:
            subject = f"{base} for {season}"[:80].strip()
        else:
            subject = base[:80].strip()
        lines.append(f"Checking {subject}…")
        if season and season not in base:
            lines.append(f"Comparing {base} across {season}…")
        else:
            lines.append(f"Comparing {base}…")
    lines.append("Verifying every number…")
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped[:3]


def _public_output_status(result, status) -> dict:
    item = {"requirement_kind": status.requirement_kind,
            "requirement_id": status.requirement_id,
            "output_id": status.output_id, "status": status.status}
    if status.status == "complete":
        binding = status.binding
        if binding.requirement_kind == "calculation":
            calculation = next(x for x in result.draft.calculations
                               if x.calculation_id == binding.calculation_id)
            item.update(value=str(calculation.result),
                        unit=calculation.unit or "unitless",
                        display_name=_output_display_name(status.output_id))
        else:
            item.update(value=("true" if binding.value.kind == "boolean" and binding.value.value
                               else "false" if binding.value.kind == "boolean"
                               else str(binding.value.value)),
                        unit=(binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                        subject_type=binding.subject_entity_type,
                        subject_id=binding.subject_entity_id,
                        display_name=_output_display_name(
                            status.output_id,
                            _envelope_definitions(result, binding.evidence_id)))
    return item


def _citation_provenance(envelope) -> dict:
    identity = envelope.source_identity
    if identity is None:
        origin, live_sources, warehouse_id = "undeclared", [], None
    elif identity.kind == "live":
        origin, live_sources, warehouse_id = "live", [identity.source], None
    elif identity.kind == "composite":
        origin, live_sources = "mixed", list(identity.live_sources)
        warehouse_id = identity.warehouse_id
    else:
        origin, live_sources, warehouse_id = "warehouse", [], identity.warehouse_id
    return {"capability": envelope.capability,
            "origin": origin,
            "warehouse_id": warehouse_id,
            "season": envelope.season,
            "as_of": envelope.as_of.isoformat() if envelope.as_of else None,
            "live_sources": live_sources}


def _published_bindings(result) -> list:
    from v2.runtime.models import withheld_claim_indices

    verified = list(getattr(result, "verified_claims", None) or [])
    bindings: dict[tuple, object] = {}
    if verified:
        withheld = withheld_claim_indices(getattr(result, "gaps", None) or [])
        internal = _internal_identifier_rx(result)
        for item in verified:
            if item.claim_index in withheld:
                continue
            if _publishable_prose(item.claim.text, internal) is None:
                continue
            for binding in item.claim.output_bindings:
                bindings[(binding.requirement_kind, binding.requirement_id,
                          binding.output_id)] = binding
    for status in result.output_statuses:
        if status.status == "complete" and status.binding is not None:
            bindings.setdefault(
                (status.requirement_kind, status.requirement_id,
                 status.output_id), status.binding)
    return list(bindings.values())


def _traced_value(envelope, binding) -> tuple[Any, str | None]:
    from v2.runtime.models import (
        AmbiguousSelector, ResolvedSelector, _declared_value_matches,
        resolve_evidence_binding, resolve_subject_row,
    )
    from v2.contracts import canonical_entity_id

    subject_row = None
    if binding.subject_entity_id is not None:
        subject_row = resolve_subject_row(envelope, binding, canonical_entity_id(
            binding.subject_entity_type, binding.subject_entity_id))
        if subject_row is None:
            return None, "its subject selector names no row the envelope holds"
    resolution = resolve_evidence_binding(envelope, binding, subject_row)
    if isinstance(resolution, AmbiguousSelector):
        return None, "its selector names several values"
    if not isinstance(resolution, ResolvedSelector) or resolution.value is None:
        return None, "its selector resolves to nothing"
    if not _declared_value_matches(binding.value, resolution.value):
        raise ValueError("publication evidence changed after admission")
    return resolution.value, None


def _public_evidence(result) -> tuple[list[dict], list[str]]:
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex, iter_values
    evidence = {item.evidence_id: item for item in result.execution.evidence}
    calculations = {item.calculation_id: item for item in result.draft.calculations}
    rows: dict[str, dict] = {}
    dropped: list[str] = []
    logger = logging.getLogger(__name__)

    def publish(row: dict) -> None:
        rows.setdefault(json.dumps(row, sort_keys=True), row)

    for binding in _published_bindings(result):
        if binding.requirement_kind != "calculation":
            envelope = evidence.get(binding.evidence_id)
            if envelope is None:
                raise ValueError("publication evidence is missing")
            value, reason = _traced_value(envelope, binding)
            if reason is not None:
                dropped.append(binding.output_id)
                logger.warning("publication could not trace %s: %s",
                               binding.output_id, reason)
                continue
            publish({"output_id": binding.output_id,
                     "display_name": _output_display_name(
                         binding.output_id, envelope.metric_definitions),
                     "subject_type": binding.subject_entity_type,
                     "subject_id": binding.subject_entity_id,
                     "value": str(value),
                     "unit": (binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                     "provenance": _citation_provenance(envelope)})
            continue
        calculation = calculations.get(binding.calculation_id)
        if calculation is None:
            raise ValueError("publication calculation is missing")
        checked = Calculation.model_validate({
            "calculation_id": calculation.calculation_id,
            "operation": calculation.operation,
            "inputs": [item.model_dump() for item in calculation.inputs],
            "result": calculation.result, "unit": calculation.unit,
            "subject_input": calculation.subject_input})
        if validate_calculation(checked, EvidenceIndex(evidence.values())) is not None:
            raise ValueError("publication calculation no longer recomputes")
        for input_ in calculation.inputs:
            envelope = evidence.get(input_.evidence_id)
            selected = ([item.value for item in iter_values(envelope)
                         if item.path == input_.path] if envelope else [])
            if len(selected) != 1:
                raise ValueError("publication calculation input must resolve exactly once")
            publish({"output_id": binding.output_id,
                     "display_name": _output_display_name(binding.output_id),
                     "input_value": str(selected[0]),
                     "provenance": _citation_provenance(envelope)})
    cited = {row["output_id"] for row in rows.values()}
    untraced = list(dict.fromkeys(
        _output_display_name(output_id) + UNTRACED_SUFFIX
        for output_id in (
            *dropped,
            *(status.output_id for status in result.output_statuses
              if status.output_id not in cited))))
    return list(rows.values()), untraced


def _public_capability_name(raw) -> str:
    from v2.adapters import CAPABILITIES
    executable = set(CAPABILITIES) | {"web_search", "web_fetch"}
    return raw if raw in executable else "tool"


def _tool_call_data(name: str, arguments) -> dict:
    from v2.api.activity import ToolCallData
    from v2.runtime.recording import argument_counts, publishable_arguments

    argument_count, unknown_argument_count = argument_counts(name, arguments)
    return ToolCallData(
        name=name,
        arguments=publishable_arguments(name, arguments),
        argument_count=argument_count,
        unknown_argument_count=unknown_argument_count,
    ).model_dump(mode="json")


def _safe_buffered_event(event):
    from v2.api.activity import ToolCallData
    from v2.api.events import NodeUpdate, ToolCall, ToolResult
    kind = str(getattr(event, "type", ""))
    public_nodes = {"entry", "data_retrieval", "tools", "analytics", "presentation"}
    if kind == "node_update":
        if event.node not in public_nodes or event.status not in {"running","complete","error"}:
            return None
        return NodeUpdate(node=event.node, status=event.status)
    if kind == "tool_call":
        return ToolCall(
            node="tools", name=_public_capability_name(getattr(event, "name", None)),
            data=ToolCallData.model_validate(
                getattr(event, "data", None) or {}).model_dump(mode="json"))
    if kind == "tool_result":
        status = getattr(event, "status", None)
        if status not in {"ok", "fail"}:
            return None
        return ToolResult(node="tools", status=status,
                          name=_public_capability_name(getattr(event, "name", None)),
                          error="Tool failed" if status == "fail" else None)
    status = getattr(event, "status", None)
    phase = getattr(event, "phase", None)
    phase_nodes = {"understand":"entry","plan":"data_retrieval",
                   "execute":"tools","verify":"analytics"}
    if phase in phase_nodes and status in {"running", "complete", "failed"}:
        return NodeUpdate(node=phase_nodes[phase],
            status="error" if status == "failed" else status)
    return None


def _stream_binding_diagnostics(result, diagnostics: bool) -> list[str]:
    from v2.api.events import BindingDiagnostic
    from v2.api.sse import encode_event

    if not diagnostics:
        return []
    return [
        encode_event(BindingDiagnostic.model_validate(item), diagnostics=True)
        for item in result.binding_diagnostics
    ]


def _stream_run_diagnostic(exc, run_id, last_stage, diagnostics: bool) -> list[str]:
    from v2.api.events import RunDiagnostic
    from v2.api.sse import encode_event

    if not diagnostics:
        return []
    message = str(exc) or type(exc).__name__
    return [
        encode_event(RunDiagnostic(
            run_id=run_id,
            error_type=type(exc).__name__,
            message=message,
            last_stage=last_stage,
        ), diagnostics=True)
    ]


async def _drain_run(
    task: "asyncio.Task",
    queue: "asyncio.Queue",
    timeout_s: float,
    drain_tick_s: float = 0.1,
) -> list:
    buffered: list = []

    async def _drain_until_done():
        while not task.done() or not queue.empty():
            try:
                buffered.append(
                    await asyncio.wait_for(queue.get(), timeout=drain_tick_s))
            except TimeoutError:
                continue

    await asyncio.wait_for(_drain_until_done(), timeout=timeout_s)
    return buffered


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

    async def limited():
        yield encode_raw("error", {"message": "rate limited, retry soon"})
        yield encode_raw("graph_end", {})

    return StreamingResponse(limited(), media_type="text/event-stream")


async def quick_answer_stream(body: QuickAnswerBody):
    _require_projects()
    import asyncio
    import uuid

    from fastapi.responses import StreamingResponse
    from shared.providers import resolve_model_id
    from shared.config import settings
    from v2.api.events import (
        CustomData, FinalAnswer, GraphEnd, NodeUpdate, ToolCall, ToolResult, WorkLog,
    )
    from v2.api.activity import ActivityJournal
    from v2.api.events import EVENT_ADAPTER
    from v2.api.sse import encode_event
    from v2.runtime.assembly import build_runtime
    from v2.runtime.ledger import LedgerKind
    from v2.runtime.policy import ExecutionPolicy

    run_id = f"run-{uuid.uuid4().hex}"
    queue: asyncio.Queue = asyncio.Queue()
    activity_dir = Path(os.environ.get("DIME_V2_ACTIVITY_DIR", str(_BACKEND / "data" / "v2-activity")))
    try:
        activity_journal = ActivityJournal(activity_dir / f"{run_id}.jsonl", run_id)
    except Exception:
        activity_journal = None

    def activity(payload: dict) -> None:
        if not policy.publish or activity_journal is None:
            return
        internal = payload.pop("correlation_id", None)
        internal_keys = getattr(activity, "internal_keys", set())
        correlation_map = getattr(activity, "correlation_map", {})
        if internal not in correlation_map:
            correlation_map[internal] = f"activity-{len(correlation_map) + 1}"
            activity.correlation_map = correlation_map
        payload["correlation_id"] = correlation_map[internal]
        event = activity_journal.append(**payload)
        common = event.model_dump(mode="json", exclude={"kind"})
        if event.kind == "tool_call":
            carried = {k: v for k, v in common.items() if k != "title"}
            queue.put_nowait(ToolCall(type="tool_call", node="tools", name=event.data.name, label=event.title, **carried))
        elif event.kind == "tool_result":
            carried = {k: v for k, v in common.items() if k not in {"title", "status", "duration_ms"}}
            queue.put_nowait(ToolResult(type="tool_result", node="tools", name=event.data.name, status="ok" if event.transition == "succeeded" else "fail", rows=event.data.rows, ms=event.duration_ms, error=("Tool failed" if event.transition == "failed" else None), **carried))
        else:
            queue.put_nowait(EVENT_ADAPTER.validate_python({"type":event.kind, **common}))
        internal_keys.add((event.kind, internal))
        activity.internal_keys = internal_keys

    def setup_error_stream():
        async def generate_error():
            yield "event: error\ndata: " + json.dumps({
                "message": "Dime could not start this run.",
                "run_id": run_id,
            }, separators=(",", ":")) + "\n\n"
            yield "event: graph_end\ndata: {}\n\n"
        return StreamingResponse(
            generate_error(), media_type="text/event-stream",
            headers={"X-Dime-Run-Id": run_id}, status_code=200,
        )

    try:
        provider, model_name = resolve_model_id(
            body.model or os.environ.get("DIME_V2_MODEL"))
    except Exception:
        return setup_error_stream()

    def public_node(node: str) -> str:
        return {
            "understand": "entry",
            "plan": "data_retrieval",
            "execute": "tools",
            "synthesize": "analytics",
            "verify": "analytics",
            "repair": "analytics",
            "reverify": "analytics",
            "runtime": "presentation",
        }.get(node.split(":", 1)[0], "analytics")

    def progress(node: str, status: str) -> None:
        if not policy.publish:
            return
        public_status = "error" if status == "failed" else status
        queue.put_nowait(NodeUpdate(
            node=public_node(node), status=public_status))

    ledger_dir = os.environ.get(
        "DIME_V2_LEDGER_DIR", str(_BACKEND / "data" / "v2-ledgers"))
    checkpoint_dir = Path(os.environ.get(
        "DIME_V2_CHECKPOINT_DIR", str(_BACKEND / "data" / "v2-checkpoints")))
    runtime_mode = runtime_v2_mode()
    if runtime_mode == "shadow":
        policy = ExecutionPolicy.shadow(ledger_dir=ledger_dir)
    elif runtime_mode == "on":
        policy = ExecutionPolicy.live(ledger_dir=ledger_dir)
    else:
        raise HTTPException(status_code=404, detail="not found")
    policy = ExecutionPolicy.model_validate({
        **policy.model_dump(), "checkpoint_dir": checkpoint_dir,
    })
    try:
        runtime, ledger = build_runtime(
            provider=provider, model_name=model_name, run_id=run_id,
            progress=progress, activity=activity, policy=policy,
            pre_tool_timeout_s=(None if settings.dime_v2_pre_tool_timeout_s <= 0
                                 else settings.dime_v2_pre_tool_timeout_s),
            run_timeout_s=settings.dime_v2_run_timeout_s,
            node_timeout_s=settings.dime_v2_node_timeout_s,
            diagnostics=body.diagnostics)
    except Exception:
        return setup_error_stream()
    context = tuple(body.history)
    if body.thread is not None and body.client is not None:
        context = tuple(_CONVERSATIONS.read(body.client, body.thread))

    def missing_tool_events():
        try:
            entries = ledger.entries
            live_keys = getattr(activity, "internal_keys", set())
            calls = {entry.call_id: entry for entry in entries
                     if entry.kind == LedgerKind.TOOL_CALL and entry.call_id is not None}
            for entry in entries:
                if entry.kind not in {LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT}:
                    continue
                kind = "tool_call" if entry.kind == LedgerKind.TOOL_CALL else "tool_result"
                if (kind, entry.call_id) in live_keys:
                    continue
                call = entry if entry.kind == LedgerKind.TOOL_CALL else calls.get(entry.call_id)
                name = _public_capability_name(
                    call.data.get("name") if call is not None else None)
                recorded = {}
                if call is not None:
                    recorded = (call.data.get("args") or {}).get("node") or {}
                if entry.kind == LedgerKind.TOOL_CALL:
                    yield ToolCall(node="tools", name=name, data=_tool_call_data(
                        name, recorded.get("arguments") or {}))
                else:
                    payload = entry.data; evidence = payload.get("evidence", {}); rows = evidence.get("rows")
                    yield ToolResult(node="tools", name=name,
                        status="ok" if payload.get("status") == "ok" else "fail",
                        rows=len(rows) if isinstance(rows, list) else None,
                        ms=payload.get("duration_ms"), error=("Tool failed" if payload.get("status") == "failed" else None))
        except Exception:
            return

    def stage_latencies_ms():
        return {
            entry.step_id: entry.data["duration_ms"]
            for entry in ledger.entries
            if entry.kind == LedgerKind.STEP_END
            and entry.step_id is not None
            and isinstance(entry.data.get("duration_ms"), int)
        }

    async def generate():


        if body.thread is not None and body.client is not None:
            from shared import store
            store.save_chat(body.thread, "human", body.q[:2000],
                            owner=body.client[:80])
        parent_sequence: int | None = None
        if body.thread is not None and body.client is not None:
            existing = _CONVERSATIONS.references(body.client, body.thread)
            parent_sequence = max(
                (ref.sequence for ref in existing), default=None)
        task = asyncio.create_task(runtime.run(
            body.q, run_id=run_id, context=context))
        try:
            try:


                buffered_events = await _drain_run(
                    task, queue, settings.dime_v2_run_timeout_s)
                result = task.result()
                while not queue.empty():
                    buffered_events.append(queue.get_nowait())

                public_tables, untraced_numbers = _public_evidence(result)
                public_statuses = [_public_output_status(result, item)
                                   for item in result.output_statuses]
                answer = _answer_text(result)
            except Exception as exc:
                timed_out = isinstance(exc, asyncio.TimeoutError)
                if timed_out and not task.done():
                    task.cancel()
                logging.getLogger(__name__).exception("v2 run failed: %r", exc)
                if policy.publish:
                    stages = stage_latencies_ms()
                    last_stage = list(stages)[-1] if stages else None
                    for chunk in _stream_run_diagnostic(
                            exc, run_id, last_stage, body.diagnostics):
                        yield chunk
                    for event in missing_tool_events():
                        safe_event = _safe_buffered_event(event)
                        if safe_event is not None:
                            yield encode_event(safe_event)
                    yield encode_event(WorkLog(run_id=run_id, status="partial"))
                    yield encode_event(FinalAnswer(
                        text=("I could not verify a publishable answer from the available data. "
                              + ("The run timed out before finishing." if timed_out else "")),
                        carry={"run_id": run_id, "verification": "partial",
                               "verified_claims": 0, "structural_flags": [],
                               "gaps": [{"kind": "run_timeout" if timed_out else "execution_failure",
                                         "blocks": []}],
                               "stage_latencies_ms": stage_latencies_ms()}))
                yield encode_event(GraphEnd())
                return
            if policy.publish:
                from v2.api.events import StatusUpdate
                for line in _status_lines(getattr(result, "task", None)):
                    try:
                        chunk = encode_event(StatusUpdate(text=line))
                    except Exception:
                        continue
                    if chunk is not None:
                        yield chunk
                for event in buffered_events:
                    safe_event = _safe_buffered_event(event)
                    if safe_event is not None:
                        yield encode_event(safe_event)
                for event in missing_tool_events():
                    try:
                        safe_event = _safe_buffered_event(event)
                        if safe_event is not None:
                            yield encode_event(safe_event)
                    except Exception:
                        continue
                yield encode_event(WorkLog(
                    run_id=run_id,
                    status="complete" if result.verification.status.value == "pass" else "partial"))
                yield encode_event(CustomData(
                    node="analytics",
                    tables=public_tables,
                    unverified_numbers=untraced_numbers))
                for chunk in _stream_binding_diagnostics(result, body.diagnostics):
                    yield chunk
                carry = {
                    "run_id": run_id,
                    "verification": result.verification.status.value,
                    "verified_claims": len(result.verified_claims),
                    "output_statuses": public_statuses,
                    "structural_flags": list(getattr(result, "structural_flags", [])),
                    "gaps": _public_gaps(result),
                    "stage_latencies_ms": stage_latencies_ms(),
                }
                yield encode_event(FinalAnswer(text=answer, carry=carry))
                if body.thread is not None and body.client is not None:
                    _CONVERSATIONS.append_exchange(
                        body.client, body.thread, body.q, answer)
                    assistant_sequence = max(
                        ref.sequence for ref in
                        _CONVERSATIONS.references(body.client, body.thread))
                    _CONVERSATIONS.record_turn_evidence(
                        body.client, body.thread, assistant_sequence,
                        list(result.execution.evidence))
                    if parent_sequence is not None:
                        branch = _CONVERSATIONS.create_branch(
                            body.client, body.thread, parent_sequence)
                        parent_evidence = _CONVERSATIONS.turn_evidence(
                            body.client, body.thread, parent_sequence)
                        if parent_evidence:
                            _CONVERSATIONS.attach_branch_evidence(
                                body.client, body.thread, branch.branch_id,
                                parent_evidence)
                    if answer:


                        from shared import store
                        store.save_chat(body.thread, "ai", answer,
                                        owner=body.client[:80])
                        store.save_run(body.thread, body.q[:2000], answer,
                                       public_tables, untraced_numbers,
                                       owner=body.client[:80],
                                       run_id=run_id)
            yield encode_event(GraphEnd())
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Dime-Run-Id": run_id})
