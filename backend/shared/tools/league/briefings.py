from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.tools import tool

from .._core import IN_SEASON_MONTHS as _IN_SEASON_MONTHS, TTL_LEADERS, TTL_SCOREBOARD_PAST
from ._helpers import _pkg

_DAY = 24 * 3600

FRESHNESS_RULES: dict[str, tuple[str, float | None]] = {
    "silver_scoreboard": ("daily in season", 36 * 3600),
    "silver_standings": ("daily in season", 36 * 3600),
    "silver_injuries": ("daily in season", 36 * 3600),
    "silver_leaders_pts": ("daily in season", 36 * 3600),
    "silver_leaders_ast": ("daily in season", 36 * 3600),
    "silver_leaders_reb": ("daily in season", 36 * 3600),
    "silver_leaders_stl": ("daily in season", 36 * 3600),
    "silver_leaders_blk": ("daily in season", 36 * 3600),
    "silver_leaders_dreb": ("daily in season", 36 * 3600),
    "silver_leaders_fg_pct": ("daily in season", 36 * 3600),
    "silver_player_gamelogs": ("daily in season", 36 * 3600),
    "silver_player_season": ("static seed (bbref per-game)", None),
    "silver_zone_splits": ("static seed (bbref shooting)", None),
    "silver_team_games": ("daily in season", 36 * 3600),
    "silver_four_factors_team": ("derived from silver_team_games (offline build)", None),
    "silver_boxscores": ("daily in season", 36 * 3600),
    "silver_boxscores_ext": ("static backfill (extended box scores)", None),
    "silver_shots": ("daily in season", 36 * 3600),
    "silver_playoff_inactive": ("static seed (bbref inactive listings)", None),
    "silver_schedule": ("daily in season", 36 * 3600),
    "silver_hustle_player": ("daily in season", 36 * 3600),
    "silver_hustle_team": ("daily in season", 36 * 3600),
    "silver_advanced": ("daily in season", 36 * 3600),
    "silver_four_factors": ("daily in season", 36 * 3600),
    "silver_clutch": ("daily in season", 36 * 3600),
    "silver_team_ratings": ("daily in season", 36 * 3600),
    "silver_on_off": ("daily in season", 36 * 3600),
    "silver_lineups": ("daily in season", 36 * 3600),
    "silver_wowy": ("daily in season", 36 * 3600),
    "silver_rosters": ("daily in season", 36 * 3600),
    "silver_salaries": ("weekly", 7 * _DAY),
    "silver_cap_players": ("weekly", 7 * _DAY),
    "silver_combine": ("weekly", 7 * _DAY),
    "silver_playoffs": ("seasonal", 400 * _DAY),
    "silver_playoff_gamelogs": ("seasonal", 400 * _DAY),
    "silver_hist_gamelogs": ("static", None),
    "silver_hist_draft": ("static", None),
    "silver_hist_hustle": ("static", None),
    "silver_hist_lineups": ("static", None),
    "silver_hist_possessions": ("static", None),
    "silver_hist_shots": ("static", None),
    "silver_hist_standings": ("static", None),
    "silver_hist_player_seasons": ("static", None),
    "silver_raptor_player": ("static", None),
    "silver_raptor_team": ("static", None),
    "silver_rapm": ("static", None),
    "silver_rapm_prior": ("static", None),
    "silver_hist_pbp": ("static", None),
    "silver_bbref_gamelogs_2024_25": ("static", None),
}


@tool(description='Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest.')
def get_briefing(game_date: str = "", season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    day = game_date.strip()
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    past = pkg.is_past_game_date(day)
    games, gmeta = pkg._warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{day}"],
        lambda: pkg.nba_stats.scoreboard(day, season), season,
        entity=f"date:{day}", live_first=(not past),
        ttl_s=(TTL_SCOREBOARD_PAST if past else None),
    )
    leaders, _ = pkg._warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: pkg.nba_stats.leaders("PTS", season), season,
        ttl_s=TTL_LEADERS,
    )
    top = [
        {"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"), "PTS": r.get("PTS")}
        for r in leaders[:5]
    ]
    return {"tool": "get_briefing", "ok": True,
            "rows": {"date": day, "games": games, "top_scorers": top},
            "meta": gmeta}


def _parse_ts(raw: object):
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _freshness_row(table: str, rows: int, last_fetch: object,
                   now) -> dict[str, Any]:
    label, max_age = FRESHNESS_RULES.get(table, ("unknown", None))
    known = table in FRESHNESS_RULES
    expected, threshold = label, max_age
    if label == "daily in season" and now.month not in _IN_SEASON_MONTHS:
        expected, threshold = "weekly (offseason)", 7 * _DAY
    ts = _parse_ts(last_fetch) if last_fetch else None
    age_hours: float | None = None
    stale: bool | None = None
    if ts is not None:
        age_hours = round((now - ts).total_seconds() / 3600, 1)
        if known:
            stale = threshold is not None and age_hours * 3600 > threshold
    return {"table": table, "rows": rows,
            "last_fetch": str(last_fetch) if ts is not None else "unknown",
            "age_hours": age_hours, "expected": expected, "stale": stale}


def _warehouse_table_meta() -> list[tuple[str, int, str | None]]:
    con = _pkg().store.connect(read_only=True)
    try:
        tables = sorted(
            r[0] for r in con.execute("SHOW TABLES").fetchall()
            if r[0].startswith("silver_"))
        if not tables:
            return []
        has_ts = {}
        for t in tables:
            has_ts[t] = any(
                r[1] == "_fetched_at"
                for r in con.execute(f"PRAGMA table_info({t})").fetchall())
        parts = []
        for t in tables:
            mx = "MAX(_fetched_at)" if has_ts[t] else "CAST(NULL AS VARCHAR)"
            parts.append(f"SELECT '{t}' AS t, COUNT(*) AS n, {mx} AS mx FROM {t}")
        return [(r[0], r[1], r[2]) for r in
                con.execute(" UNION ALL ".join(parts)).fetchall()]
    finally:
        con.close()


@tool(description='Warehouse freshness panel: every silver table, row count, last fetch, stale flag.')
def get_warehouse_freshness() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    try:
        meta = _warehouse_table_meta()
    except Exception as exc:
        return {"tool": "get_warehouse_freshness", "ok": False,
                "error": str(exc)[:200]}
    rows = [_freshness_row(t, n, last, now) for t, n, last in meta]
    stale_n = sum(1 for r in rows if r["stale"])
    unknown_n = sum(1 for r in rows if r["stale"] is None)
    return {"tool": "get_warehouse_freshness", "ok": True, "rows": rows,
            "meta": {"source": "warehouse",
                     "generated_at": now.isoformat(),
                     "tables": len(rows), "stale": stale_n,
                     "unknown": unknown_n,
                     "in_season": now.month in _IN_SEASON_MONTHS}}
