from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any, Iterable

UNAVAILABLE_METRICS = ("EPM", "LEBRON", "DARKO", "DRIP", "PER", "BPM",
                       "WS", "VORP")

AVAILABLE_METRICS = {
    "RAPM": {"label": "RAPM-lite", "table": "silver_rapm",
             "note": "ridge on stint differentials; estimate"},
    "ONOFF": {"label": "on-off net", "table": "silver_on_off",
              "note": "lineup splits, noisy"},
    "PIE": {"label": "PIE", "table": "silver_advanced",
            "note": "box-score share"},
    "TRUESHOOTING": {"label": "true shooting", "table": "silver_advanced",
                     "note": "scoring efficiency"},
    "RAPTOR": {"label": "RAPTOR", "table": "silver_raptor_player",
               "note": "box plus on-off; historical vintage, estimate"},
    "WAR": {"label": "WAR", "table": "silver_raptor_player",
            "note": "wins above replacement; historical vintage, estimate"},
}

_ALIASES = {
    "RAPMLITE": "RAPM",
    "TS": "TRUESHOOTING",
    "TSPCT": "TRUESHOOTING",
    "ONOFFNET": "ONOFF",
    "WARTOTAL": "WAR",
}

DEFAULT_TABLE = "silver_boxscores"

LEADERS_TABLES = (
    "silver_leaders_pts",
    "silver_leaders_reb",
    "silver_leaders_ast",
    "silver_leaders_stl",
    "silver_leaders_blk",
    "silver_leaders_dreb",
    "silver_leaders_fg_pct",
)

CAPABILITY_TABLES: dict[str, tuple[str, ...]] = {
    "team_ratings": ("silver_team_ratings",),
    "playoff_team_ratings": ("silver_playoffs",),
    "playoffs": ("silver_playoffs",),
    "season_series": (
        "silver_team_games",
        "silver_playoffs",
        "silver_playoff_gamelogs",
    ),
    "standings": ("silver_standings",),
    "team_trajectory": ("silver_standings",),
    "team_totals": ("silver_boxscores",),
    "game_logs": ("silver_boxscores",),
    "player_report": ("silver_boxscores",),
    "shooting_efficiency": ("silver_advanced",),
    "on_off": ("silver_on_off",),
    "lineups": ("silver_lineups",),
    "shots": ("silver_shots",),
}

_RATE_TO_TOTAL = {
    "PPG": "PTS",
    "RPG": "REB",
    "APG": "AST",
    "SPG": "STL",
    "BPG": "BLK",
}

KNOWN_TABLES = (
    "silver_boxscores",
    "silver_boxscores_ext",
    "silver_lineups",
    "silver_rapm",
    "silver_on_off",
    "silver_advanced",
    "silver_shots",
    "silver_raptor_player",
    "silver_raptor_team",
)

_TABLE_NAME = r"[A-Za-z_][A-Za-z0-9_]*"

_state_lock = threading.RLock()
_season_cache: dict[str, tuple[tuple[int, int], frozenset[str]]] = {}


def table_for_metric(metric: str) -> str:
    key = _ALIASES.get(_key(metric), _key(metric))
    known = AVAILABLE_METRICS.get(key)
    if known:
        return known["table"]
    return DEFAULT_TABLE


def _key(metric: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (metric or "").upper())


def _leaders_table_for_stat(stat: object) -> str | None:
    try:
        from shared.tools._core import clamp_stat
        normalized = clamp_stat(str(stat or ""))
    except Exception:
        return None
    total = _RATE_TO_TOTAL.get(normalized, normalized)
    if total == "TS_PCT":
        return "silver_advanced"
    if total == "FG3_PCT":
        return "silver_leaders_pts"
    return f"silver_leaders_{total.lower()}"


def _arguments_dict(arguments: object) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return dict(arguments)
    as_dict = getattr(arguments, "as_dict", None)
    if callable(as_dict):
        try:
            value = as_dict()
            if isinstance(value, dict):
                return dict(value)
        except Exception:
            return {}
    model_dump = getattr(arguments, "model_dump", None)
    if callable(model_dump):
        try:
            value = model_dump(mode="json")
            if isinstance(value, dict):
                return dict(value)
        except Exception:
            return {}
    return {}


def _requirement_arguments(requirement: object, capability: str) -> dict[str, Any]:
    sets = getattr(requirement, "capability_argument_sets", None) or []
    for item in sets:
        if getattr(item, "capability_id", None) == capability:
            return _arguments_dict(getattr(item, "arguments", None))
    return _arguments_dict(getattr(requirement, "capability_arguments", None))


def tables_for_capability(
    capability: str, arguments: object = None,
) -> tuple[str, ...]:
    name = str(capability or "")
    if name == "qualified_leaders":
        values = _arguments_dict(arguments)
        for key in ("stat_category", "requested_metric", "stat", "metric"):
            if values.get(key) is not None:
                table = _leaders_table_for_stat(values.get(key))
                if table is not None:
                    return (table,)
                break
        return LEADERS_TABLES
    if name == "rookie_leaders":
        return LEADERS_TABLES
    known = CAPABILITY_TABLES.get(name)
    if known is not None:
        return known
    return ()


def task_coverage_groups(task: object) -> list[frozenset[str]]:
    return [tables for _, tables in task_coverage_groups_labeled(task)]


def task_coverage_groups_labeled(
    task: object,
) -> list[tuple[str | None, frozenset[str]]]:
    labeled: list[tuple[str | None, frozenset[str]]] = []
    evidence = [str(item) for item in
                getattr(task, "required_evidence", None) or []]
    for metric in getattr(task, "metric_ids", None) or []:
        table = table_for_metric(str(metric))
        if evidence and table == DEFAULT_TABLE:
            continue
        labeled.append((None, frozenset({table})))
    requirements = list(getattr(task, "requirements", None) or [])
    if not evidence:
        return labeled
    for capability in dict.fromkeys(evidence):
        tables: set[str] = set()
        matched = False
        for requirement in requirements:
            options = list(
                getattr(requirement, "capability_options", None) or [])
            if capability not in [str(option) for option in options]:
                continue
            matched = True
            tables.update(tables_for_capability(
                capability,
                _requirement_arguments(requirement, capability),
            ))
        if not matched:
            tables.update(tables_for_capability(capability, {}))
        if tables:
            labeled.append((capability, frozenset(tables)))
    return labeled


def _classify(metric: str) -> dict[str, str]:
    key = _ALIASES.get(_key(metric), _key(metric))
    for prop in UNAVAILABLE_METRICS:
        if key == _key(prop):
            return {"metric": prop, "status": "unavailable",
                    "note": "not in warehouse, never estimated"}
    known = AVAILABLE_METRICS.get(key)
    if known:
        return {"metric": known["label"], "status": "available",
                "note": f"{known['note']} ({known['table']})"}
    return {"metric": metric, "status": "unknown",
            "note": "not in the coverage registry"}


def warehouse_path() -> Path:
    try:
        from shared import store as _store
        return _store.DB_PATH
    except Exception:
        override = os.environ.get("DIME_WAREHOUSE")
        if override:
            return Path(override)
        return (Path(__file__).resolve().parent.parent.parent
                / "data" / "warehouse.duckdb")


def parse_season_start(value: object) -> int | None:
    parts = str(value or "").strip().split("-")
    if len(parts) != 2:
        return None
    year, tail = parts
    if len(year) != 4 or len(tail) != 2:
        return None
    if not year.isdigit() or not tail.isdigit():
        return None
    start = int(year)
    if int(tail) != (start + 1) % 100:
        return None
    return start


def _freshness(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def coverage_cache_clear() -> None:
    with _state_lock:
        _season_cache.clear()


def _read_table_seasons(path: Path, table: str) -> frozenset[str]:
    import duckdb

    connection = duckdb.connect(str(path), read_only=True)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({table})").fetchall()
        }
        if "_season" not in columns:
            return frozenset()
        rows = connection.execute(
            f"SELECT DISTINCT _season FROM {table}").fetchall()
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return frozenset(row[0] for row in rows if row and row[0])


def table_seasons(table: str) -> frozenset[str]:
    name = str(table or "")
    if re.fullmatch(_TABLE_NAME, name) is None:
        return frozenset()
    try:
        path = warehouse_path()
    except Exception:
        return frozenset()
    fresh = _freshness(path)
    with _state_lock:
        entry = _season_cache.get(name)
        if entry is not None and fresh is not None and entry[0] == fresh:
            return entry[1]
    try:
        seasons = _read_table_seasons(path, name)
    except Exception:
        return frozenset()
    with _state_lock:
        if fresh is not None:
            _season_cache[name] = (fresh, seasons)
    return seasons


def coverage_bounds(
    tables: Iterable[str] | None = None,
) -> tuple[str, str] | None:
    found: set[str] = set()
    for seasons in tables_seasons(tables).values():
        found.update(seasons)
    ranked = [(parse_season_start(season), season) for season in found]
    ranked = [(start, season) for start, season in ranked if start is not None]
    if not ranked:
        return None
    ranked.sort()
    return (ranked[0][1], ranked[-1][1])


def coverage_label(tables: Iterable[str] | None = None) -> str | None:
    bounds = coverage_bounds(tables)
    if bounds is None:
        return None
    low, high = bounds
    if low == high:
        return low
    return f"{low}–{high}"


def tables_seasons(
    tables: Iterable[str] | None = None,
) -> dict[str, frozenset[str]]:
    names = list(tables) if tables is not None else list(KNOWN_TABLES)
    return {name: table_seasons(name) for name in names}


def max_known_season(
    tables: Iterable[str] | None = None,
) -> str | None:
    best_start: int | None = None
    best: str | None = None
    for seasons in tables_seasons(tables).values():
        for season in seasons:
            start = parse_season_start(season)
            if start is None:
                continue
            if best_start is None or start > best_start:
                best_start = start
                best = season
    return best


def season_beyond_upper_bound(
    season: object,
    tables: Iterable[str] | None = None,
) -> bool:
    start = parse_season_start(season)
    if start is None:
        return True
    top = max_known_season(tables)
    if top is None:
        return False
    ceiling = parse_season_start(top)
    if ceiling is None:
        return False
    return start > ceiling + 1


def _available_sorted(seasons: frozenset[str]) -> list[str]:
    known = sorted(
        season for season in seasons
        if parse_season_start(season) is not None)
    return known if known else sorted(seasons)


def coverage_check(
    metric: str, season: str, table: str | None = None,
) -> dict[str, Any]:
    resolved = table or table_for_metric(metric)
    seasons = table_seasons(resolved)
    requested = str(season)
    covered = requested in seasons and not season_beyond_upper_bound(
        requested)
    if covered:
        message = f"Numbers are available for the {requested} season."
        available = _available_sorted(seasons)
    else:
        available = _available_sorted(seasons)
        if available:
            message = (
                f"Numbers for the {requested} season are not available. "
                f"Available seasons: {', '.join(available)}. "
                "Which season should be used instead?"
            )
        else:
            message = (
                f"Numbers for the {requested} season are not available. "
                "No seasons are on hand for that data right now. "
                "Which season should be used instead?"
            )
    return {
        "covered": covered,
        "table": resolved,
        "requested_season": requested,
        "available_seasons": available,
        "message": message,
    }


def metric_coverage(
    metrics: str | list[str],
    player: str = "",
    season: str | None = None,
) -> dict[str, Any]:
    if isinstance(metrics, str):
        metrics = [m.strip() for m in re.split(r"[,;&]|\band\b", metrics)
                 if m.strip()]
    rows = []
    for raw in metrics:
        row = _classify(raw)
        if player:
            row["player"] = player
        if season is not None:
            verdict = coverage_check(raw, season)
            row["covered"] = verdict["covered"]
            row["available_seasons"] = verdict["available_seasons"]
        rows.append(row)
    unavailable = [r["metric"] for r in rows if r["status"] == "unavailable"]
    subject = f" for {player}" if player else ""
    warnings: list[str] = []
    if unavailable:
        joined = " and ".join(unavailable)
        verb = "are" if len(unavailable) > 1 else "is"
        warnings.append(
            f"{joined} {verb} not available in the warehouse{subject}; "
            "Dime never estimates missing proprietary metrics. Available "
            "current impact context includes RAPM-lite, on-off net, PIE, "
            "and true shooting.")
    unknown = [r["metric"] for r in rows if r["status"] == "unknown"]
    for name in unknown:
        warnings.append(f"{name} is not a recognized metric{subject}.")
    available = [r["metric"] for r in rows if r["status"] == "available"]
    parts = []
    if unavailable:
        parts.append(warnings[0])
    if available:
        parts.append(f"Available in the warehouse{subject}: "
                     + ", ".join(available) + ".")
    if not parts:
        parts.append(f"No recognized metrics requested{subject}.")
    meta: dict[str, Any] = {
        "source": "warehouse coverage",
        "coverage": "per-table season sets read from the warehouse; "
                    "unavailable metrics are constants, available metrics "
                    "name their silver table",
        "deterministic_answer": " ".join(parts),
        "warnings": warnings,
    }
    if season:
        meta["season"] = str(season)
    return {"tool": "metric_coverage", "ok": True, "rows": rows, "meta": meta}
