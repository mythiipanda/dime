from typing import Any

from langchain_core.tools import tool

from .common import (
    call_sync,
    finish_dict_list,
    finish_strict_rows,
    sanitize_for_wire,
)
from .errors import enrich_error


def _extract_historical_list(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    leaders = raw_rows.get("leaders")
    if isinstance(leaders, list):
        return [r for r in leaders if isinstance(r, dict)]
    seasons = raw_rows.get("seasons")
    if isinstance(seasons, list):
        out: list[dict[str, Any]] = []
        for s in seasons:
            if isinstance(s, dict):
                out.extend(r for r in s.get("leaders") or [] if isinstance(r, dict))
        return out
    return [raw_rows]


def _historical_leaders_rows(res: dict[str, Any], category: str) -> list[dict[str, Any]]:
    return [
        {
            "player_name": r.get("player_name") or r.get("player"),
            "season": r.get("season") or r.get("season_label"),
            "value": r.get("value"),
            "gp": r.get("gp"),
            "stat": r.get("stat") or category,
        }
        for r in _extract_historical_list(res.get("rows"))
    ]


def _trend_rows(raw_rows: Any, mapping: tuple[tuple[str, str], ...], field: str) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key, label in mapping:
        items = raw_rows.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    rows.append({**item, field: label})
    return rows or [raw_rows]


def _award_results_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [
            {"award": k, **v} if isinstance(v, dict) else {"award": k, "value": v}
            for k, v in raw_rows.items()
        ]
    return []


def _award_race_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [r for r in raw_rows.get("candidates", []) if isinstance(r, dict)]
    return []


def _streak_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, dict):
        raw_list = raw_rows.get("streaks", [])
    elif isinstance(raw_rows, list):
        raw_list = raw_rows
    else:
        raw_list = []
    keys = ("holder", "holder_id", "streak", "start_date", "end_date", "active")
    return [{k: r.get(k) for k in keys} for r in raw_list if isinstance(r, dict)]


def _finder_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    if "a" in raw_rows and "b" in raw_rows and isinstance(raw_rows.get("a"), dict):
        return [
            {"entry": side_key, **raw_rows[side_key]}
            for side_key in ("a", "b")
            if isinstance(raw_rows.get(side_key), dict)
        ]
    return [raw_rows]


def register() -> dict[str, Any]:
    from shared.tools.league import (
        get_finder as _orig_get_finder,
        get_leaderboard_deltas as _orig_get_leaderboard_deltas,
        get_leaders as _orig_get_leaders,
        get_player_ratings as _orig_get_player_ratings,
        get_player_risers as _orig_get_player_risers,
        get_risers as _orig_get_risers,
        get_rookie_leaders as _orig_get_rookie_leaders,
        get_team_compare as _orig_get_team_compare,
        get_team_leaders as _orig_get_team_leaders,
        get_young_player_usage as _orig_get_young_player_usage,
    )
    from shared.tools.streaks import get_streaks as _orig_get_streaks
    from shared.tools.award_results import get_award_results as _orig_get_award_results
    try:
        from shared.tools.awards import get_award_race as _orig_get_award_race
    except ImportError:
        from backend.shared.tools.awards import get_award_race as _orig_get_award_race
    try:
        from shared.tools.history import get_historical_leaders as _orig_get_historical_leaders
    except ImportError:
        from backend.shared.tools.history import get_historical_leaders as _orig_get_historical_leaders

    @tool("get_leaders", description=_orig_get_leaders.description)
    def get_leaders(stat_category: str = "PTS", ranking_direction: str = "desc",
                    min_attempts: int = 0, season: str | None = None) -> dict:
        res = call_sync(_orig_get_leaders, "get_leaders", {
            "stat_category": stat_category, "ranking_direction": ranking_direction,
            "min_attempts": min_attempts, "season": season,
        })
        return finish_dict_list(res, "get_leaders", ["player", "team", "stat_category", "value", "gp"])

    @tool("get_rookie_leaders", description=_orig_get_rookie_leaders.description)
    def get_rookie_leaders(stat: str = "ppg", min_value: float = 0,
                           min_gp: int = 10, limit: int = 15, season: str | None = None) -> dict:
        res = call_sync(_orig_get_rookie_leaders, "get_rookie_leaders", {
            "stat": stat, "min_value": min_value, "min_gp": min_gp, "limit": limit, "season": season,
        })
        return finish_dict_list(res, "get_rookie_leaders", ["player", "team", "age", "gp", "mpg", "ppg", "rpg", "apg"])

    @tool("get_team_leaders", description=_orig_get_team_leaders.description)
    def get_team_leaders(stat_category: str = "AST", season: str | None = None) -> dict:
        res = call_sync(_orig_get_team_leaders, "get_team_leaders", {"stat_category": stat_category, "season": season})
        return finish_dict_list(res, "get_team_leaders", ["rank", "team", "abbrev", "stat", "gp", "per_game"])

    @tool("get_team_compare", description=_orig_get_team_compare.description)
    def get_team_compare(stat_category: str = "PTS", top: int = 3, season: str | None = None) -> dict:
        res = call_sync(_orig_get_team_compare, "get_team_compare", {
            "stat_category": stat_category, "top": top, "season": season,
        })
        return finish_dict_list(res, "get_team_compare", ["rank", "team", "abbrev", "stat", "gp", "per_game", "record"])

    @tool("get_historical_leaders", description=_orig_get_historical_leaders.description)
    def get_historical_leaders(
        category: str = "pts", start_season: int | str | None = 2015,
        end_season: int | str | None = 2026, limit: int | str | None = 10, mode: str = "leaders",
    ) -> dict:
        cols = ["player_name", "season", "value", "gp", "stat"]
        res = call_sync(_orig_get_historical_leaders, "get_historical_leaders", {
            "category": category, "start_season": start_season,
            "end_season": end_season, "limit": limit, "mode": mode,
        })
        return finish_strict_rows(
            res, "get_historical_leaders", cols, "Historical leaders query failed",
            lambda r: _historical_leaders_rows(r, category), fixed_cols=True,
        )

    @tool("get_young_player_usage", description=_orig_get_young_player_usage.description)
    def get_young_player_usage(max_age: int = 22, min_minutes: int = 1000, season: str | None = None) -> dict:
        res = call_sync(_orig_get_young_player_usage, "get_young_player_usage", {
            "max_age": max_age, "min_minutes": min_minutes, "season": season,
        })
        return finish_dict_list(res, "get_young_player_usage", ["RANK", "PLAYER", "TEAM", "AGE", "GP", "MPG", "MINUTES", "USG_PCT"])

    @tool("get_player_ratings", description=_orig_get_player_ratings.description)
    def get_player_ratings(season: str | None = None, metric: str = "offense",
                           limit: int = 10, min_minutes: int = 1000) -> dict:
        res = call_sync(_orig_get_player_ratings, "get_player_ratings", {
            "season": season, "metric": metric, "limit": limit, "min_minutes": min_minutes,
        })
        return finish_dict_list(res, "get_player_ratings", ["PLAYER", "TEAM", "MINUTES", "RATING", "METRIC"])

    @tool("get_player_risers", description=_orig_get_player_risers.description)
    def get_player_risers(season: str | None = None, n: int = 10) -> dict:
        res = call_sync(_orig_get_player_risers, "get_player_risers", {"season": season, "n": n})
        rows = _trend_rows(res.get("rows"), (("risers", "riser"), ("fallers", "faller")), "TREND") if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["PLAYER", "TEAM", "GP", "SEASON_PPG", "PPG_DELTA", "TREND"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_player_risers", res)
        return sanitize_for_wire(res)

    @tool("get_risers", description=_orig_get_risers.description)
    def get_risers(season: str | None = None, weeks: int = 4) -> dict:
        res = call_sync(_orig_get_risers, "get_risers", {"season": season, "weeks": weeks})
        rows = _trend_rows(res.get("rows"), (("risers", "riser"), ("fallers", "faller")), "TREND") if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["TEAM", "LAST10", "LAST10_PCT", "SEASON_PCT", "DELTA", "TREND"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_risers", res)
        return sanitize_for_wire(res)

    @tool("get_leaderboard_deltas", description=_orig_get_leaderboard_deltas.description)
    def get_leaderboard_deltas(season: str | None = None, days: int = 7) -> dict:
        res = call_sync(_orig_get_leaderboard_deltas, "get_leaderboard_deltas", {"season": season, "days": days})
        rows = _trend_rows(res.get("rows"), (("climbers", "climber"), ("fallers", "faller"), ("new_entries", "new")), "trend") if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["player", "team", "rank_base", "rank_now", "rank_change", "pts_change", "trend"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_leaderboard_deltas", res)
        return sanitize_for_wire(res)

    @tool("get_award_results", description=_orig_get_award_results.description)
    def get_award_results(view: str = "winner", award: str = "mvp",
                          season: str | None = None, player: str = "") -> dict:
        args: dict[str, Any] = {"view": view, "award": award, "season": season}
        if player:
            args["player"] = player
        res = call_sync(_orig_get_award_results, "get_award_results", args)
        rows = _award_results_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["player", "award", "season", "rank", "share", "votes"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_award_results", res)
        return sanitize_for_wire(res)

    @tool("get_award_race", description=_orig_get_award_race.description)
    def get_award_race(award: str, season: str | None = None) -> dict:
        res = call_sync(_orig_get_award_race, "get_award_race", {"award": award, "season": season})
        rows = _award_race_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["rank", "player", "team", "score"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_award_race", res)
        return sanitize_for_wire(res)

    @tool("get_streaks", description=_orig_get_streaks.description)
    def get_streaks(stat: str = "points", threshold: float | None = None, scope: str = "player",
                    season: str | None = None, mode: str = "longest", top: int = 10) -> dict:
        cols = ["holder", "streak", "start_date", "end_date", "active"]
        res = call_sync(_orig_get_streaks, "get_streaks", {
            "stat": stat, "threshold": threshold, "scope": scope,
            "season": season, "mode": mode, "top": top,
        })
        return finish_strict_rows(res, "get_streaks", cols, "Streak lookup failed", _streak_rows)

    @tool("get_finder", description=_orig_get_finder.description)
    def get_finder(mode: str = "streak", team_abbrev: str = "", opponent: str = "",
                   season: str | None = None, window: int = 5) -> dict:
        res = call_sync(_orig_get_finder, "get_finder", {
            "mode": mode, "team_abbrev": team_abbrev, "opponent": opponent,
            "season": season, "window": window,
        })
        rows = _finder_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["mode", "team", "opponent", "streak", "games", "result"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_finder", res)
        return sanitize_for_wire(res)

    return {
        "get_leaders": get_leaders,
        "get_rookie_leaders": get_rookie_leaders,
        "get_team_leaders": get_team_leaders,
        "get_team_compare": get_team_compare,
        "get_historical_leaders": get_historical_leaders,
        "get_young_player_usage": get_young_player_usage,
        "get_player_ratings": get_player_ratings,
        "get_player_risers": get_player_risers,
        "get_risers": get_risers,
        "get_leaderboard_deltas": get_leaderboard_deltas,
        "get_award_results": get_award_results,
        "get_award_race": get_award_race,
        "get_streaks": get_streaks,
        "get_finder": get_finder,
    }
