from typing import Any

from langchain_core.tools import tool
from shared.lineup_variants import SeasonType

from .common import (
    _flatten_sections,
    _row_list_result,
    call_sync,
    finish_dict_list,
    finish_strict_rows,
    sanitize_for_wire,
)
from .errors import enrich_error


def _clutch_filter(rows: list[dict[str, Any]], team: str, scope: str, min_games: int) -> list[dict[str, Any]]:
    if team and scope == "team":
        abbr = team.upper()
        filtered = [r for r in rows if r.get("TEAM_ABBREVIATION") == abbr or r.get("team") == abbr]
        if filtered:
            rows = filtered
    if min_games:
        rows = [r for r in rows if (r.get("GP") or 0) >= min_games]
    return rows


def _situational_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, dict) and isinstance(raw_rows.get("splits"), list):
        return [r for r in raw_rows["splits"] if isinstance(r, dict)]
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    return []


def _playtype_rows(res: dict[str, Any], subject: str) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, dict):
        raw_list = raw_rows.get("play_types", [])
        subj = raw_rows.get("subject", subject)
        return [
            {
                "subject": subj, "play_type": pt.get("play_type"),
                "poss_pct": pt.get("poss_pct"), "ppp": pt.get("ppp"),
                "percentile": pt.get("percentile"), "gp": pt.get("gp"), "poss": pt.get("poss"),
            }
            for pt in raw_list if isinstance(pt, dict)
        ]
    if isinstance(raw_rows, list):
        return [
            {
                "subject": pt.get("subject", subject), "play_type": pt.get("play_type"),
                "poss_pct": pt.get("poss_pct"), "ppp": pt.get("ppp"),
                "percentile": pt.get("percentile"), "gp": pt.get("gp"), "poss": pt.get("poss"),
            }
            for pt in raw_rows if isinstance(pt, dict)
        ]
    return []


def _wowy_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        raw_list = [r for r in raw_rows if isinstance(r, dict)]
    elif isinstance(raw_rows, dict):
        nested = raw_rows.get("rows")
        raw_list = [r for r in nested if isinstance(r, dict)] if isinstance(nested, list) else [raw_rows]
    return [
        {
            "lineup_state": r.get("lineup_state") if r.get("lineup_state") is not None else r.get("split"),
            "minutes": r.get("minutes"),
            "off_rating": r.get("off_rating"),
            "def_rating": r.get("def_rating"),
            "net_rating": r.get("net_rating"),
            "poss": r.get("poss") if r.get("poss") is not None else r.get("possessions"),
        }
        for r in raw_list
    ]


def _raptor_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        raw_list = [r for r in raw_rows if isinstance(r, dict)]
    elif isinstance(raw_rows, dict):
        nested = raw_rows.get("rows")
        raw_list = [r for r in nested if isinstance(r, dict)] if isinstance(nested, list) else [raw_rows]
    return [
        {
            "SEASON": r.get("SEASON") if r.get("SEASON") is not None else r.get("_season"),
            "TEAM": r.get("TEAM"),
            "MP": r.get("MP"),
            "RAPTOR_O": r.get("RAPTOR_O") if r.get("RAPTOR_O") is not None else r.get("RAPTOR_OFFENSE"),
            "RAPTOR_D": r.get("RAPTOR_D") if r.get("RAPTOR_D") is not None else r.get("RAPTOR_DEFENSE"),
            "RAPTOR": r.get("RAPTOR") if r.get("RAPTOR") is not None else r.get("RAPTOR_TOTAL"),
            "WAR": r.get("WAR") if r.get("WAR") is not None else r.get("WAR_TOTAL"),
        }
        for r in raw_list
    ]


def _tracking_rows(res: dict[str, Any], excluded: set[str], player: str, team: str,
                   season: str, measure_type: str) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list = [r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else []
    rows: list[dict[str, Any]] = []
    for r in raw_list:
        subject = r.get("PLAYER_NAME") or r.get("TEAM_ABBREVIATION") or player or team
        row_measure_type = r.get("measure_type") or measure_type
        for column, value in r.items():
            if column in excluded:
                continue
            rows.append({
                "subject": subject,
                "season": season,
                "measure_type": row_measure_type,
                "stat": column,
                "value": value,
            })
    return rows


def _rapm_prior_rows(res: dict[str, Any], player: str) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows: list[dict[str, Any]] = []
    p_name = raw_rows.get("player") or player
    est = raw_rows.get("estimate")
    cur = raw_rows.get("current")
    if isinstance(cur, dict):
        rows.append({
            "player": cur.get("name") or p_name, "season": cur.get("season"),
            "rapm": cur.get("rapm"), "possessions": cur.get("possessions"),
            "kind": "current", "estimate": est,
        })
    for pri in raw_rows.get("priors") or []:
        if isinstance(pri, dict):
            rows.append({
                "player": pri.get("name") or p_name, "season": pri.get("season"),
                "rapm": pri.get("rapm"), "possessions": pri.get("possessions"),
                "kind": "prior", "estimate": est,
            })
    return rows


def _gamelog_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    leader_mode = "matches" not in raw_rows
    fields = ("date", "game_id", "opponent", "matchup", "home",
              "pts", "reb", "ast", "stl", "blk", "tov", "min", "wl")
    rows: list[dict[str, Any]] = []
    for m in raw_rows.get("matches") or raw_rows.get("leaders") or []:
        if isinstance(m, dict):
            rows.append(m if leader_mode else {k: m.get(k) for k in fields})
    return rows


def _dict_or_list_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [raw_rows]
    return []


def register() -> dict[str, Any]:
    try:
        from shared.tools.rapm import get_rapm as _orig_get_rapm
    except ImportError:
        from shared.tools.league import get_rapm as _orig_get_rapm
    try:
        from shared.tools.league import get_clutch_stats as _orig_get_clutch_stats
    except ImportError:
        from shared.tools.league import get_clutch as _orig_get_clutch_stats
    from shared.tools.league import get_situational_splits as _orig_get_situational_splits
    from shared.tools.playtypes import get_playtype_profile as _orig_get_playtype_profile
    from shared.tools.tracking import get_defensive_matchups as _orig_get_defensive_matchups
    from shared.tools.player import get_comps as _orig_get_comps, get_on_off as _orig_get_on_off
    try:
        from shared.tools.player import get_era_comps as _orig_get_era_comps
    except ImportError:
        from backend.shared.tools.player import get_era_comps as _orig_get_era_comps
    try:
        from shared.tools.player import get_availability_impact as _orig_get_availability_impact
    except ImportError:
        from backend.shared.tools.player import get_availability_impact as _orig_get_availability_impact
    try:
        from shared.tools.player import (
            get_last_x as _orig_get_last_x,
            get_player_report as _orig_get_player_report,
            get_raptor_history as _orig_get_raptor_history,
            get_splits as _orig_get_splits,
            get_wowy as _orig_get_wowy,
        )
    except ImportError:
        from backend.shared.tools.player import (
            get_last_x as _orig_get_last_x,
            get_player_report as _orig_get_player_report,
            get_raptor_history as _orig_get_raptor_history,
            get_splits as _orig_get_splits,
            get_wowy as _orig_get_wowy,
        )
    try:
        from shared.tools.tracking import (
            _PLAYER_IDENTITY as _TRACKING_PLAYER_IDENTITY,
            _TEAM_IDENTITY as _TRACKING_TEAM_IDENTITY,
            get_tracking_profile as _orig_get_tracking_profile,
        )
    except ImportError:
        from backend.shared.tools.tracking import (
            _PLAYER_IDENTITY as _TRACKING_PLAYER_IDENTITY,
            _TEAM_IDENTITY as _TRACKING_TEAM_IDENTITY,
            get_tracking_profile as _orig_get_tracking_profile,
        )
    try:
        from shared.tools.priors import get_rapm_prior as _orig_get_rapm_prior
    except ImportError:
        from backend.shared.tools.priors import get_rapm_prior as _orig_get_rapm_prior
    try:
        from shared.tools.league import get_impact_rank as _orig_get_impact_rank
    except ImportError:
        from backend.shared.tools.league import get_impact_rank as _orig_get_impact_rank
    try:
        from shared.tools.gamelog import search_game_logs as _orig_search_game_logs
    except ImportError:
        from backend.shared.tools.gamelog import search_game_logs as _orig_search_game_logs

    tracking_excluded = set(_TRACKING_PLAYER_IDENTITY) | set(_TRACKING_TEAM_IDENTITY) | {"measure_type"}

    @tool("get_rapm", description=_orig_get_rapm.description)
    def get_rapm(player: str = "", top: int = 10, season: str | None = None) -> dict:
        res = call_sync(_orig_get_rapm, "get_rapm", {"player": player, "top": top, "season": season})
        rows = res.get("rows") if res.get("ok") and isinstance(res.get("rows"), list) else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["player_id", "name", "rapm", "possessions"]
        if not res.get("ok"):
            enrich_error("get_rapm", res)
        return res


    @tool("get_era_comps", description=_orig_get_era_comps.description)
    def get_era_comps(player_id: str | int, season: str | None = None, k: int = 5,
                      start_season: str | None = None, end_season: str | None = None) -> dict:
        res = call_sync(_orig_get_era_comps, "get_era_comps", {
            "player_id": player_id, "season": season, "k": k,
            "start_season": start_season, "end_season": end_season})
        rows = res.get("rows") if res.get("ok") and isinstance(res.get("rows"), list) else []
        default_cols = ["PLAYER", "PLAYER_ID", "TEAM", "season", "age", "similarity", "archetype", "shared_archetype", "drivers"]
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_era_comps", res)
        return res

    @tool("get_comps", description=_orig_get_comps.description)
    def get_comps(player_id: str | int, season: str | None = None, k: int = 5) -> dict:
        res = call_sync(_orig_get_comps, "get_comps", {"player_id": player_id, "season": season, "k": k})
        rows = res.get("rows") if res.get("ok") and isinstance(res.get("rows"), list) else []
        default_cols = ["PLAYER", "PLAYER_ID", "TEAM", "season", "era", "similarity", "archetype", "shared_archetype", "drivers"]
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_comps", res)
        return res

    @tool("get_on_off", description=_orig_get_on_off.description)
    def get_on_off(player_id: str | int, team_id: str | int, season: str | None = None) -> dict:
        res = call_sync(_orig_get_on_off, "get_on_off", {"player_id": player_id, "team_id": team_id, "season": season})
        raw_rows = res.get("rows")
        rows = [r if isinstance(r, dict) else {"value": r} for r in raw_rows] if res.get("ok") and isinstance(raw_rows, list) else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["Stat", "On", "Off", "On-Off"]
        if not res.get("ok"):
            enrich_error("get_on_off", res)
        return sanitize_for_wire(res)

    @tool("get_availability_impact", description=_orig_get_availability_impact.description)
    def get_availability_impact(player: str = "", season: str | None = None,
                                teammate: str = "", min_minutes: float = 28.0,
                                min_missed: int = 15, limit: int = 5) -> dict:
        res = call_sync(_orig_get_availability_impact, "get_availability_impact", {
            "player": player, "season": season, "teammate": teammate,
            "min_minutes": min_minutes, "min_missed": min_missed, "limit": limit,
        })
        raw_rows = res.get("rows")
        rows = [r if isinstance(r, dict) else {"value": r} for r in raw_rows] if res.get("ok") and isinstance(raw_rows, list) else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["split", "games", "wins", "losses", "win_pct", "avg_margin"]
        if not res.get("ok"):
            enrich_error("get_availability_impact", res)
        return sanitize_for_wire(res)

    @tool("get_clutch_stats", description=_orig_get_clutch_stats.description)
    def get_clutch_stats(player: str = "", team: str = "", season: str | None = None, min_games: int = 5) -> dict:
        scope = "team" if (team and not player) else "player"
        args: dict[str, Any] = {"scope": scope, "season": season}
        if player:
            args["player"] = player
        res = call_sync(_orig_get_clutch_stats, "get_clutch_stats", args)
        return finish_dict_list(
            res, "get_clutch_stats", ["player", "team", "season", "pts", "reb", "ast", "fg_pct", "min"],
            set_ok=False, row_filter=lambda rows: _clutch_filter(rows, team, scope, min_games),
        )

    @tool("get_situational_splits", description=_orig_get_situational_splits.description)
    def get_situational_splits(scope: str = "player", entity: str = "", season: str | None = None,
                               clutch_seconds: int = 300, clutch_margin: int = 5,
                               season_type: str = "regular") -> dict:
        res = call_sync(_orig_get_situational_splits, "get_situational_splits", {
            "scope": scope, "entity": entity, "season": season,
            "clutch_seconds": clutch_seconds, "clutch_margin": clutch_margin, "season_type": season_type,
        })
        cols = ["split", "gp", "pts", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct"]
        rows = _situational_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else cols
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_situational_splits", res)
        return sanitize_for_wire(res)

    @tool("get_playtype_profile", description=_orig_get_playtype_profile.description)
    def get_playtype_profile(subject: str, kind: str = "player", side: str = "offense", season: str | None = None) -> dict:
        cols = ["play_type", "poss_pct", "ppp", "percentile", "gp", "poss"]
        res = call_sync(_orig_get_playtype_profile, "get_playtype_profile", {
            "subject": subject, "kind": kind, "side": side, "season": season,
        })
        return finish_strict_rows(res, "get_playtype_profile", cols, "Playtype profile lookup failed",
                                  lambda r: _playtype_rows(r, subject))

    @tool("get_defensive_matchups", description=_orig_get_defensive_matchups.description)
    def get_defensive_matchups(player: str = "", season: str = "2025-26") -> dict:
        cols = ["PLAYER_NAME", "GP", "FREQ", "D_FGM", "D_FGA", "D_FG_PCT", "NORMAL_FG_PCT", "PCT_PLUSMINUS"]
        res = call_sync(_orig_get_defensive_matchups, "get_defensive_matchups", {"player": player, "season": season})
        return finish_strict_rows(res, "get_defensive_matchups", cols, "Defensive matchups lookup failed",
                                  _dict_or_list_rows)

    @tool("get_wowy", description=_orig_get_wowy.description)
    def get_wowy(player_a: str = "", player_b: str = "", player_ids: str = "",
                 team_id: str | int = 0, season: str | None = None, season_type: SeasonType = 'regular-season') -> dict:
        cols = ["lineup_state", "minutes", "off_rating", "def_rating", "net_rating", "poss"]
        args = {
            "player_a": player_a, "player_b": player_b, "player_ids": player_ids,
            "team_id": team_id, "season": season,
        }
        if season_type != 'regular-season':
            args['season_type'] = season_type
        res = call_sync(_orig_get_wowy, "get_wowy", args)
        return finish_strict_rows(res, "get_wowy", cols, "WOWY lookup failed", _wowy_rows, fixed_cols=True)

    @tool("get_raptor_history", description=_orig_get_raptor_history.description)
    def get_raptor_history(player: str = "", season: str = "") -> dict:
        cols = ["SEASON", "TEAM", "MP", "RAPTOR_O", "RAPTOR_D", "RAPTOR", "WAR"]
        res = call_sync(_orig_get_raptor_history, "get_raptor_history", {"player": player, "season": season})
        return finish_strict_rows(res, "get_raptor_history", cols, "RAPTOR history lookup failed",
                                  _raptor_rows, fixed_cols=True)

    @tool("get_last_x", description=_orig_get_last_x.description)
    def get_last_x(player_id: str | int, n: int = 10, season: str | None = None) -> dict:
        res = call_sync(_orig_get_last_x, "get_last_x", {"player_id": player_id, "n": n, "season": season})
        return _row_list_result(res, "get_last_x", ["GAME_DATE", "MATCHUP", "PTS", "REB", "AST", "MIN"])

    @tool("get_player_report", description=_orig_get_player_report.description)
    def get_player_report(player: str | int, season: str | None = None) -> dict:
        res = call_sync(_orig_get_player_report, "get_player_report", {"player": player, "season": season})
        return _flatten_sections(res, ["section", "PLAYER", "TEAM", "PPG", "RPG", "APG"], name="get_player_report")

    @tool("get_splits", description=_orig_get_splits.description)
    def get_splits(player_id: str | int, season: str | None = None) -> dict:
        res = call_sync(_orig_get_splits, "get_splits", {"player_id": player_id, "season": season})
        return _row_list_result(res, "get_splits", ["split", "GP", "PPG", "FG_PCT"])

    @tool("get_tracking_profile", description=_orig_get_tracking_profile.description)
    def get_tracking_profile(player: str = "", team: str = "", season: str = "2025-26",
                             measure_type: str = "Drives") -> dict:
        cols = ["subject", "season", "measure_type", "stat", "value"]
        res = call_sync(_orig_get_tracking_profile, "get_tracking_profile", {
            "player": player, "team": team, "season": season, "measure_type": measure_type,
        }, include_exc_type=False)
        return finish_strict_rows(
            res, "get_tracking_profile", cols, "Tracking profile lookup failed",
            lambda r: _tracking_rows(r, tracking_excluded, player, team, season, measure_type), fixed_cols=True,
        )

    @tool("get_rapm_prior", description=_orig_get_rapm_prior.description)
    def get_rapm_prior(player: str = "", seasons: object = None) -> dict:
        cols = ["player", "season", "rapm", "possessions", "kind", "estimate"]
        res = call_sync(_orig_get_rapm_prior, "get_rapm_prior", {"player": player, "seasons": seasons})
        return finish_strict_rows(res, "get_rapm_prior", cols, "RAPM prior lookup failed",
                                  lambda r: _rapm_prior_rows(r, player), fixed_cols=True)

    @tool("get_impact_rank", description=_orig_get_impact_rank.description)
    def get_impact_rank(player: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_impact_rank, "get_impact_rank", {"player": player, "season": season})
        rows = res.get("rows") if res.get("ok") and isinstance(res.get("rows"), list) else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["player", "season", "metric", "value", "rank", "players", "qualifier", "source"]
        if not res.get("ok"):
            enrich_error("get_impact_rank", res)
        return res

    @tool("search_game_logs", description=_orig_search_game_logs.description)
    def search_game_logs(
        player: str | None = None, league_wide: bool = False, team_wide: bool = False,
        min_points: float | None = None, min_rebounds: float | None = None,
        min_assists: float | None = None, min_pra: float | None = None,
        max_points: float | None = None, max_rebounds: float | None = None,
        max_assists: float | None = None, triple_double: bool = False,
        double_double: bool = False, best_game: bool = False,
        opponent: str | None = None, month: str | int | None = None,
        start_date: str | None = None, end_date: str | None = None,
        home_away: str | None = None, playoffs: bool = False,
        season: str | None = None, limit: int = 50,
    ) -> dict:
        cols = ["date", "game_id", "opponent", "matchup", "home", "pts", "reb", "ast", "stl", "blk", "tov", "min", "wl"]
        res = call_sync(_orig_search_game_logs, "search_game_logs", {
            "player": player, "league_wide": league_wide, "team_wide": team_wide,
            "min_points": min_points, "min_rebounds": min_rebounds, "min_assists": min_assists,
            "min_pra": min_pra, "max_points": max_points, "max_rebounds": max_rebounds,
            "max_assists": max_assists, "triple_double": triple_double,
            "double_double": double_double, "best_game": best_game,
            "opponent": opponent, "month": month, "start_date": start_date,
            "end_date": end_date, "home_away": home_away, "playoffs": playoffs,
            "season": season, "limit": limit,
        })
        return finish_strict_rows(res, "search_game_logs", cols, "Game logs search failed", _gamelog_rows)

    @tool("get_career_arc", description="Query year-over-year career trajectory, statistical evolution, scoring efficiency, and RAPTOR ratings for an NBA player across multiple seasons.")
    def get_career_arc(player: str = "", player_id: int = 0) -> dict:
        from shared.tools.career_arc import get_career_arc as _run_career_arc
        cols = ["season", "pts", "reb", "ast", "min", "ts_pct", "raptor"]
        try:
            res = _run_career_arc.invoke({"player": player, "player_id": player_id})
            if not isinstance(res, dict):
                return sanitize_for_wire(enrich_error("get_career_arc", {
                    "ok": False, "tool": "get_career_arc", "rows": [], "columns": cols,
                    "error": "Invalid result from career arc tool",
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_career_arc", {
                "ok": False, "tool": "get_career_arc", "rows": [], "columns": cols,
                "error": str(exc),
            }))
        if not res.get("ok"):
            enrich_error("get_career_arc", res)
        return sanitize_for_wire(res)

    return {
        "get_rapm": get_rapm,
        "get_comps": get_comps,
        "get_era_comps": get_era_comps,
        "get_on_off": get_on_off,
        "get_availability_impact": get_availability_impact,
        "get_clutch_stats": get_clutch_stats,
        "get_situational_splits": get_situational_splits,
        "get_playtype_profile": get_playtype_profile,
        "get_defensive_matchups": get_defensive_matchups,
        "get_wowy": get_wowy,
        "get_raptor_history": get_raptor_history,
        "get_last_x": get_last_x,
        "get_player_report": get_player_report,
        "get_splits": get_splits,
        "get_tracking_profile": get_tracking_profile,
        "get_rapm_prior": get_rapm_prior,
        "get_impact_rank": get_impact_rank,
        "search_game_logs": search_game_logs,
        "get_career_arc": get_career_arc,
    }
