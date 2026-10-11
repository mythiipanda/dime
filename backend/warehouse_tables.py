from __future__ import annotations

import os
import threading
from pathlib import Path

import duckdb
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class WarehouseSeasonRange(BaseModel):
    min: str
    max: str


class WarehouseTable(BaseModel):
    name: str
    row_count: int
    column_count: int
    season_range: WarehouseSeasonRange | None
    source_badge: str
    description: str


router = APIRouter()

SOURCE_BADGES = ("nba_official", "bbref", "derived", "internal", "unknown")

BBREF_PREFIX = "silver_bbref_"

BBREF_NAMES = frozenset({"silver_salaries"})

INTERNAL_NAMES = frozenset({
    "chat_history",
    "fetch_log",
    "leaderboard_snapshots",
    "runs",
    "watchlists",
})

DERIVED_NAMES = frozenset({
    "silver_cap_players",
    "silver_four_factors",
    "silver_four_factors_team",
    "silver_on_off",
    "silver_player_season",
    "silver_raptor_player",
    "silver_raptor_team",
    "silver_rapm",
    "silver_rapm_prior",
    "silver_wowy",
})

SEASON_COLUMNS = ("season", "season_id", "game_date", "year")

DESCRIPTIONS = {
    "chat_history": "Workspace chat turns stored per thread.",
    "fetch_log": "Ingest log of every warehouse fetch by dataset and season.",
    "leaderboard_snapshots": "Daily scoring-leader snapshots used for mover tracking.",
    "runs": "Saved analysis runs backing thread history.",
    "silver_advanced": "Advanced splits from the NBA stats feed across recent seasons.",
    "silver_bbref_awards": "Basketball-Reference award voting back to 1976-77.",
    "silver_bbref_gamelogs_2024_25": "Basketball-Reference player game logs for 2024-25.",
    "silver_boxscores": "Official box scores cached per game for 2025-26.",
    "silver_cap_players": "Salary-cap table with salaries, options and guarantees.",
    "silver_clutch": "Clutch-time splits from the NBA stats feed.",
    "silver_combine": "Draft combine measurements for recent classes.",
    "silver_four_factors": "Cached four-factors result for the last queried matchup.",
    "silver_four_factors_team": "Team four-factors ratings for 2025-26.",
    "silver_hist_draft": "Draft picks back to 1997.",
    "silver_hist_gamelogs": "Team game logs back to 2009.",
    "silver_hist_hustle": "Hustle stats archive across seasons.",
    "silver_hist_lineups": "Historical lineup stints, the second-largest table.",
    "silver_hist_pbp": "Play-by-play archive with 3.2M recorded actions.",
    "silver_hist_player_seasons": "Player season totals archive.",
    "silver_hist_possessions": "Possession-level archive, the largest table.",
    "silver_hist_shots": "Shot-by-shot archive since 2010, the real shooting corpus.",
    "silver_hist_standings": "Historical standings records back to 2009-10.",
    "silver_hustle_player": "Player hustle stats for the current window.",
    "silver_hustle_team": "Team hustle stats for the current window.",
    "silver_injuries": "Current injury report sourced from ESPN.",
    "silver_leaders_ast": "Season assist-leaders cache.",
    "silver_leaders_blk": "Season blocks-leaders cache.",
    "silver_leaders_dreb": "Season defensive-rebounds-leaders cache.",
    "silver_leaders_fg_pct": "Season field-goal-percentage-leaders cache.",
    "silver_leaders_pts": "Season scoring-leaders cache.",
    "silver_leaders_reb": "Season rebounds-leaders cache.",
    "silver_leaders_stl": "Season steals-leaders cache.",
    "silver_lineups": "Lineup stints cached per team for 2025-26.",
    "silver_on_off": "Cached on/off results for recently queried players.",
    "silver_player_gamelogs": "Player game logs cached per player.",
    "silver_player_season": "Union of player season rows across sources.",
    "silver_playoff_gamelogs": "Playoff player game logs.",
    "silver_playoffs": "Playoff results for recent postseasons.",
    "silver_rapm": "Regularized adjusted plus-minus estimates.",
    "silver_rapm_prior": "Prior-season inputs behind the RAPM estimates.",
    "silver_raptor_player": "FiveThirtyEight RAPTOR ratings, ending in 2022.",
    "silver_raptor_team": "FiveThirtyEight team RAPTOR ratings, ending in 2022.",
    "silver_rosters": "Coaching staffs by team and season.",
    "silver_salaries": "Player salaries from Basketball-Reference contracts.",
    "silver_schedule": "ESPN team schedules for 2025-26.",
    "silver_scoreboard": "Scoreboard snapshots cached per date.",
    "silver_shots": "Shot charts cached per recently queried player.",
    "silver_standings": "Official standings snapshots.",
    "silver_team_games": "Team game logs cached per team.",
    "silver_team_ratings": "Offensive and defensive ratings snapshot.",
    "silver_wowy": "Cached with-or-without-you result for the last query.",
    "watchlists": "Workspace watchlist entries.",
}

_lock = threading.Lock()

_snapshot = {"path": "", "key": None, "tables": []}


def _default_warehouse_path() -> Path:
    try:
        from shared.store import DB_PATH as configured_default
        return Path(configured_default)
    except Exception:
        return Path(__file__).resolve().parent / "data" / "warehouse.duckdb"


def warehouse_path() -> Path:
    configured = os.environ.get("DIME_WAREHOUSE", "").strip()
    if configured:
        return Path(configured)
    return _default_warehouse_path()


def _badge_for_evidence(value: str) -> str:
    s = (value or "").strip().lower()
    if not s:
        return "unknown"
    if "basketball-reference" in s or s.startswith("bref") or "bref_" in s:
        return "bbref"
    if s == "nba_api" or s.startswith("sportsdataverse"):
        return "nba_official"
    if s in ("pbpstats", "warehouse-union", "rapm-lite", "rapm-prior") or s.startswith("rapm") or "fivethirtyeight" in s or "raptor" in s or "orojas" in s or "salary-cap" in s:
        return "derived"
    return "unknown"


def source_badge_for(name: str, sources: list[str] | None = None) -> str:
    if name in INTERNAL_NAMES:
        return "internal"
    if sources is not None:
        cleaned = sorted({(s or "").strip() for s in sources if (s or "").strip()})
        if not cleaned:
            return "unknown"
        badges = {_badge_for_evidence(s) for s in cleaned}
        if len(badges) == 1:
            return next(iter(badges))
        return "unknown"
    if name in BBREF_NAMES or name.startswith(BBREF_PREFIX):
        return "bbref"
    if name in DERIVED_NAMES:
        return "derived"
    return "unknown"


def season_column_for(columns: list[str]) -> str | None:
    normalized: dict[str, str] = {}
    for column in columns:
        key = column.lower().strip("_")
        if key not in normalized:
            normalized[key] = column
    for candidate in SEASON_COLUMNS:
        if candidate in normalized:
            return normalized[candidate]
    return None


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def describe_table(con: object, name: str) -> dict:
    quoted = quote_identifier(name)
    row_count = con.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
    columns = [row[1] for row in con.execute(f"PRAGMA table_info({quoted})").fetchall()]
    season_range = None
    column = season_column_for(columns)
    if column is not None and row_count > 0 and name not in INTERNAL_NAMES:
        bounds = con.execute(
            f"SELECT MIN({quote_identifier(column)}), MAX({quote_identifier(column)}) FROM {quoted}"
        ).fetchone()
        if bounds[0] is not None and bounds[1] is not None:
            season_range = {"min": str(bounds[0]), "max": str(bounds[1])}
    sources: list[str] = []
    if "_source" in columns and row_count > 0:
        try:
            sources = [row[0] for row in con.execute(f"SELECT DISTINCT _source FROM {quoted}").fetchall()]
        except Exception:
            sources = []
    return {
        "name": name,
        "row_count": int(row_count),
        "column_count": len(columns),
        "season_range": season_range,
        "source_badge": source_badge_for(name, sources),
        "description": DESCRIPTIONS.get(name, ""),
    }


def _stat_key(path: Path):
    st = path.stat()
    size = st.st_size
    mtime = st.st_mtime_ns
    ctime = getattr(st, "st_ctime_ns", None)
    token = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        try:
            try:
                from shared.change_token import change_token as _change_token
                token = _change_token(fd)
            except Exception:
                token = None
        finally:
            os.close(fd)
    except OSError:
        token = None
    return (mtime, size, ctime, token)


def load_snapshot(path: Path) -> list:
    try:
        freshness = _stat_key(path)
    except OSError:
        raise HTTPException(status_code=503, detail="warehouse unavailable")
    with _lock:
        if (
            _snapshot["tables"]
            and _snapshot["path"] == str(path)
            and _snapshot["key"] == freshness
        ):
            return _snapshot["tables"]
    try:
        con = duckdb.connect(str(path), read_only=True)
    except Exception:
        raise HTTPException(status_code=503, detail="warehouse unavailable")
    try:
        names = sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
        tables = [describe_table(con, name) for name in names]
    finally:
        try:
            con.close()
        except Exception:
            pass
    with _lock:
        _snapshot["path"] = str(path)
        _snapshot["key"] = freshness
        _snapshot["tables"] = tables
    return tables


def snapshot_clear() -> None:
    with _lock:
        _snapshot["path"] = ""
        _snapshot["key"] = None
        _snapshot["tables"] = []


@router.get("/v2/warehouse/tables", response_model=list[WarehouseTable])
def warehouse_tables() -> list:
    return load_snapshot(warehouse_path())
