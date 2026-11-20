import os
from typing import Any

from langchain_core.tools import tool

from .common import call_sync, finish_dict_list, sanitize_for_wire
from .errors import enrich_error


def _standings_deep_item(item: dict[str, Any], cat_label: str) -> dict[str, Any]:
    row = dict(item)
    row["CATEGORY"] = cat_label
    if "RECORD" not in row and "W" in row and "L" in row:
        row["RECORD"] = f"{row['W']}-{row['L']}"
    return row


def _collect_deep_category(cat: str, items: Any) -> list[dict[str, Any]]:
    if isinstance(items, list):
        return [_standings_deep_item(item, cat) for item in items if isinstance(item, dict)]
    if isinstance(items, dict):
        rows: list[dict[str, Any]] = []
        for sub_cat, sub_items in items.items():
            if isinstance(sub_items, list):
                rows.extend(_standings_deep_item(item, f"{cat}_{sub_cat}") for item in sub_items if isinstance(item, dict))
        return rows
    return []


def _standings_deep_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    rows: list[dict[str, Any]] = []
    for cat, items in raw_rows.items():
        rows.extend(_collect_deep_category(cat, items))
    return rows or [raw_rows]


def _win_prob_rows(raw_rows: Any, team_a: str, team_b: str) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    win_prob = raw_rows.get("win_prob") or {}
    a = (team_a or "").upper()
    b = (team_b or "").upper()
    p_a = win_prob.get(a)
    p_b = win_prob.get(b)
    if p_a is None and p_b is None and len(win_prob) >= 2:
        keys = list(win_prob.keys())
        p_a = win_prob.get(keys[0])
        p_b = win_prob.get(keys[1])
    return [{
        "team_a": a, "team_b": b,
        "win_prob_a": p_a, "win_prob_b": p_b,
        "elo_a": raw_rows.get("elo_a"), "elo_b": raw_rows.get("elo_b"),
    }]


def _playoffs_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    champ = raw_rows.get("champion", "")
    wins = raw_rows.get("wins")
    if isinstance(wins, list) and wins:
        return [
            {"team": w.get("team"), "w": w.get("w"), "l": w.get("l"), "champion": champ}
            for w in wins if isinstance(w, dict)
        ]
    if champ:
        rec = raw_rows.get("champion_record") or {}
        return [{"team": champ, "w": rec.get("w"), "l": rec.get("l"), "champion": champ}]
    return []


def _playoff_sim_rows(raw_rows: Any, sims: int) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if not isinstance(raw_rows, dict):
        return []
    teams = raw_rows.get("teams")
    if not (isinstance(teams, list) and teams):
        return [raw_rows]
    title_probs = raw_rows.get("title_probs") or {}
    final_probs = raw_rows.get("final_probs") or {}
    sims_val = raw_rows.get("sims", sims)
    t_scale = 100 if max(title_probs.values(), default=0.0) <= 1.0 else 1
    f_scale = 100 if max(final_probs.values(), default=0.0) <= 1.0 else 1
    return [
        {
            "team": t,
            "title_pct": round(title_probs.get(t, 0.0) * t_scale, 2),
            "finals_pct": round(final_probs.get(t, 0.0) * f_scale, 2),
            "sims": sims_val,
        }
        for t in teams
    ]


def _dict_or_list_rows(raw_rows: Any) -> list[dict[str, Any]]:
    if isinstance(raw_rows, list):
        return [r for r in raw_rows if isinstance(r, dict)]
    if isinstance(raw_rows, dict):
        return [raw_rows]
    return []


def _offline_call(orig: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        if os.environ.get("PI_OFFLINE"):
            raise RuntimeError("offline mode: live fetching disabled")
        res = orig.invoke(args)
        if not isinstance(res, dict):
            return {"tool": name, "ok": False, "error": str(res)}
        return res
    except Exception as exc:
        return {"tool": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def register() -> dict[str, Any]:
    from shared.tools.league import (
        get_combine as _orig_get_combine,
        get_draft_board as _orig_get_draft_board,
        get_draft_model as _orig_get_draft_model,
        get_elo_standings as _orig_get_elo_standings,
        get_free_agents as _orig_get_free_agents,
        get_expectations as _orig_get_expectations,
        get_hustle as _orig_get_hustle,
        get_injuries as _orig_get_injuries,
        get_news_feed as _orig_get_news_feed,
        get_prospect as _orig_get_prospect,
        get_playoff_sim as _orig_get_playoff_sim,
        get_playoff_team_ratings as _orig_get_playoff_team_ratings,
        get_playoffs as _orig_get_playoffs,
        get_ratings as _orig_get_ratings,
        get_roster_fit as _orig_get_roster_fit,
        get_standings as _orig_get_standings,
        get_standings_deep as _orig_get_standings_deep,
        get_win_prob as _orig_get_win_prob,
    )
    from shared.tools.competitive import get_competitive_ratings as _orig_get_competitive_ratings
    try:
        from shared.tools.league import get_elo as _orig_get_elo
    except ImportError:
        from backend.shared.tools.league import get_elo as _orig_get_elo

    @tool("get_standings", description=_orig_get_standings.description)
    def get_standings(season: str | None = None) -> dict:
        res = call_sync(_orig_get_standings, "get_standings", {"season": season})
        return finish_dict_list(res, "get_standings", ["team", "wins", "losses", "pct", "conference", "division", "gb"])

    @tool("get_standings_deep", description=_orig_get_standings_deep.description)
    def get_standings_deep(season: str | None = None, top: int = 5) -> dict:
        res = call_sync(_orig_get_standings_deep, "get_standings_deep", {"season": season, "top": top})
        rows = _standings_deep_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["TEAM", "CATEGORY", "W", "L", "PCT", "RECORD"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_standings_deep", res)
        return sanitize_for_wire(res)

    @tool("get_ratings", description=_orig_get_ratings.description)
    def get_ratings(season: str | None = None, team: str = "",
                    requested_metric: str = "", ranking_direction: str = "") -> dict:
        res = call_sync(_orig_get_ratings, "get_ratings", {
            "season": season, "team": team, "requested_metric": requested_metric,
            "ranking_direction": ranking_direction,
        })
        return finish_dict_list(res, "get_ratings", ["team", "off_rating", "def_rating", "net_rating", "pace", "wins", "losses"])

    @tool("get_competitive_ratings", description=_orig_get_competitive_ratings.description)
    def get_competitive_ratings(team: str = "league", season: str | None = None,
                                blowout_margin: float = 20, min_games: int = 10) -> dict:
        res = call_sync(_orig_get_competitive_ratings, "get_competitive_ratings", {
            "team": team, "season": season, "blowout_margin": blowout_margin, "min_games": min_games,
        })
        return finish_dict_list(res, "get_competitive_ratings", ["team", "team_name", "games", "mov", "competitive_mov", "padding_delta"], set_ok=False)

    @tool("get_elo", description=_orig_get_elo.description)
    def get_elo(season: str | None = None) -> dict:
        cols = ["rank", "TEAM", "ELO", "W", "L"]
        res = call_sync(_orig_get_elo, "get_elo", {"season": season})
        if not res.get("ok"):
            return sanitize_for_wire(enrich_error("get_elo", {
                "ok": False, "tool": "get_elo", "rows": [], "columns": cols,
                "error": str(res.get("error") or "ELO ratings query failed"),
            }))
        raw_rows = res.get("rows")
        raw_list = [r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else []
        res["rows"] = [{k: r.get(k) for k in cols} for r in raw_list]
        res["columns"] = cols
        res["ok"] = True
        return sanitize_for_wire(res)

    @tool("get_elo_standings", description=_orig_get_elo_standings.description)
    def get_elo_standings(season: str | None = None, opponent: str | None = None, limit: int = 30) -> dict:
        res = call_sync(_orig_get_elo_standings, "get_elo_standings", {"season": season, "opponent": opponent, "limit": limit})
        return finish_dict_list(res, "get_elo_standings", ["rank", "abbr", "elo", "games", "w", "l", "elo_win_pct", "win_equiv", "elo_implied_spread"])

    @tool("get_win_prob", description=_orig_get_win_prob.description)
    def get_win_prob(team_a: str, team_b: str, season: str | None = None, home_abbrev: str = "") -> dict:
        res = call_sync(_orig_get_win_prob, "get_win_prob", {
            "team_a": team_a, "team_b": team_b, "season": season, "home_abbrev": home_abbrev,
        })
        default_cols = ["team_a", "team_b", "win_prob_a", "win_prob_b", "elo_a", "elo_b"]
        rows = _win_prob_rows(res.get("rows"), team_a, team_b) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else default_cols
        if not res.get("ok"):
            enrich_error("get_win_prob", res)
        return sanitize_for_wire(res)

    @tool("get_playoffs", description=_orig_get_playoffs.description)
    def get_playoffs(season: str | None = None) -> dict:
        res = call_sync(_orig_get_playoffs, "get_playoffs", {"season": season})
        rows = _playoffs_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["team", "w", "l", "champion"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_playoffs", res)
        return sanitize_for_wire(res)

    @tool("get_playoff_sim", description=_orig_get_playoff_sim.description)
    def get_playoff_sim(season: str | None = None, sims: int = 2000) -> dict:
        res = call_sync(_orig_get_playoff_sim, "get_playoff_sim", {"season": season, "sims": sims})
        rows = _playoff_sim_rows(res.get("rows"), sims) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["team", "title_pct", "finals_pct", "sims"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_playoff_sim", res)
        return sanitize_for_wire(res)

    @tool("get_playoff_team_ratings", description=_orig_get_playoff_team_ratings.description)
    def get_playoff_team_ratings(season: str | None = None, limit: int = 30) -> dict:
        res = call_sync(_orig_get_playoff_team_ratings, "get_playoff_team_ratings", {"season": season, "limit": limit})
        rows = _dict_or_list_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["team", "games", "off_rating", "def_rating", "net_rating"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_playoff_team_ratings", res)
        return sanitize_for_wire(res)

    @tool("get_hustle", description=_orig_get_hustle.description)
    def get_hustle(scope: str = "player", season: str | None = None) -> dict:
        res = call_sync(_orig_get_hustle, "get_hustle", {"scope": scope, "season": season})
        return finish_dict_list(res, "get_hustle", ["player_name", "team_abbreviation", "contested_shots", "deflections", "charges_drawn", "screen_assists"])

    @tool("get_injuries", description=_orig_get_injuries.description)
    def get_injuries(team: str = "", player: str = "", season: str | None = None) -> dict:
        res = call_sync(_orig_get_injuries, "get_injuries", {"team": team, "player": player, "season": season})
        return finish_dict_list(res, "get_injuries", ["player", "team", "status", "injury", "description"])

    @tool("get_news_feed", description=_orig_get_news_feed.description)
    def get_news_feed(team: str = "", player: str = "", limit: int = 15) -> dict:
        res = call_sync(_orig_get_news_feed, "get_news_feed", {"team": team, "player": player, "limit": limit})
        return finish_dict_list(res, "get_news_feed", ["headline", "published", "url", "source_feed", "players", "teams"])

    @tool("get_free_agents", description=_orig_get_free_agents.description)
    def get_free_agents(team: str = "", fa_year: str = "2027") -> dict:
        res = call_sync(_orig_get_free_agents, "get_free_agents", {"team": team, "fa_year": fa_year})
        rows = _dict_or_list_rows(res.get("free_agents") if res.get("ok") else [])
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["PLAYER_NAME", "TEAM", "FA_TYPE", "PRIOR_SALARY", "CAP_HOLD_EST"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_free_agents", res)
        return sanitize_for_wire(res)

    @tool("get_prospect", description=_orig_get_prospect.description)
    def get_prospect(player: str = "", draft_year: str = "2027", position: str = "") -> dict:
        res = call_sync(_orig_get_prospect, "get_prospect", {"player": player, "draft_year": draft_year, "position": position})
        rows = _dict_or_list_rows(res.get("boards") if res.get("ok") else [])
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["ORDER", "PLAYER_NAME", "POSITION", "SCHOOL", "AGE", "BOARD"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_prospect", res)
        return sanitize_for_wire(res)

    @tool("get_roster_fit", description=_orig_get_roster_fit.description)
    def get_roster_fit(team_id=None, team: str = "", season=None) -> dict:
        res = call_sync(_orig_get_roster_fit, "get_roster_fit", {
            "team_id": team_id, "team": team, "season": season})
        return finish_dict_list(res, "get_roster_fit",
                                ["dimension", "team", "league_avg",
                                 "contender_avg", "gap_vs_contenders"])

    @tool("get_expectations", description=_orig_get_expectations.description)
    def get_expectations(team_id=None, team: str = "", season=None,
                         seasons: int = 3) -> dict:
        res = call_sync(_orig_get_expectations, "get_expectations", {
            "team_id": team_id, "team": team, "season": season,
            "seasons": seasons})
        return finish_dict_list(res, "get_expectations",
                                ["season", "team", "projected_wins",
                                 "actual_wins", "wins_vs_projection",
                                 "net_rating", "status"])

    @tool("get_draft_board", description=_orig_get_draft_board.description)
    def get_draft_board(season: str = "2025") -> dict:
        res = _offline_call(_orig_get_draft_board, "get_draft_board", {"season": season})
        return finish_dict_list(res, "get_draft_board", ["rank", "player", "pos", "school", "draft_score", "bpm"])

    @tool("get_combine", description=_orig_get_combine.description)
    def get_combine(season: str = "2025") -> dict:
        res = _offline_call(_orig_get_combine, "get_combine", {"season": season})
        return finish_dict_list(res, "get_combine", ["player", "pos", "height_wo_shoes", "height_w_shoes", "weight", "wingspan", "standing_reach"])

    @tool("get_draft_model", description=_orig_get_draft_model.description)
    def get_draft_model(season: str = "2025") -> dict:
        res = call_sync(_orig_get_draft_model, "get_draft_model", {"season": season})
        rows = _dict_or_list_rows(res.get("rows")) if res.get("ok") else []
        res["rows"] = rows
        res["columns"] = list(rows[0].keys()) if rows else ["PLAYER", "TEAM", "PTS", "TS_PCT", "USG", "STAR_P"]
        res["ok"] = bool(res.get("ok", False))
        if not res["ok"]:
            enrich_error("get_draft_model", res)
        return sanitize_for_wire(res)

    return {
        "get_standings": get_standings,
        "get_standings_deep": get_standings_deep,
        "get_ratings": get_ratings,
        "get_competitive_ratings": get_competitive_ratings,
        "get_elo": get_elo,
        "get_elo_standings": get_elo_standings,
        "get_win_prob": get_win_prob,
        "get_playoffs": get_playoffs,
        "get_playoff_sim": get_playoff_sim,
        "get_playoff_team_ratings": get_playoff_team_ratings,
        "get_hustle": get_hustle,
        "get_injuries": get_injuries,
        "get_news_feed": get_news_feed,
        "get_free_agents": get_free_agents,
        "get_prospect": get_prospect,
        "get_roster_fit": get_roster_fit,
        "get_expectations": get_expectations,
        "get_draft_board": get_draft_board,
        "get_combine": get_combine,
        "get_draft_model": get_draft_model,
    }
