from typing import Any

from langchain_core.tools import tool

from .common import (
    _bounded_live_call,
    _row_list_result,
    _sectioned_result,
    call_sync,
    finish_strict_rows,
    sanitize_for_wire,
)
from .errors import enrich_error


def _prediction_row(res: dict[str, Any]) -> dict[str, Any]:
    matchup = res.get("matchup") or {}
    estimate = res.get("estimate") or {}
    inputs = res.get("inputs") or {}
    home = matchup.get("home", "")
    away = matchup.get("away", "")
    win_prob = estimate.get("win_prob") or {}
    score = estimate.get("projected_score") or {}
    return {
        "team_home": home,
        "team_away": away,
        "win_prob_home": win_prob.get(home),
        "win_prob_away": win_prob.get(away),
        "projected_score_home": score.get(home),
        "projected_score_away": score.get(away),
        "pace": inputs.get("game_pace"),
    }


def _wpa_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, dict) and isinstance(raw_rows.get("leaders"), list):
        return raw_rows["leaders"]
    if isinstance(raw_rows, list):
        return raw_rows
    return []


def _h2h_game_row(g: dict[str, Any], player_val: Any, opp_val: Any) -> dict[str, Any]:
    row = {
        "date": g.get("date"),
        "matchup": g.get("matchup"),
        "wl": g.get("wl"),
        "min": g.get("min"),
        "pts": g.get("pts"),
        "reb": g.get("reb"),
        "ast": g.get("ast"),
        "stl": g.get("stl"),
        "blk": g.get("blk"),
        "plus_minus": g.get("plus_minus"),
        "player": player_val,
        "opponent": opp_val,
    }
    for k, v in g.items():
        if k not in row:
            row[k] = v
    return row


def _h2h_rows(res: dict[str, Any], player: str, opponent: str) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    player_val = raw_rows.get("player") or player
    opp_val = raw_rows.get("opponent") or opponent
    games = raw_rows.get("games")
    if isinstance(games, list) and games:
        return [_h2h_game_row(g, player_val, opp_val) for g in games if isinstance(g, dict)]
    vs_opp = raw_rows.get("vs_opponent")
    if isinstance(vs_opp, dict):
        return [{"player": player_val, "opponent": opp_val, **vs_opp}]
    return []


def _matrix_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [raw_rows]
    return []


def register() -> dict[str, Any]:
    from shared.tools.prediction import get_game_prediction as _orig_get_game_prediction
    from shared.tools.wpa import get_wpa_leaders as _orig_get_wpa_leaders
    try:
        from shared.tools.headtohead import get_head_to_head as _orig_get_head_to_head
    except ImportError:
        from backend.shared.tools.headtohead import get_head_to_head as _orig_get_head_to_head
    try:
        from shared.tools.lineup_matrix import get_lineup_matchup_matrix as _orig_get_lineup_matchup_matrix
    except ImportError:
        from backend.shared.tools.lineup_matrix import get_lineup_matchup_matrix as _orig_get_lineup_matchup_matrix
    try:
        from shared.tools.preview import get_matchup_preview as _orig_get_matchup_preview
    except ImportError:
        from backend.shared.tools.preview import get_matchup_preview as _orig_get_matchup_preview
    try:
        from shared.tools.splits import (
            get_matchup_splits as _orig_get_matchup_splits,
            get_regression_check as _orig_get_regression_check,
        )
    except ImportError:
        from backend.shared.tools.splits import (
            get_matchup_splits as _orig_get_matchup_splits,
            get_regression_check as _orig_get_regression_check,
        )
    try:
        from shared.tools.team import (
            get_boxscore,
            get_games_on_date,
            get_injury_impact as _orig_get_injury_impact,
            get_matchup_brief as _orig_get_matchup_brief,
            get_recap as _orig_get_recap,
            get_rotation_check as _orig_get_rotation_check,
            get_opponent_scout as _orig_get_opponent_scout,
            get_scout_pack as _orig_get_scout_pack,
        )
    except ImportError:
        from backend.shared.tools.team import (
            get_boxscore,
            get_games_on_date,
            get_injury_impact as _orig_get_injury_impact,
            get_matchup_brief as _orig_get_matchup_brief,
            get_recap as _orig_get_recap,
            get_rotation_check as _orig_get_rotation_check,
            get_opponent_scout as _orig_get_opponent_scout,
            get_scout_pack as _orig_get_scout_pack,
        )

    @tool("get_game_prediction", description=_orig_get_game_prediction.description)
    def get_game_prediction(a: str = "", b: str = "", game_date: str = "",
                            season: str | None = None, n_sims: int = 10000,
                            seed: int = 7) -> dict:
        res = call_sync(_orig_get_game_prediction, "get_game_prediction", {
            "a": a, "b": b, "game_date": game_date, "season": season, "n_sims": n_sims, "seed": seed,
        })
        default_cols = [
            "team_home", "team_away", "win_prob_home", "win_prob_away",
            "projected_score_home", "projected_score_away", "pace",
        ]
        if res.get("ok"):
            row = _prediction_row(res)
            res["rows"] = [row]
            res["columns"] = list(row.keys())
            return res
        res["rows"] = []
        res["columns"] = default_cols
        return enrich_error("get_game_prediction", res)

    @tool("get_wpa_leaders", description=_orig_get_wpa_leaders.description)
    def get_wpa_leaders(season: int | str | None = 2025,
                        limit: int | str | None = 10,
                        min_events: int | str | None = 100) -> dict:
        res = call_sync(_orig_get_wpa_leaders, "get_wpa_leaders", {
            "season": season, "limit": limit, "min_events": min_events,
        })
        default_cols = [
            "rank", "player", "player_id", "team", "wpa", "wpa_g",
            "events", "plus_events", "minus_events", "games",
        ]
        rows = _wpa_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_wpa_leaders", res)
        return res

    @tool("get_head_to_head", description=_orig_get_head_to_head.description)
    def get_head_to_head(player: str, opponent: str, season: str | None = None) -> dict:
        cols = ["date", "matchup", "wl", "min", "pts", "reb", "ast", "stl", "blk", "plus_minus"]
        try:
            res = _orig_get_head_to_head.invoke({"player": player, "opponent": opponent, "season": season})
            if not isinstance(res, dict) or not res.get("ok"):
                err = res.get("error") if isinstance(res, dict) else res
                return sanitize_for_wire(enrich_error("get_head_to_head", {
                    "ok": False, "tool": "get_head_to_head", "rows": [],
                    "columns": cols, "error": str(err or "Head-to-head lookup failed"),
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_head_to_head", {
                "tool": "get_head_to_head", "ok": False, "error": str(exc),
                "rows": [], "columns": [],
            }))
        return finish_strict_rows(res, "get_head_to_head", cols, "Head-to-head lookup failed",
                                  lambda r: _h2h_rows(r, player, opponent))

    @tool("get_lineup_matchup_matrix", description=_orig_get_lineup_matchup_matrix.description)
    def get_lineup_matchup_matrix(team_a: str, team_b: str, min_minutes: float = 10,
                                  season: str | None = None) -> dict:
        cols = ["team_a_lineup", "team_b_lineup", "poss", "est_minutes", "OFF_RATING_A", "DEF_RATING_A", "NET_RATING_A", "blowout_share"]
        try:
            res = _orig_get_lineup_matchup_matrix.invoke({
                "team_a": team_a, "team_b": team_b, "min_minutes": min_minutes, "season": season,
            })
            if not isinstance(res, dict) or not res.get("ok"):
                err = res.get("error") if isinstance(res, dict) else res
                return sanitize_for_wire(enrich_error("get_lineup_matchup_matrix", {
                    "ok": False, "tool": "get_lineup_matchup_matrix", "rows": [],
                    "columns": cols, "error": str(err or "Lineup matchup matrix lookup failed"),
                }))
        except Exception as exc:
            return sanitize_for_wire(enrich_error("get_lineup_matchup_matrix", {
                "tool": "get_lineup_matchup_matrix", "ok": False, "error": str(exc),
                "rows": [], "columns": [],
            }))
        return finish_strict_rows(res, "get_lineup_matchup_matrix", cols,
                                  "Lineup matchup matrix lookup failed", _matrix_rows)

    @tool("get_matchup_brief", description=_orig_get_matchup_brief.description)
    async def get_matchup_brief(a: str = "", b: str = "", season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_matchup_brief, "get_matchup_brief",
                                       {"a": a, "b": b, "season": season})

    @tool("get_matchup_preview", description=_orig_get_matchup_preview.description)
    async def get_matchup_preview(a: str = "", b: str = "", game_date: str = "",
                                  season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_matchup_preview, "get_matchup_preview",
                                       {"a": a, "b": b, "game_date": game_date, "season": season})

    @tool("get_scout_pack", description=_orig_get_scout_pack.description)
    async def get_scout_pack(team: str = "", opponent: str = "", season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_scout_pack, "get_scout_pack",
                                       {"team": team, "opponent": opponent, "season": season})

    @tool("get_opponent_scout", description=_orig_get_opponent_scout.description)
    async def get_opponent_scout(team: str = "", opponent: str = "", season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_opponent_scout, "get_opponent_scout",
                                       {"team": team, "opponent": opponent, "season": season})

    @tool("get_injury_impact", description=_orig_get_injury_impact.description)
    async def get_injury_impact(team: str = "", season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_injury_impact, "get_injury_impact",
                                       {"team": team, "season": season})

    @tool("get_rotation_check", description=_orig_get_rotation_check.description)
    async def get_rotation_check(team: str | int = "", season: str | None = None,
                                 min_possessions: int = 100, top_units: int = 5) -> dict:
        return await _sectioned_result(_orig_get_rotation_check, "get_rotation_check",
                                       {"team": team, "season": season,
                                        "min_possessions": min_possessions, "top_units": top_units})

    @tool("get_matchup_splits", description=_orig_get_matchup_splits.description)
    async def get_matchup_splits(player: str, n: int = 15, season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_matchup_splits, "get_matchup_splits",
                                       {"player": player, "n": n, "season": season})

    @tool("get_regression_check", description=_orig_get_regression_check.description)
    async def get_regression_check(player: str, stat: str = "PTS", n: int = 10,
                                   season: str | None = None) -> dict:
        return await _sectioned_result(_orig_get_regression_check, "get_regression_check",
                                       {"player": player, "stat": stat, "n": n, "season": season})

    @tool("get_recap", description=_orig_get_recap.description)
    async def get_recap(game_id: str, season: str | None = None) -> dict:
        default_cols = ["PLAYER", "TEAM", "PTS", "REB", "AST"]
        res = await _bounded_live_call(_orig_get_recap, "get_recap", {"game_id": game_id, "season": season})
        return _row_list_result(res, "get_recap", default_cols)

    return {
        "get_game_prediction": get_game_prediction,
        "get_wpa_leaders": get_wpa_leaders,
        "get_head_to_head": get_head_to_head,
        "get_lineup_matchup_matrix": get_lineup_matchup_matrix,
        "get_matchup_brief": get_matchup_brief,
        "get_matchup_preview": get_matchup_preview,
        "get_scout_pack": get_scout_pack,
        "get_opponent_scout": get_opponent_scout,
        "get_injury_impact": get_injury_impact,
        "get_rotation_check": get_rotation_check,
        "get_matchup_splits": get_matchup_splits,
        "get_regression_check": get_regression_check,
        "get_recap": get_recap,
        "get_games_on_date": get_games_on_date,
        "get_boxscore": get_boxscore,
    }
