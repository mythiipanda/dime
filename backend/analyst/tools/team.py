from typing import Any

from langchain_core.tools import tool
from shared.lineup_variants import SeasonType, MeasureType, PerMode

from .common import (
    _flatten_sections,
    _row_list_result,
    _section_object_result,
    call_sync,
    finish_dict_list,
    finish_strict_rows,
    sanitize_for_wire,
)
from .errors import enrich_error


def _rest_rows(raw_rows: Any, team_abbrev: str) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    team = team_abbrev.upper() if team_abbrev else ""
    buckets = raw_rows.get("rest_buckets")
    if isinstance(buckets, dict):
        return [
            {
                "team": team,
                "rest_days": bucket_name,
                "games": b_val.get("games", 0),
                "wins": b_val.get("wins", 0),
                "losses": b_val.get("losses", 0),
                "win_pct": b_val.get("win_pct"),
            }
            for bucket_name, b_val in buckets.items()
            if isinstance(b_val, dict)
        ]
    return [
        {"team": team, "rest_days": k, **v}
        for k, v in raw_rows.items()
        if isinstance(v, dict)
    ]


def _rest_advantage_rows(res: dict[str, Any], team: str) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    fields = ("date", "opponent", "home", "result", "pts_for", "pts_against",
              "rest_days", "opp_rest_days", "rest_diff")
    if isinstance(raw_rows, dict):
        t_name = raw_rows.get("team") or team
        return [
            {"team": t_name, **{k: g.get(k) for k in fields}}
            for g in raw_rows.get("games") or []
            if isinstance(g, dict)
        ]
    if isinstance(raw_rows, list):
        return [
            {"team": item.get("team") or team, **{k: item.get(k) for k in fields}}
            for item in raw_rows
            if isinstance(item, dict)
        ]
    return []


def _extract_game_list(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        for key in ("games", "rows"):
            if isinstance(raw_rows.get(key), list):
                return [r for r in raw_rows[key] if isinstance(r, dict)]
        return [raw_rows]
    if isinstance(res.get("games"), list):
        return [r for r in res["games"] if isinstance(r, dict)]
    return []


def _season_series_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    cols = ("game_id", "date", "matchup", "phase", "winner")
    return [{k: r.get(k) for k in cols} for r in _extract_game_list(res)]


def _team_game_log_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    pairs = (
        ("game_id", "Game_ID"), ("date", "GAME_DATE"), ("matchup", "MATCHUP"),
        ("wl", "WL"), ("pts", "PTS"), ("opp_pts", "OPP_PTS"),
        ("reb", "REB"), ("ast", "AST"), ("stl", "STL"), ("blk", "BLK"), ("tov", "TOV"),
    )
    return [
        {dst: r.get(dst) if r.get(dst) is not None else r.get(alt) for dst, alt in pairs}
        for r in _extract_game_list(res)
    ]


def _pick_rows(res: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list = [r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else []
    return [{k: r.get(k) for k in keys} for r in raw_list]


def _possession_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    return _pick_rows(res, (
        "possession_number", "period", "clock_in", "clock_out", "off_abbr", "def_abbr",
        "points", "wpa_delta", "score_home_in", "score_away_in", "score_home_out", "score_away_out",
    ))


def _stint_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    return _pick_rows(res, (
        "stint_number", "poss_start", "poss_end", "period_in", "clock_in",
        "period_out", "clock_out", "duration_sec", "home_abbr", "away_abbr",
        "score_home_in", "score_away_in", "score_home_out", "score_away_out", "home_swing",
    ))


def register() -> dict[str, Any]:
    from shared.tools.league import (
        get_lineup_leaders as _orig_get_lineup_leaders,
        get_rest as _orig_get_rest,
        get_team_four_factors as _orig_get_team_four_factors,
        get_team_trajectory as _orig_get_team_trajectory,
    )
    from shared.tools.lineup import get_lineup_stats as _orig_get_lineup_stats
    try:
        from shared.tools.rest import get_rest_advantage as _orig_get_rest_advantage
    except ImportError:
        from backend.shared.tools.rest import get_rest_advantage as _orig_get_rest_advantage
    try:
        from shared.tools.stints import get_stint_timeline as _orig_get_stint_timeline
    except ImportError:
        from backend.shared.tools.stints import get_stint_timeline as _orig_get_stint_timeline
    try:
        from shared.tools.possessions import get_possession_log as _orig_get_possession_log
    except ImportError:
        from backend.shared.tools.possessions import get_possession_log as _orig_get_possession_log
    try:
        from shared.tools.team import (
            get_lineups as _orig_get_lineups,
            get_scouting_report as _orig_get_scouting_report,
            get_season_series as _orig_get_season_series,
            get_team_game_log as _orig_get_team_game_log,
            get_team_hub as _orig_get_team_hub,
        )
    except ImportError:
        from backend.shared.tools.team import (
            get_lineups as _orig_get_lineups,
            get_scouting_report as _orig_get_scouting_report,
            get_season_series as _orig_get_season_series,
            get_team_game_log as _orig_get_team_game_log,
            get_team_hub as _orig_get_team_hub,
        )

    @tool("get_four_factors", description=_orig_get_team_four_factors.description)
    def get_four_factors(team: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_team_four_factors, "get_four_factors", {"team": team, "season": season})
        default_cols = [
            "team", "season", "efg_pct", "tov_pct", "orb_pct", "ft_rate",
            "def_efg_pct", "def_tov_pct", "def_orb_pct", "def_ft_rate",
        ]
        return finish_dict_list(res, "get_four_factors", default_cols)

    @tool("get_team_four_factors", description=_orig_get_team_four_factors.description)
    def get_team_four_factors(team: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_team_four_factors, "get_team_four_factors", {"team": team, "season": season})
        default_cols = [
            "TEAM", "GP", "W", "EFG_PCT", "TOV_PCT", "ORB_PCT", "FT_RATE",
            "OPP_EFG_PCT", "OPP_TOV_PCT", "DRB_PCT", "OPP_FT_RATE",
        ]
        return finish_dict_list(res, "get_team_four_factors", default_cols)

    @tool("get_lineup_stats", description=_orig_get_lineup_stats.description)
    def get_lineup_stats(team: str | int, season: str | None = None,
                         min_possessions: int = 100, include_small: bool = False,
                         limit: int = 10) -> dict:
        res = call_sync(_orig_get_lineup_stats, "get_lineup_stats", {
            "team": team, "season": season, "min_possessions": min_possessions,
            "include_small": include_small, "limit": limit,
        })
        rows = res.get("rows") if res.get("ok") and isinstance(res.get("rows"), list) else []
        default_cols = ["GROUP_NAME", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING", "POSS"]
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_lineup_stats", res)
        return res

    @tool("get_lineup_leaders", description=_orig_get_lineup_leaders.description)
    def get_lineup_leaders(min_minutes: int = 100, limit: int = 10, season: str | None = None, playoffs: bool = False) -> dict:
        args = {"min_minutes": min_minutes, "limit": limit, "season": season}
        if playoffs:
            args['playoffs'] = playoffs
        res = call_sync(_orig_get_lineup_leaders, "get_lineup_leaders", args)
        return finish_dict_list(res, "get_lineup_leaders", ["team_abbreviation", "group_name", "gp", "min", "plus_minus", "net48"])

    @tool("get_rest", description=_orig_get_rest.description)
    def get_rest(team_abbrev: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_rest, "get_rest", {"team_abbrev": team_abbrev, "season": season})
        default_cols = ["team", "rest_days", "games", "wins", "losses", "win_pct"]
        rows = _rest_rows(res.get("rows"), team_abbrev) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_rest", res)
        return sanitize_for_wire(res)

    @tool("get_rest_advantage", description=_orig_get_rest_advantage.description)
    def get_rest_advantage(
        team: str = "league", season: str = "2025-26", season_type: str = "all",
        date: str = "", opponent: str = "",
    ) -> dict:
        cols = ["date", "team", "opponent", "home", "result", "pts_for", "pts_against", "rest_days", "opp_rest_days", "rest_diff"]
        res = call_sync(_orig_get_rest_advantage, "get_rest_advantage", {
            "team": team, "season": season, "season_type": season_type, "date": date, "opponent": opponent,
        })
        return finish_strict_rows(
            res, "get_rest_advantage", cols, "Rest advantage lookup failed",
            lambda r: _rest_advantage_rows(r, team), fixed_cols=True,
        )

    @tool("get_team_trajectory", description=_orig_get_team_trajectory.description)
    def get_team_trajectory(team: str = "", through_season: str | None = None, seasons_back: int = 5) -> dict:
        res = call_sync(_orig_get_team_trajectory, "get_team_trajectory", {
            "team": team, "through_season": through_season, "seasons": seasons_back,
        })
        return finish_dict_list(res, "get_team_trajectory", ["season", "team", "wins", "losses", "win_pct"])

    @tool("get_team_hub", description=_orig_get_team_hub.description)
    def get_team_hub(team_id: str | int, season: str | None = None) -> dict:
        default_cols = ["section", "PLAYER", "TEAM", "AGE", "GP", "PPG", "RPG", "APG"]
        res = call_sync(_orig_get_team_hub, "get_team_hub", {"team_id": team_id, "season": season})
        return _flatten_sections(res, default_cols, name="get_team_hub")

    @tool("get_lineups", description=_orig_get_lineups.description)
    def get_lineups(team_id: str | int, season: str | None = None, season_type: SeasonType = 'regular-season', measure_type: MeasureType = 'base', per_mode: PerMode = 'totals') -> dict:
        default_cols = ["GROUP_NAME", "MIN", "PLUS_MINUS", "SAMPLE_TIER", "EST_POSS", "competitive_net", "competitive_poss"]
        args = {"team_id": team_id, "season": season}
        for key, value, default in [('season_type', season_type, 'regular-season'),
                                    ('measure_type', measure_type, 'base'), ('per_mode', per_mode, 'totals')]:
            if value != default:
                args[key] = value
        res = call_sync(_orig_get_lineups, "get_lineups", args)
        result = _row_list_result(res, "get_lineups", default_cols)
        if measure_type != 'base' and result['rows']:
            result['columns'] = list(dict.fromkeys(key for row in result['rows'] for key in row))
        return result

    @tool("get_team_game_log", description=_orig_get_team_game_log.description)
    def get_team_game_log(team: str, limit: int = 10, playoffs: bool = False, season: str | None = None) -> dict:
        cols = ["game_id", "date", "matchup", "wl", "pts", "opp_pts", "reb", "ast", "stl", "blk", "tov"]
        res = call_sync(_orig_get_team_game_log, "get_team_game_log", {
            "team": team, "limit": limit, "playoffs": playoffs, "season": season,
        })
        return finish_strict_rows(res, "get_team_game_log", cols, "Team game log lookup failed",
                                  _team_game_log_rows, fixed_cols=True)

    @tool("get_season_series", description=_orig_get_season_series.description)
    def get_season_series(team_a: str, team_b: str, season: str | None = None) -> dict:
        cols = ["game_id", "date", "matchup", "phase", "winner"]
        res = call_sync(_orig_get_season_series, "get_season_series", {
            "team_a": team_a, "team_b": team_b, "season": season,
        })
        return finish_strict_rows(res, "get_season_series", cols, "Season series lookup failed",
                                  _season_series_rows, fixed_cols=True)

    @tool("get_possession_log", description=_orig_get_possession_log.description)
    def get_possession_log(game_id: str = "", period: int | None = None, clock_range: str | None = None) -> dict:
        cols = [
            "possession_number", "period", "clock_in", "clock_out", "off_abbr", "def_abbr",
            "points", "wpa_delta", "score_home_in", "score_away_in", "score_home_out", "score_away_out",
        ]
        res = call_sync(_orig_get_possession_log, "get_possession_log", {
            "game_id": game_id, "period": period, "clock_range": clock_range,
        })
        return finish_strict_rows(res, "get_possession_log", cols, "Possession log lookup failed",
                                  _possession_rows, fixed_cols=True)

    @tool("get_stint_timeline", description=_orig_get_stint_timeline.description)
    def get_stint_timeline(game_id: str = "") -> dict:
        cols = [
            "stint_number", "poss_start", "poss_end", "period_in", "clock_in",
            "period_out", "clock_out", "duration_sec", "home_abbr", "away_abbr",
            "score_home_in", "score_away_in", "score_home_out", "score_away_out", "home_swing",
        ]
        res = call_sync(_orig_get_stint_timeline, "get_stint_timeline", {"game_id": game_id})
        return finish_strict_rows(res, "get_stint_timeline", cols, "Stint timeline lookup failed",
                                  _stint_rows, fixed_cols=True)

    @tool("get_scouting_report", description=_orig_get_scouting_report.description)
    def get_scouting_report(team_id: str | int, season: str | None = None) -> dict:
        default_cols = ["section", "value", "GROUP_NAME", "MIN", "PLUS_MINUS"]
        res = call_sync(_orig_get_scouting_report, "get_scouting_report", {"team_id": team_id, "season": season})
        return _section_object_result(res, "get_scouting_report", default_cols)

    return {
        "get_four_factors": get_four_factors,
        "get_team_four_factors": get_team_four_factors,
        "get_lineup_stats": get_lineup_stats,
        "get_lineup_leaders": get_lineup_leaders,
        "get_rest": get_rest,
        "get_rest_advantage": get_rest_advantage,
        "get_team_trajectory": get_team_trajectory,
        "get_team_hub": get_team_hub,
        "get_lineups": get_lineups,
        "get_team_game_log": get_team_game_log,
        "get_season_series": get_season_series,
        "get_possession_log": get_possession_log,
        "get_stint_timeline": get_stint_timeline,
        "get_scouting_report": get_scouting_report,
    }
