"""Named Dime data operations over MCP stdio. Pi receives a fixed read-only view."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

# Resolve source imports independently of the private working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


def catalogue():
    from shared.tools.sql_exec import sql_exec, TABLES
    from shared.tools.league import (
        _get_warehouse_schema,
        get_win_prob as _orig_get_win_prob,
        get_team_four_factors as _orig_get_four_factors,
        get_hustle as _orig_get_hustle,
        get_injuries as _orig_get_injuries,
        get_briefing as _orig_get_briefing,
        get_standings as _orig_get_standings,
        get_rest as _orig_get_rest,
        get_team_trajectory as _orig_get_team_trajectory,
        get_ratings as _orig_get_ratings,
        get_rookie_leaders as _orig_get_rookie_leaders,
        get_cap_ledger as _orig_get_cap_ledger,
        get_leaders as _orig_get_leaders,
        get_lineup_leaders as _orig_get_lineup_leaders,
        get_playoffs as _orig_get_playoffs,
        get_team_leaders as _orig_get_team_leaders,
        get_team_compare as _orig_get_team_compare,
        get_elo_standings as _orig_get_elo_standings,
        get_draft_board as _orig_get_draft_board,
        get_combine as _orig_get_combine,
        get_young_player_usage as _orig_get_young_player_usage,
    )
    try:
        from shared.tools.league import get_clutch_stats as _orig_get_clutch_stats
    except ImportError:
        from shared.tools.league import get_clutch as _orig_get_clutch_stats
    from shared.tools.competitive import get_competitive_ratings as _orig_get_competitive_ratings
    from shared.tools.season_semantics import annotate_schema
    try:
        from shared.tools.rapm import get_rapm as _orig_get_rapm
    except ImportError:
        from shared.tools.league import get_rapm as _orig_get_rapm
    from shared.tools.prediction import get_game_prediction as _orig_get_game_prediction
    from shared.tools.wpa import get_wpa_leaders as _orig_get_wpa_leaders
    from shared.tools.player import (
        get_comps as _orig_get_comps,
        get_on_off as _orig_get_on_off,
        get_shot_zones as _orig_get_shot_zones,
    )
    from shared.tools.lineup import get_lineup_stats as _orig_get_lineup_stats
    from shared.tools.award_results import get_award_results as _orig_get_award_results
    from langchain_core.tools import tool

    declared_catalog = ", ".join(TABLES)
    description = (
        "Read declared warehouse columns, source units and season encodings. "
        "Pass tables to return only those declared tables (avoiding full catalog payloads). "
        f"Declared table allowlist: {declared_catalog}. "
        "This allowlist names declared tables, not proof of actual table content, "
        "complete warehouse inventory or data freshness. "
        "catalog_scope covers the returned declared tables and columns only, not the full warehouse "
        "inventory; a name absent here is not evidence it is absent everywhere."
    )

    @tool("warehouse_schema", description=description)
    def warehouse_schema(tables: list[str] | None = None) -> dict:
        """Read declared warehouse columns, source units and season encodings."""
        _, columns = _get_warehouse_schema()
        if tables is None:
            selected = list(columns)
        else:
            selected = []
            unknown = []
            for name in dict.fromkeys(tables):
                if name in columns:
                    selected.append(name)
                else:
                    unknown.append(name)
            if unknown:
                raise ValueError(
                    "unknown declared table(s) in tables selection: "
                    f"{', '.join(unknown)}; omit tables for the full declared schema")
            if not selected:
                raise ValueError(
                    "tables selection must name at least one declared table; "
                    "omit tables for the full declared schema")
        annotated = annotate_schema(
            {"tables": {name: columns[name] for name in selected}})
        annotated["catalog_scope"] = {
            "kind": "declared_read_only_tables",
            "exhaustive_warehouse_inventory": False,
            "available_table_count": len(columns),
            "returned_table_count": len(selected),
            "negative_claim_scope": "returned declared tables and columns only",
        }
        return annotated

    @tool("get_rapm", description=_orig_get_rapm.description)
    def get_rapm(player: str = "", top: int = 10, season: str | None = None) -> dict:
        """RAPM-lite ratings. Blank player returns top list, else one row."""
        try:
            res = _orig_get_rapm.invoke({"player": player, "top": top, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_rapm", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_rapm", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        rows = res.get("rows")
        if not (res.get("ok") and isinstance(rows, list)):
            rows = []
        cols = list(rows[0].keys()) if rows else ["player_id", "name", "rapm", "possessions"]
        res["rows"] = rows
        res["columns"] = cols
        return res

    @tool("get_game_prediction", description=_orig_get_game_prediction.description)
    def get_game_prediction(a: str = "", b: str = "", game_date: str = "",
                            season: str | None = None, n_sims: int = 10000,
                            seed: int = 7) -> dict:
        """Pre-game Monte Carlo prediction: win probability, projected score/total, and confidence intervals."""
        try:
            res = _orig_get_game_prediction.invoke({
                "a": a, "b": b, "game_date": game_date, "season": season, "n_sims": n_sims, "seed": seed
            })
            if not isinstance(res, dict):
                res = {"tool": "get_game_prediction", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_game_prediction", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = [
            "team_home", "team_away", "win_prob_home", "win_prob_away",
            "projected_score_home", "projected_score_away", "pace"
        ]
        if res.get("ok"):
            matchup = res.get("matchup") or {}
            estimate = res.get("estimate") or {}
            inputs = res.get("inputs") or {}
            home = matchup.get("home", "")
            away = matchup.get("away", "")
            win_prob = estimate.get("win_prob") or {}
            score = estimate.get("projected_score") or {}
            pace = inputs.get("game_pace")
            row = {
                "team_home": home,
                "team_away": away,
                "win_prob_home": win_prob.get(home),
                "win_prob_away": win_prob.get(away),
                "projected_score_home": score.get(home),
                "projected_score_away": score.get(away),
                "pace": pace,
            }
            res["rows"] = [row]
            res["columns"] = list(row.keys())
        else:
            res["rows"] = []
            res["columns"] = default_cols
        return res

    @tool("get_wpa_leaders", description=_orig_get_wpa_leaders.description)
    def get_wpa_leaders(season: int | str | None = 2025,
                        limit: int | str | None = 10,
                        min_events: int | str | None = 100) -> dict:
        """WPA-by-play leaderboard for one season."""
        try:
            res = _orig_get_wpa_leaders.invoke({
                "season": season, "limit": limit, "min_events": min_events
            })
            if not isinstance(res, dict):
                res = {"tool": "get_wpa_leaders", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_wpa_leaders", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        raw_rows = res.get("rows")
        default_cols = [
            "rank", "player", "player_id", "team", "wpa", "wpa_g",
            "events", "plus_events", "minus_events", "games"
        ]
        if res.get("ok"):
            if isinstance(raw_rows, dict) and "leaders" in raw_rows and isinstance(raw_rows["leaders"], list):
                rows = raw_rows["leaders"]
            elif isinstance(raw_rows, list):
                rows = raw_rows
            else:
                rows = []
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return res

    @tool("get_comps", description=_orig_get_comps.description)
    def get_comps(player_id: str | int, season: str | None = None, k: int = 5) -> dict:
        """Nearest statistical neighbors by per-36 + advanced shape. Same-season only."""
        try:
            res = _orig_get_comps.invoke({"player_id": player_id, "season": season, "k": k})
            if not isinstance(res, dict):
                res = {"tool": "get_comps", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_comps", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        rows = res.get("rows")
        default_cols = [
            "PLAYER", "PLAYER_ID", "TEAM", "season", "era", "similarity",
            "archetype", "shared_archetype", "drivers"
        ]
        if not (res.get("ok") and isinstance(rows, list)):
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return res

    @tool("get_lineup_stats", description=_orig_get_lineup_stats.description)
    def get_lineup_stats(team: str | int, season: str | None = None,
                         min_possessions: int = 100, include_small: bool = False,
                         limit: int = 10) -> dict:
        """Five-man lineup ratings with sample floors. Names, abbrevs, or ids."""
        try:
            res = _orig_get_lineup_stats.invoke({
                "team": team, "season": season, "min_possessions": min_possessions,
                "include_small": include_small, "limit": limit
            })
            if not isinstance(res, dict):
                res = {"tool": "get_lineup_stats", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_lineup_stats", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        rows = res.get("rows")
        default_cols = [
            "GROUP_NAME", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING", "POSS"
        ]
        if not (res.get("ok") and isinstance(rows, list)):
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return res

    @tool("get_win_prob", description=_orig_get_win_prob.description)
    def get_win_prob(team_a: str, team_b: str, season: str | None = None,
                     home_abbrev: str = "") -> dict:
        """Real ELO win probability between two abbreviations. Neutral unless home_abbrev matches a side."""
        try:
            res = _orig_get_win_prob.invoke({
                "team_a": team_a, "team_b": team_b, "season": season, "home_abbrev": home_abbrev
            })
            if not isinstance(res, dict):
                res = {"tool": "get_win_prob", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_win_prob", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team_a", "team_b", "win_prob_a", "win_prob_b", "elo_a", "elo_b"]
        raw_rows = res.get("rows")
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                win_prob = raw_rows.get("win_prob") or {}
                a = (team_a or "").upper()
                b = (team_b or "").upper()
                p_a = win_prob.get(a)
                p_b = win_prob.get(b)
                if p_a is None and p_b is None and len(win_prob) >= 2:
                    keys = list(win_prob.keys())
                    p_a = win_prob.get(keys[0])
                    p_b = win_prob.get(keys[1])
                ra = raw_rows.get("elo_a")
                rb = raw_rows.get("elo_b")
                rows = [{
                    "team_a": a,
                    "team_b": b,
                    "win_prob_a": p_a,
                    "win_prob_b": p_b,
                    "elo_a": ra,
                    "elo_b": rb,
                }]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
            else:
                rows = []
        else:
            rows = []

        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_on_off", description=_orig_get_on_off.description)
    def get_on_off(player_id: str | int, team_id: str | int, season: str | None = None) -> dict:
        """On and off splits for one player on one team. Possession level."""
        try:
            res = _orig_get_on_off.invoke({
                "player_id": player_id, "team_id": team_id, "season": season
            })
            if not isinstance(res, dict):
                res = {"tool": "get_on_off", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_on_off", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["Stat", "On", "Off", "On-Off"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_shot_zones", description=_orig_get_shot_zones.description)
    def get_shot_zones(player_id: str | int, season: str | None = None, min_attempts: int = 50) -> dict:
        """Zone splits for one player id: rim, midrange, three with shares."""
        try:
            res = _orig_get_shot_zones.invoke({
                "player_id": player_id, "season": season, "min_attempts": min_attempts
            })
            if not isinstance(res, dict):
                res = {"tool": "get_shot_zones", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_shot_zones", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["zone", "attempts", "makes", "fg_pct", "share_pct"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_four_factors", description=_orig_get_four_factors.description)
    def get_four_factors(team: str = "", season: str | None = None) -> dict:
        """Team four factors breakdown (eFG%, TOV%, ORB%, FT rate, plus defensive mirrors)."""
        try:
            res = _orig_get_four_factors.invoke({"team": team, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_four_factors", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_four_factors", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = [
            "team", "season", "efg_pct", "tov_pct", "orb_pct", "ft_rate",
            "def_efg_pct", "def_tov_pct", "def_orb_pct", "def_ft_rate"
        ]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_clutch_stats", description=_orig_get_clutch_stats.description)
    def get_clutch_stats(player: str = "", team: str = "", season: str | None = None, min_games: int = 5) -> dict:
        """NBA clutch statistics (last 5 min, margin <= 5) for player or team scope."""
        scope = "team" if (team and not player) else "player"
        args = {"scope": scope, "season": season}
        if player:
            args["player"] = player
        try:
            res = _orig_get_clutch_stats.invoke(args)
            if not isinstance(res, dict):
                res = {"tool": "get_clutch_stats", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_clutch_stats", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "season", "pts", "reb", "ast", "fg_pct", "min"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
            if team and scope == "team":
                abbr = team.upper()
                filtered = [r for r in rows if r.get("TEAM_ABBREVIATION") == abbr or r.get("team") == abbr]
                if filtered:
                    rows = filtered
            if min_games:
                rows = [r for r in rows if (r.get("GP") or 0) >= min_games]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_competitive_ratings", description=_orig_get_competitive_ratings.description)
    def get_competitive_ratings(team: str = "league", season: str | None = None,
                                blowout_margin: float = 20, min_games: int = 10) -> dict:
        """Competitive Margin of Victory (MOV excluding blowouts)."""
        try:
            res = _orig_get_competitive_ratings.invoke({
                "team": team, "season": season, "blowout_margin": blowout_margin, "min_games": min_games
            })
            if not isinstance(res, dict):
                res = {"tool": "get_competitive_ratings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_competitive_ratings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "team_name", "games", "mov", "competitive_mov", "padding_delta"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_hustle", description=_orig_get_hustle.description)
    def get_hustle(scope: str = "player", season: str | None = None) -> dict:
        """NBA hustle leaders for player or team scope."""
        try:
            res = _orig_get_hustle.invoke({"scope": scope, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_hustle", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_hustle", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = [
            "player_name", "team_abbreviation", "contested_shots",
            "deflections", "charges_drawn", "screen_assists"
        ]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_injuries", description=_orig_get_injuries.description)
    def get_injuries(team: str = "", player: str = "", season: str | None = None) -> dict:
        """NBA injury and availability report."""
        try:
            res = _orig_get_injuries.invoke({"team": team, "player": player, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_injuries", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_injuries", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "status", "injury", "description"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_award_results", description=_orig_get_award_results.description)
    def get_award_results(view: str = "winner", award: str = "mvp",
                          season: str | None = None, player: str = "") -> dict:
        """Historical recorded NBA award voting results."""
        try:
            args: dict[str, Any] = {"view": view, "award": award, "season": season}
            if player:
                args["player"] = player
            res = _orig_get_award_results.invoke(args)
            if not isinstance(res, dict):
                res = {"tool": "get_award_results", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_award_results", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "award", "season", "rank", "share", "votes"]
        raw_rows = res.get("rows")
        if res.get("ok"):
            if isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
            elif isinstance(raw_rows, dict):
                rows = [
                    {"award": k, **v} if isinstance(v, dict) else {"award": k, "value": v}
                    for k, v in raw_rows.items()
                ]
            else:
                rows = []
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_briefing", description=_orig_get_briefing.description)
    def get_briefing(game_date: str = "", season: str | None = None) -> dict:
        """Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest."""
        try:
            res = _orig_get_briefing.invoke({
                "game_date": game_date, "season": season
            })
            if not isinstance(res, dict):
                res = {"tool": "get_briefing", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_briefing", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["date", "matchup", "score", "status", "top_scorer", "top_pts"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                date_val = raw_rows.get("date", "")
                games = raw_rows.get("games")
                top_scorers = raw_rows.get("top_scorers")
                # Flatten games into row dicts if available
                if isinstance(games, list) and games:
                    for g in games:
                        if isinstance(g, dict):
                            row = {"date": date_val, **g}
                            rows.append(row)
                # Or include top scorers if games is empty
                if not rows and isinstance(top_scorers, list) and top_scorers:
                    for s in top_scorers:
                        if isinstance(s, dict):
                            row = {"date": date_val, **s}
                            rows.append(row)
                # If both are empty or rows is empty, create at least a summary row if date is present
                if not rows and date_val:
                    rows = [{"date": date_val, "games_count": 0, "status": "no games scheduled or completed"}]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]

        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        return sanitize_for_wire(res)

    @tool("get_standings", description=_orig_get_standings.description)
    def get_standings(season: str | None = None) -> dict:
        """NBA regular-season conference and league standings for any season."""
        try:
            res = _orig_get_standings.invoke({"season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_standings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_standings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "wins", "losses", "pct", "conference", "division", "gb"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_rest", description=_orig_get_rest.description)
    def get_rest(team_abbrev: str = "", season: str | None = None) -> dict:
        """Back-to-back and rest-day schedule splits for any team."""
        try:
            res = _orig_get_rest.invoke({"team_abbrev": team_abbrev, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_rest", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_rest", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "rest_days", "games", "wins", "losses", "win_pct"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                buckets = raw_rows.get("rest_buckets")
                if isinstance(buckets, dict):
                    team = team_abbrev.upper() if team_abbrev else ""
                    for bucket_name, b_val in buckets.items():
                        if isinstance(b_val, dict):
                            rows.append({
                                "team": team,
                                "rest_days": bucket_name,
                                "games": b_val.get("games", 0),
                                "wins": b_val.get("wins", 0),
                                "losses": b_val.get("losses", 0),
                                "win_pct": b_val.get("win_pct"),
                            })
                else:
                    for k, v in raw_rows.items():
                        if isinstance(v, dict):
                            rows.append({"team": team_abbrev.upper() if team_abbrev else "", "rest_days": k, **v})
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]

        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_team_trajectory", description=_orig_get_team_trajectory.description)
    def get_team_trajectory(team: str = "", through_season: str | None = None, seasons_back: int = 5) -> dict:
        """Multi-season regular-season records and win percentages for any team."""
        try:
            res = _orig_get_team_trajectory.invoke({
                "team": team, "through_season": through_season, "seasons": seasons_back
            })
            if not isinstance(res, dict):
                res = {"tool": "get_team_trajectory", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_team_trajectory", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["season", "team", "wins", "losses", "win_pct"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)


    @tool("get_ratings", description=_orig_get_ratings.description)
    def get_ratings(season: str | None = None, team: str = "",
                    requested_metric: str = "", ranking_direction: str = "") -> dict:
        """Team offensive, defensive, net ratings, and pace (league-wide or team specific)."""
        try:
            res = _orig_get_ratings.invoke({
                "season": season,
                "team": team,
                "requested_metric": requested_metric,
                "ranking_direction": ranking_direction,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_ratings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_ratings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "off_rating", "def_rating", "net_rating", "pace", "wins", "losses"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_rookie_leaders", description=_orig_get_rookie_leaders.description)
    def get_rookie_leaders(stat: str = "ppg", min_value: float = 0,
                           min_gp: int = 10, limit: int = 15,
                           season: str | None = None) -> dict:
        """Current rookie class leaderboard (first-year NBA players only, verified against historical seasons)."""
        try:
            res = _orig_get_rookie_leaders.invoke({
                "stat": stat,
                "min_value": min_value,
                "min_gp": min_gp,
                "limit": limit,
                "season": season,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_rookie_leaders", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_rookie_leaders", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "age", "gp", "mpg", "ppg", "rpg", "apg"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_cap_ledger", description=_orig_get_cap_ledger.description)
    def get_cap_ledger(team: str = "", season: str | None = None) -> dict:
        """Payroll, luxury tax position, and first/second apron room for one team."""
        try:
            fields = getattr(getattr(_orig_get_cap_ledger, "args_schema", None), "model_fields", {})
            call_args: dict[str, Any] = {}
            if "team_abbrev" in fields:
                call_args["team_abbrev"] = team
            if "team" in fields or not fields:
                call_args["team"] = team
            if "season" in fields and season is not None:
                call_args["season"] = season
            try:
                res = _orig_get_cap_ledger.invoke(call_args)
            except Exception:
                fallback = {"team_abbrev": team} if "team" in call_args else {"team": team}
                res = _orig_get_cap_ledger.invoke(fallback)
            if not isinstance(res, dict):
                res = {"tool": "get_cap_ledger", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_cap_ledger", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "total_salary", "cap_space", "tax_room", "first_apron_room", "second_apron_room"]
        raw_rows = res.get("rows")
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
            else:
                rows = []
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_leaders", description=_orig_get_leaders.description)
    def get_leaders(stat_category: str = "PTS", ranking_direction: str = "desc",
                    min_attempts: int = 0, season: str | None = None) -> dict:
        """Qualified league statistical leaders for any category."""
        try:
            res = _orig_get_leaders.invoke({
                "stat_category": stat_category,
                "ranking_direction": ranking_direction,
                "min_attempts": min_attempts,
                "season": season,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_leaders", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_leaders", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "stat_category", "value", "gp"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_lineup_leaders", description=_orig_get_lineup_leaders.description)
    def get_lineup_leaders(min_minutes: int = 100, limit: int = 10, season: str | None = None) -> dict:
        """League-wide 5-man lineup net-rating leaderboard with minutes qualification floor."""
        try:
            res = _orig_get_lineup_leaders.invoke({
                "min_minutes": min_minutes,
                "limit": limit,
                "season": season,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_lineup_leaders", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_lineup_leaders", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team_abbreviation", "group_name", "gp", "min", "plus_minus", "net48"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_playoffs", description=_orig_get_playoffs.description)
    def get_playoffs(season: str | None = None) -> dict:
        """Playoff series wins per team, finals matchup, and champion for any season."""
        try:
            res = _orig_get_playoffs.invoke({"season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_playoffs", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_playoffs", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "w", "l", "champion"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                champ = raw_rows.get("champion", "")
                wins = raw_rows.get("wins")
                if isinstance(wins, list) and wins:
                    for w in wins:
                        if isinstance(w, dict):
                            rows.append({
                                "team": w.get("team"),
                                "w": w.get("w"),
                                "l": w.get("l"),
                                "champion": champ,
                            })
                elif champ:
                    rec = raw_rows.get("champion_record") or {}
                    rows.append({
                        "team": champ,
                        "w": rec.get("w"),
                        "l": rec.get("l"),
                        "champion": champ,
                    })
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]

        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_team_leaders", description=_orig_get_team_leaders.description)
    def get_team_leaders(stat_category: str = "AST", season: str | None = None) -> dict:
        """Team totals leaderboard for a counting stat (PTS, REB, AST, STL, BLK)."""
        try:
            res = _orig_get_team_leaders.invoke({"stat_category": stat_category, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_team_leaders", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_team_leaders", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["rank", "team", "abbrev", "stat", "gp", "per_game"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_team_compare", description=_orig_get_team_compare.description)
    def get_team_compare(stat_category: str = "PTS", top: int = 3, season: str | None = None) -> dict:
        """Top-N team comparison on a counting stat joined with win-loss records."""
        try:
            res = _orig_get_team_compare.invoke({"stat_category": stat_category, "top": top, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_team_compare", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_team_compare", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["rank", "team", "abbrev", "stat", "gp", "per_game", "record"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_elo_standings", description=_orig_get_elo_standings.description)
    def get_elo_standings(season: str | None = None, opponent: str | None = None, limit: int = 30) -> dict:
        """ELO power ratings as standings with implied win pct, win equivalents, and Elo-implied spreads."""
        try:
            res = _orig_get_elo_standings.invoke({"season": season, "opponent": opponent, "limit": limit})
            if not isinstance(res, dict):
                res = {"tool": "get_elo_standings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_elo_standings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["rank", "abbr", "elo", "games", "w", "l", "elo_win_pct", "win_equiv", "elo_implied_spread"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_draft_board", description=_orig_get_draft_board.description)
    def get_draft_board(season: str = "2025") -> dict:
        """Blended draft board rankings combining college production and combine testing."""
        try:
            con = _store.connect(read_only=True)
            try:
                con.execute("SELECT 1 FROM silver_combine LIMIT 0")
            finally:
                con.close()
            if os.environ.get("PI_OFFLINE"):
                raise RuntimeError("offline mode: live fetching disabled")
            res = _orig_get_draft_board.invoke({"season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_draft_board", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_draft_board", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["rank", "player", "pos", "school", "draft_score", "bpm"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_combine", description=_orig_get_combine.description)
    def get_combine(season: str = "2025") -> dict:
        """Anthropometric measurements (height, wingspan, reach, weight) and athletic drills."""
        try:
            con = _store.connect(read_only=True)
            try:
                con.execute("SELECT 1 FROM silver_combine LIMIT 0")
            finally:
                con.close()
            if os.environ.get("PI_OFFLINE"):
                raise RuntimeError("offline mode: live fetching disabled")
            res = _orig_get_combine.invoke({"season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_combine", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_combine", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "pos", "height_wo_shoes", "height_w_shoes", "weight", "wingspan", "standing_reach"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_young_player_usage", description=_orig_get_young_player_usage.description)
    def get_young_player_usage(max_age: int = 22, min_minutes: int = 1000, season: str | None = None) -> dict:
        """Usage-rate leaderboard for young players with customizable age ceilings and minute floors."""
        try:
            con = _store.connect(read_only=True)
            try:
                con.execute("SELECT 1 FROM silver_advanced LIMIT 0")
            finally:
                con.close()
            res = _orig_get_young_player_usage.invoke({
                "max_age": max_age,
                "min_minutes": min_minutes,
                "season": season,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_young_player_usage", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_young_player_usage", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["RANK", "PLAYER", "TEAM", "AGE", "GP", "MPG", "MINUTES", "USG_PCT"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    # Deliberately do not export WAREHOUSE_TOOLS, which includes mutators.
    return {
        item.name: item for item in (
            sql_exec,
            warehouse_schema,
            get_rapm,
            get_game_prediction,
            get_wpa_leaders,
            get_comps,
            get_lineup_stats,
            get_win_prob,
            get_on_off,
            get_shot_zones,
            get_four_factors,
            get_clutch_stats,
            get_competitive_ratings,
            get_hustle,
            get_injuries,
            get_award_results,
            get_briefing,
            get_standings,
            get_rest,
            get_team_trajectory,
            get_ratings,
            get_rookie_leaders,
            get_cap_ledger,
            get_leaders,
            get_lineup_leaders,
            get_playoffs,
            get_team_leaders,
            get_team_compare,
            get_elo_standings,
            get_draft_board,
            get_combine,
            get_young_player_usage,
        )
    }


def sanitize_for_wire(val: Any) -> Any:
    """Recursively sanitize data structures for NaN-safe JSON encoding."""
    if val is None or isinstance(val, (str, bool, int)):
        return val
    if isinstance(val, (float, np.floating)):
        return None if (math.isnan(val) or math.isinf(val)) else float(val)
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, np.ndarray):
        return sanitize_for_wire(val.tolist())
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return int(val) if val.as_tuple().exponent >= 0 else float(val)
    if isinstance(val, dict):
        return {str(k): sanitize_for_wire(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [sanitize_for_wire(x) for x in val]
    return val


def wire_default(value):
    # Dataset rows previously crossed FastAPI's JSON encoder. Preserve those
    # date and numeric representations at the explicit MCP boundary.
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value.as_tuple().exponent >= 0 else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if (math.isnan(value) or math.isinf(value)) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    raise TypeError(f"Data result is not JSON serializable: {type(value).__name__}")


async def main():
    warehouse = Path(os.environ["DIME_WAREHOUSE"])
    if not warehouse.is_absolute() or not warehouse.is_file():
        raise ValueError("DIME_WAREHOUSE must be an explicit existing absolute file")
    from analyst.direct_data import internal_catalogue
    tools = {**catalogue(), **internal_catalogue()}
    async def list_tools(_ctx, _params):
        return ListToolsResult(tools=[Tool(name=item.name, description=item.description,
                     inputSchema=item.args_schema.model_json_schema())
                for item in tools.values()])

    async def call_tool(_ctx, params):
        try:
            # SQL's existing implementation performs blocking DuckDB work. Keep
            # MCP responsive while independent read-only calls execute.
            result = await asyncio.to_thread(
                lambda: asyncio.run(tools[params.name].ainvoke(params.arguments or {})))
            sanitized = sanitize_for_wire(result)
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(sanitized, allow_nan=False, default=wire_default))])
        except Exception as error:
            return CallToolResult(isError=True, content=[TextContent(
                type="text", text=f"{type(error).__name__}: {error}")])

    server = Server("dime-data-engine", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
