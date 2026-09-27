from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import inspect
import marshal
import time
from collections import defaultdict
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Mapping

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from v2.projects.service import ProjectStore
from v2.conversations import ConversationStore
from v2.api.sse import encode_raw, with_heartbeat

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
    return os.environ.get("DIME_RUNTIME_V2", "off").lower() == "on"


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
    """Safe identity of the warehouse bound to this server process."""
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
    """Bind import-time module code plus canonical runtime configuration."""
    code_hash = getattr(module, "_LOADED_MODULE_CODE_SHA256", None)
    if not isinstance(code_hash, str) or len(code_hash) != 64:
        raise RuntimeError("module lacks import-time code identity")
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(code_hash.encode() + b"\0" + encoded).hexdigest()


def _typed_argument_asset_hashes() -> dict[str, str]:
    """Startup pins for checked typed-wire and capability compiler assets."""
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
    """Deeply immutable identity of code, data, and prompts bound at startup."""
    from v2.adapters import models
    prompts = models.bind_provider_route_prompts()
    expected_routes = set(models._PROVIDER_ROUTE_PROMPT_NAMES)
    if set(prompts) != expected_routes or expected_routes != {
            "intake", "intake_admission", "requirement_review", "planner", "synthesizer",
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
    """Fail startup unless one promotion-generated expected manifest matches."""
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
        # Fail closed on substantive drift (code, data, prompts) — this is the
        # safety invariant: never serve unapproved artifacts. The revision
        # label alone is not substantive; :latest moves under pinned revisions
        # during normal deploys, so label mismatch is warn-only.
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
        # Revision-label-only mismatch: warn, don't block deploy.
        _log.warning(
            "startup asset revision label mismatch: expected %s, observed %s",
            expected.get("revision"), observed_dict.get("revision"),
        )
    return observed


@router.get("/revision")
def revision() -> dict:
    # Round-trip gives callers a copy while preserving startup-bound identity.
    return runtime_asset_manifest().as_dict()


def _models_catalog() -> dict:
    # Deferred: shared.providers pulls heavyweight provider SDKs
    # (langchain_*); keep v2.main importable in minimal envs.
    # Same source as the v1 /api/v1/models + /api/v1/health endpoints.
    from shared.providers import models_catalog

    return models_catalog()


@router.get("/models")
def models() -> dict:
    return _models_catalog()


@router.get("/health")
def health() -> dict:
    catalog = _models_catalog()
    return {"ok": True, "providers": catalog["available"]}


# ---------------------------------------------------------------------------
# Datasets (v1-removal Step 3, item 4)
#
# v1 parity for the /api/v1/datasets/* endpoints in app/datasets.py, served
# here as /api/datasets/*. All heavy imports (shared.store, shared.sources,
# shared.tools, polars) stay deferred to call time so v2.main remains
# importable in minimal envs (same pattern as the /models and chat ports).
# Registration order matters: /datasets/freshness must precede
# /datasets/{name} or the literal path is swallowed by the wildcard.
# ---------------------------------------------------------------------------

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

# In-memory cache for the freshness endpoint (v1 parity: per-worker cache,
# 300s TTL; each cached row carries its own last_fetch so the payload is
# self-describing).
_DATASETS_FRESHNESS_TTL_S = 300
_DATASETS_FRESHNESS_CACHE = {"at": 0.0, "payload": None}


def _datasets_freshness_payload() -> dict:
    from shared import store

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
            rows.append({"table": t, "rows": n, "last_fetch": last})
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
        # Pin the stat column after the identity columns so capped table
        # renderers (12-col cap) keep it visible (QA F8, Explore tab).
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
        # Pin the overall record ahead of ConferenceRecord/DivisionRecord:
        # the 12-col render cap used to cut before WINS/LOSSES, so the
        # Explore standings panel showed "41-11" (conference record) as
        # the only record column while the team was 64-18 overall.
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
        from shared.tools._core import trust_tier

        for r in rows:
            tier, est = trust_tier(r.get("MIN"))
            r["TRUST"] = tier
            r["EST_POSS"] = est
            if tier == "SMALL" and not r.get("SAMPLE"):
                r["SAMPLE"] = "small: under ~100 possessions, do not trust"
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

        return nba_stats.leaders(clamp_stat(stat), season)
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

        table = f"silver_leaders_{clamp_stat(stat).lower()}"
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
        # Warehouse storage order is arbitrary; leaders must come back
        # ranked or the Top-10 chart and table drop or bury leaders.
        from shared.tools import clamp_stat

        stat_col = clamp_stat(stat)
        if stat_col in frame.columns:
            frame = frame.sort(stat_col, descending=True, nulls_last=True)
    if entity_scoped:
        # Warehouse-first per entity; never force a live call when seeded.
        if entity:
            try:
                frame = store.read_frame(
                    table, "_season = ? AND _entity = ?", [season, entity])
            except Exception:
                frame = frame.clear()
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _datasets_fetch_live(name, season, player_id, team_id, game_id, game_date, stat, ids)
        if live is None:
            return {"ok": False, "error": "missing id param for this dataset"}
        if not live.ok:
            # Honest attribution: name the failed live source, then stale-fallback.
            stale = None
            if entity_scoped and entity:
                try:
                    stale = store.read_frame(table, "_entity = ?", [entity])
                except Exception:
                    stale = None
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
        # Warehouse storage order is arbitrary; game logs must come back
        # newest-first by REAL date or the panel's "recent" slice quietly
        # shows December string-sort order (QA F19).
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
    if fmt == "csv":
        return Response(frame.write_csv(), media_type="text/csv")
    if fmt == "parquet":
        buf = io.BytesIO()
        frame.write_parquet(buf)
        return Response(buf.getvalue(), media_type="application/octet-stream")
    out = _datasets_envelope(table, season, frame, cached)
    out["ok"] = True
    return out


# ---------------------------------------------------------------------------
# Threads + SQL rerun (v1-removal Step 3, item 4)
#
# v1 parity for GET /api/v1/threads (+/{thread_id}/runs, /{thread_id}/export)
# and POST /api/v1/sql/rerun in app/routes.py, served here as /api/threads/*
# and /api/sql/rerun. Backed by the same shared.store thread log and the
# same shared league.rerun_sql read-only validator.
# ---------------------------------------------------------------------------


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


class SqlRerunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = ""


@router.post("/sql/rerun")
async def sql_rerun(body: SqlRerunBody) -> dict:
    """One-click re-run of a warehouse SQL shown by text_to_sql.

    Boundary: parse and clamp here; read-only validation lives in the
    shared league._validate_readonly_sql used by text_to_sql. (v1 parity)
    """
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
    """Entity resolution passthrough (v1 parity: clamps query to 80 chars)."""
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
    """Trade legality check passthrough (v1 parity)."""
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
    """Shareable debate-card builder (v1 parity; file URL on the v2 mount)."""
    from shared.tools import get_debate_card
    from shared.tools._core import clamp_season

    qa = (a or "").strip()[:80]
    qb = (b or "").strip()[:80]
    if not qa or not qb:
        return {"ok": False, "error": "two player names required"}
    clamped = clamp_season(season)
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
    """Serve a generated debate-card HTML file (v1 parity)."""
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


def public_evidence_table(item):
    """Bounded public projection; internal provenance never crosses SSE."""
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
    identity = (f"{status.requirement_kind}:{status.requirement_id or 'task'}:"
                f"{status.output_id}")
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
    return f"{identity}{subject} = {value} ({unit})"


def _answer_text(result) -> str:
    """Project only deterministically admitted output authority."""
    lines = [_output_line(result, item) for item in result.output_statuses
             if item.status == "complete"]
    for item in result.output_statuses:
        if item.status != "complete":
            identity = (f"{item.requirement_kind}:{item.requirement_id or 'task'}:"
                        f"{item.output_id}")
            lines.append(f"{identity} could not be verified ({item.status}).")
    gap_messages = {
        "missing_evidence": "Some requested outputs could not be verified.",
        "source_conflict": "Available sources conflict for some requested outputs.",
        "unsupported_claim": "Some requested outputs were not supported.",
        "execution_failure": "Some requested data was unavailable.",
        "synthesis_incomplete": "Some requested outputs could not be published.",
    }
    kinds = []
    for gap in result.gaps:
        if gap.kind.value not in kinds:
            kinds.append(gap.kind.value)
    for kind in kinds:
        lines.append(gap_messages[kind])
    return "\n".join(lines) or "I could not verify a publishable answer from the available data."


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
                        unit=calculation.unit or "unitless")
        else:
            item.update(value=("true" if binding.value.kind == "boolean" and binding.value.value
                               else "false" if binding.value.kind == "boolean"
                               else str(binding.value.value)),
                        unit=(binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                        subject_type=binding.subject_entity_type,
                        subject_id=binding.subject_entity_id)
    return item


def _public_evidence_tables(result) -> list[dict]:
    from v2.domain.evidence import iter_values
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex
    evidence = {item.evidence_id:item for item in result.execution.evidence}
    calculations = {item.calculation_id:item for item in result.draft.calculations}
    tables = []
    for status in result.output_statuses:
        if status.status != "complete":
            continue
        binding = status.binding
        if hasattr(binding, "evidence_id"):
            envelope = evidence.get(binding.evidence_id)
            if envelope is None:
                raise ValueError("publication evidence is missing")
            values=[v.value for v in iter_values(envelope) if v.path==binding.selector]
            if len(values)!=1:
                raise ValueError("publication selector must resolve exactly once")
            selected=values[0]; declared=binding.value
            if declared.kind=="boolean": equal=isinstance(selected,bool) and selected is declared.value
            elif declared.kind=="integer": equal=not isinstance(selected,bool) and isinstance(selected,int) and selected==declared.value
            elif declared.kind=="float": equal=isinstance(selected,float) and selected==declared.value
            elif declared.kind=="decimal":
                from decimal import Decimal
                equal=isinstance(selected,Decimal) and selected==Decimal(declared.value)
            else: equal=isinstance(selected,str) and selected==declared.value
            if not equal:
                raise ValueError("publication evidence changed after admission")
            tables.append({"output_id":binding.output_id,
                "subject_type":binding.subject_entity_type,
                "subject_id":binding.subject_entity_id,
                "value":str(binding.value.value),
                "unit":binding.unit.value if binding.unit.kind=="declared" else "unitless",
                "provenance":{"capability":envelope.capability,
                              "season":envelope.season,
                              "as_of":envelope.as_of.isoformat() if envelope.as_of else None}})
        else:
            calculation=calculations.get(binding.calculation_id)
            if calculation is None:
                raise ValueError("publication calculation is missing")
            checked=Calculation.model_validate({"calculation_id":calculation.calculation_id,
                "operation":calculation.operation,"inputs":[x.model_dump() for x in calculation.inputs],
                "result":calculation.result,"unit":calculation.unit,"subject_input":calculation.subject_input})
            if validate_calculation(checked,EvidenceIndex(evidence.values())) is not None:
                raise ValueError("publication calculation no longer recomputes")
            for input_ in calculation.inputs:
                envelope=evidence.get(input_.evidence_id)
                values=[v.value for v in iter_values(envelope)] if envelope else []
                selected=[v.value for v in iter_values(envelope) if v.path==input_.path] if envelope else []
                if len(selected)!=1:
                    raise ValueError("publication calculation input must resolve exactly once")
                tables.append({"output_id":binding.output_id,
                    "input_value":str(selected[0]),
                    "provenance":{"capability":envelope.capability,
                                  "season":envelope.season,
                                  "as_of":envelope.as_of.isoformat() if envelope.as_of else None}})
    return tables


def _safe_buffered_event(event):
    """Closed public-event projection for buffered runtime lifecycle."""
    from v2.api.events import NodeUpdate, ToolCall, ToolResult
    kind = str(getattr(event, "type", ""))
    public_nodes = {"entry", "data_retrieval", "tools", "analytics", "presentation"}
    if kind == "node_update":
        if event.node not in public_nodes or event.status not in {"running","complete","error"}:
            return None
        return NodeUpdate(node=event.node, status=event.status)
    if kind == "tool_call":
        return ToolCall(node="tools", name="tool")
    if kind == "tool_result":
        status = getattr(event, "status", None)
        if status not in {"ok", "fail"}:
            return None
        return ToolResult(node="tools", name="tool", status=status,
                          error="Tool failed" if status == "fail" else None)
    status = getattr(event, "status", None)
    phase = getattr(event, "phase", None)
    phase_nodes = {"understand":"entry","plan":"data_retrieval",
                   "execute":"tools","verify":"analytics"}
    if phase in phase_nodes and status in {"running", "complete", "failed"}:
        return NodeUpdate(node=phase_nodes[phase],
            status="error" if status == "failed" else status)
    return None


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
):
    # GET mirrors the v1 chat stream: no request body, history comes from
    # the conversation store via thread+client (same together-constraint
    # as the POST body).
    return await _guarded_chat_stream(
        request,
        QuickAnswerBody(
            q=q,
            model=model,
            thread=thread,
            client=client or request.headers.get("x-dime-client") or None,
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
    """Sliding-window per-IP chat rate limit (v1 parity).

    Deferred settings import keeps v2.main importable in minimal envs,
    same as the /models port.
    """
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
    from v2.adapters import CAPABILITIES
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
            queue.put_nowait(ToolCall(type="tool_call", node="tools", name=event.data.name, label=event.title, **common))
        elif event.kind == "tool_result":
            queue.put_nowait(ToolResult(type="tool_result", node="tools", name=event.data.name, status="ok" if event.transition == "succeeded" else "fail", rows=event.data.rows, ms=event.duration_ms, error=("Tool failed" if event.transition == "failed" else None), **{k:v for k,v in common.items() if k not in {"status","duration_ms"}}))
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
    runtime_mode = os.environ.get("DIME_RUNTIME_V2", "off").lower()
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
            pre_tool_timeout_s=settings.dime_v2_pre_tool_timeout_s)
    except Exception:
        return setup_error_stream()
    context = tuple(body.history)
    if body.thread is not None and body.client is not None:
        context = tuple(_CONVERSATIONS.read(body.client, body.thread))

    def missing_tool_events():
        """Yield sanitized undelivered ledger tool events in ledger order."""
        try:
            entries = ledger.entries
            live_keys = getattr(activity, "internal_keys", set())
            calls = {entry.call_id: entry for entry in entries
                     if entry.kind == LedgerKind.TOOL_CALL and entry.call_id is not None}
            executable = set(CAPABILITIES) | {"web_search", "web_fetch"}
            for entry in entries:
                if entry.kind not in {LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT}:
                    continue
                kind = "tool_call" if entry.kind == LedgerKind.TOOL_CALL else "tool_result"
                if (kind, entry.call_id) in live_keys:
                    continue
                call = entry if entry.kind == LedgerKind.TOOL_CALL else calls.get(entry.call_id)
                raw_name = call.data.get("name") if call is not None else None
                name = str(raw_name) if raw_name in executable else "tool"
                if entry.kind == LedgerKind.TOOL_CALL:
                    yield ToolCall(node="tools", name=name)
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
        # v1 parity: the human turn lands in the shared thread log so the
        # chat is visible in /api/threads even if the run fails midway.
        if body.thread is not None and body.client is not None:
            from shared import store
            store.save_chat(body.thread, "human", body.q[:2000],
                            owner=body.client[:80])
        task = asyncio.create_task(runtime.run(
            body.q, run_id=run_id, context=context))
        try:
            buffered_events = []
            try:
                while not task.done() or not queue.empty():
                    try:
                        buffered_events.append(
                            await asyncio.wait_for(queue.get(), timeout=0.1))
                    except TimeoutError:
                        continue
                result = await task
                while not queue.empty():
                    buffered_events.append(queue.get_nowait())
                # Validate every public projection before emitting buffered SSE.
                public_tables = _public_evidence_tables(result)
                public_statuses = [_public_output_status(result, item)
                                   for item in result.output_statuses]
                answer = _answer_text(result)
            except Exception as exc:
                if policy.publish:
                    for event in missing_tool_events():
                        safe_event = _safe_buffered_event(event)
                        if safe_event is not None:
                            yield encode_event(safe_event)
                    yield encode_event(WorkLog(run_id=run_id, status="partial"))
                    yield encode_event(FinalAnswer(
                        text="I could not verify a publishable answer from the available data.",
                        carry={"run_id": run_id, "verification": "partial",
                               "verified_claims": 0, "structural_flags": [],
                               "gaps": [{"kind": "execution_failure"}],
                               "stage_latencies_ms": stage_latencies_ms()}))
                yield encode_event(GraphEnd())
                return
            if policy.publish:
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
                    tables=public_tables))
                carry = {
                    "run_id": run_id,
                    "verification": result.verification.status.value,
                    "verified_claims": len(result.verified_claims),
                    "output_statuses": public_statuses,
                    "structural_flags": list(getattr(result, "structural_flags", [])),
                    "gaps": [{"kind": gap.kind.value} for gap in result.gaps],
                    "stage_latencies_ms": stage_latencies_ms(),
                }
                yield encode_event(FinalAnswer(text=answer, carry=carry))
                if body.thread is not None and body.client is not None:
                    _CONVERSATIONS.append_exchange(
                        body.client, body.thread, body.q, answer)
                    if answer:
                        # v1 parity: persist the exchange to the shared
                        # thread log so v2 chats appear in /api/threads,
                        # /api/threads/{thread_id}/runs and .../export.
                        from shared import store
                        store.save_chat(body.thread, "ai", answer,
                                        owner=body.client[:80])
                        store.save_run(body.thread, body.q[:2000], answer,
                                       public_tables, [],
                                       owner=body.client[:80])
            yield encode_event(GraphEnd())
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Dime-Run-Id": run_id})
