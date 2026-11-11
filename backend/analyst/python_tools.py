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
        get_contract_value as _orig_get_contract_value,
        get_trade_check as _orig_get_trade_check,
        get_trade_value as _orig_get_trade_value,
        get_situational_splits as _orig_get_situational_splits,
        get_playoff_sim as _orig_get_playoff_sim,
        get_playoff_team_ratings as _orig_get_playoff_team_ratings,
        get_player_risers as _orig_get_player_risers,
        get_standings_deep as _orig_get_standings_deep,
        get_warehouse_freshness as _orig_get_warehouse_freshness,
        get_finder as _orig_get_finder,
        get_draft_model as _orig_get_draft_model,
        get_leaderboard_deltas as _orig_get_leaderboard_deltas,
        get_player_ratings as _orig_get_player_ratings,
        get_risers as _orig_get_risers,
        get_team_four_factors as _orig_get_team_four_factors,
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
        try:
            _, columns = _get_warehouse_schema()
        except Exception as exc:
            return sanitize_for_wire({
                "tool": "warehouse_schema",
                "ok": False,
                "error": f"warehouse unavailable: {exc}",
                "tables": {},
                "columns": [],
                "catalog_scope": {
                    "kind": "declared_read_only_tables",
                    "exhaustive_warehouse_inventory": False,
                    "available_table_count": 0,
                    "returned_table_count": 0,
                    "negative_claim_scope": "warehouse unavailable",
                },
            })
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
                return sanitize_for_wire({
                    "tool": "warehouse_schema",
                    "ok": False,
                    "error": (
                        "unknown declared table(s) in tables selection: "
                        f"{', '.join(unknown)}; omit tables for the full declared schema"
                    ),
                    "tables": {},
                    "columns": [],
                })
            if not selected:
                return sanitize_for_wire({
                    "tool": "warehouse_schema",
                    "ok": False,
                    "error": (
                        "tables selection must name at least one declared table; "
                        "omit tables for the full declared schema"
                    ),
                    "tables": {},
                    "columns": [],
                })
        annotated = annotate_schema(
            {"tables": {name: columns[name] for name in selected}})
        annotated["catalog_scope"] = {
            "kind": "declared_read_only_tables",
            "exhaustive_warehouse_inventory": False,
            "available_table_count": len(columns),
            "returned_table_count": len(selected),
            "negative_claim_scope": "returned declared tables and columns only",
        }
        annotated["tool"] = "warehouse_schema"
        annotated["ok"] = True
        return sanitize_for_wire(annotated)

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

    @tool("get_contract_value", description=_orig_get_contract_value.description)
    def get_contract_value(season: str | None = None, min_gp: int = 20, team: str = "", player: str = "") -> dict:
        """Contract value residuals from production vs salary."""
        try:
            res = _orig_get_contract_value.invoke({
                "season": season,
                "min_gp": min_gp,
                "team": team,
                "player": player,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_contract_value", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_contract_value", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "salary", "salary_hat", "residual", "gp"]
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

    @tool("get_trade_check", description=_orig_get_trade_check.description)
    def get_trade_check(team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "", season: str | None = None) -> dict:
        """CBA trade legality check under 2023 CBA apron and salary matching rules."""
        try:
            res = _orig_get_trade_check.invoke({
                "team_a": team_a,
                "players_a": players_a,
                "team_b": team_b,
                "players_b": players_b,
                "season": season,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_trade_check", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_trade_check", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["side", "team", "payroll", "outgoing", "allowed_incoming", "legal", "issues"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                legal_val = raw_rows.get("legal")
                issues_val = raw_rows.get("issues")
                for side_key in ("team_a", "team_b"):
                    side_data = raw_rows.get(side_key)
                    if isinstance(side_data, dict):
                        rows.append({
                            "side": side_key,
                            "team": side_data.get("team", ""),
                            "payroll": side_data.get("payroll"),
                            "outgoing": side_data.get("out") if "out" in side_data else side_data.get("outgoing"),
                            "allowed_incoming": side_data.get("allowed_in") if "allowed_in" in side_data else side_data.get("allowed_incoming"),
                            "legal": legal_val,
                            "issues": issues_val,
                        })
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_trade_value", description=_orig_get_trade_value.description)
    def get_trade_value(team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "", picks_a: str = "", picks_b: str = "") -> dict:
        """Trade value grade: estimated production surplus value vs salary per side plus pick equity."""
        try:
            res = _orig_get_trade_value.invoke({
                "team_a": team_a,
                "players_a": players_a,
                "team_b": team_b,
                "players_b": players_b,
                "picks_a": picks_a,
                "picks_b": picks_b,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_trade_value", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_trade_value", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["side", "player", "team", "value_m", "salary_m", "residual_m"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                for side_key in ("team_a", "team_b"):
                    side_data = raw_rows.get(side_key)
                    if isinstance(side_data, dict):
                        side_team = side_data.get("team", "")
                        players = side_data.get("players")
                        if isinstance(players, list):
                            for p in players:
                                if isinstance(p, dict):
                                    sal = p.get("salary_26_27")
                                    salary_m = round(sal / 1e6, 2) if isinstance(sal, (int, float)) else p.get("salary_m")
                                    val_m = p.get("est_market_value_m") if "est_market_value_m" in p else p.get("value_m")
                                    rows.append({
                                        "side": side_key,
                                        "player": p.get("name") or p.get("player", ""),
                                        "team": p.get("team") or side_team,
                                        "value_m": val_m,
                                        "salary_m": salary_m,
                                        "residual_m": p.get("residual_m"),
                                    })
                if not rows and "verdict" in raw_rows and isinstance(raw_rows["verdict"], dict):
                    v = raw_rows["verdict"]
                    rows.append({
                        "side": "verdict",
                        "player": v.get("winner", ""),
                        "team": "",
                        "value_m": v.get("delta_m"),
                        "salary_m": None,
                        "residual_m": None,
                    })
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_situational_splits", description=_orig_get_situational_splits.description)
    def get_situational_splits(scope: str = "player", entity: str = "", season: str | None = None, clutch_seconds: int = 300, clutch_margin: int = 5, season_type: str = "regular") -> dict:
        """Clutch situational splits for one player or team across score margins, time thresholds, and venues."""
        try:
            res = _orig_get_situational_splits.invoke({
                "scope": scope,
                "entity": entity,
                "season": season,
                "clutch_seconds": clutch_seconds,
                "clutch_margin": clutch_margin,
                "season_type": season_type,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_situational_splits", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_situational_splits", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["split", "gp", "pts", "fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict) and "splits" in raw_rows and isinstance(raw_rows["splits"], list):
                rows = [r for r in raw_rows["splits"] if isinstance(r, dict)]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_playoff_sim", description=_orig_get_playoff_sim.description)
    def get_playoff_sim(season: str | None = None, sims: int = 2000) -> dict:
        """Simulated championship and finals odds from power ratings via Monte Carlo brackets."""
        try:
            res = _orig_get_playoff_sim.invoke({"season": season, "sims": sims})
            if not isinstance(res, dict):
                res = {"tool": "get_playoff_sim", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_playoff_sim", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "title_pct", "finals_pct", "sims"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                teams = raw_rows.get("teams")
                if isinstance(teams, list) and teams:
                    title_probs = raw_rows.get("title_probs") or {}
                    final_probs = raw_rows.get("final_probs") or {}
                    sims_val = raw_rows.get("sims", sims)
                    is_t_ratio = max(title_probs.values(), default=0.0) <= 1.0
                    is_f_ratio = max(final_probs.values(), default=0.0) <= 1.0
                    rows = [
                        {
                            "team": t,
                            "title_pct": round(title_probs.get(t, 0.0) * 100, 2) if is_t_ratio else round(title_probs.get(t, 0.0), 2),
                            "finals_pct": round(final_probs.get(t, 0.0) * 100, 2) if is_f_ratio else round(final_probs.get(t, 0.0), 2),
                            "sims": sims_val,
                        }
                        for t in teams
                    ]
                else:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_playoff_team_ratings", description=_orig_get_playoff_team_ratings.description)
    def get_playoff_team_ratings(season: str | None = None, limit: int = 30) -> dict:
        """Team offensive, defensive, and net ratings from playoff game logs."""
        try:
            res = _orig_get_playoff_team_ratings.invoke({"season": season, "limit": limit})
            if not isinstance(res, dict):
                res = {"tool": "get_playoff_team_ratings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_playoff_team_ratings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["team", "games", "off_rating", "def_rating", "net_rating"]
        raw_rows = res.get("rows")
        if res.get("ok") and isinstance(raw_rows, list):
            rows = [r for r in raw_rows if isinstance(r, dict)]
        elif res.get("ok") and isinstance(raw_rows, dict):
            rows = [raw_rows]
        else:
            rows = []
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_player_risers", description=_orig_get_player_risers.description)
    def get_player_risers(season: str | None = None, n: int = 10) -> dict:
        """Player risers and fallers: last-N games scoring and efficiency versus season baseline."""
        try:
            res = _orig_get_player_risers.invoke({"season": season, "n": n})
            if not isinstance(res, dict):
                res = {"tool": "get_player_risers", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_player_risers", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["PLAYER", "TEAM", "GP", "SEASON_PPG", "PPG_DELTA", "TREND"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                for trend_key, trend_label in (("risers", "riser"), ("fallers", "faller")):
                    trend_items = raw_rows.get(trend_key)
                    if isinstance(trend_items, list):
                        for item in trend_items:
                            if isinstance(item, dict):
                                row = dict(item)
                                row["TREND"] = trend_label
                                rows.append(row)
                if not rows:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_standings_deep", description=_orig_get_standings_deep.description)
    def get_standings_deep(season: str | None = None, top: int = 5) -> dict:
        """Standings deep cuts: clutch records, comeback kings, blown leads, and monthly momentum."""
        try:
            res = _orig_get_standings_deep.invoke({"season": season, "top": top})
            if not isinstance(res, dict):
                res = {"tool": "get_standings_deep", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_standings_deep", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["TEAM", "CATEGORY", "W", "L", "PCT", "RECORD"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                for cat, items in raw_rows.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                row = dict(item)
                                row["CATEGORY"] = cat
                                if "RECORD" not in row and "W" in row and "L" in row:
                                    row["RECORD"] = f"{row['W']}-{row['L']}"
                                rows.append(row)
                    elif isinstance(items, dict):
                        for sub_cat, sub_items in items.items():
                            if isinstance(sub_items, list):
                                for item in sub_items:
                                    if isinstance(item, dict):
                                        row = dict(item)
                                        row["CATEGORY"] = f"{cat}_{sub_cat}"
                                        if "RECORD" not in row and "W" in row and "L" in row:
                                            row["RECORD"] = f"{row['W']}-{row['L']}"
                                        rows.append(row)
                if not rows:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)



    @tool("get_warehouse_freshness", description=_orig_get_warehouse_freshness.description)
    def get_warehouse_freshness() -> dict:
        """Warehouse freshness and data recency panel across all silver tables."""
        try:
            res = _orig_get_warehouse_freshness.invoke({})
            if not isinstance(res, dict):
                res = {"tool": "get_warehouse_freshness", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_warehouse_freshness", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["table", "rows", "last_fetch", "stale"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
            elif isinstance(raw_rows, dict):
                rows = [raw_rows]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_finder", description=_orig_get_finder.description)
    def get_finder(mode: str = "streak", team_abbrev: str = "", opponent: str = "", season: str | None = None, window: int = 5) -> dict:
        """Historical multi-season search across streaks, versus, span, player_streak, and head2head."""
        try:
            res = _orig_get_finder.invoke({
                "mode": mode, "team_abbrev": team_abbrev, "opponent": opponent,
                "season": season, "window": window,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_finder", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_finder", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["mode", "team", "opponent", "streak", "games", "result"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                if "a" in raw_rows and "b" in raw_rows and isinstance(raw_rows.get("a"), dict):
                    for side_key in ("a", "b"):
                        side_val = raw_rows.get(side_key)
                        if isinstance(side_val, dict):
                            rows.append({"entry": side_key, **side_val})
                else:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_draft_model", description=_orig_get_draft_model.description)
    def get_draft_model(season: str = "2025") -> dict:
        """Prospect star-probability classifier from college production."""
        try:
            res = _orig_get_draft_model.invoke({"season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_draft_model", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_draft_model", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["PLAYER", "TEAM", "PTS", "TS_PCT", "USG", "STAR_P"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
            elif isinstance(raw_rows, dict):
                rows = [raw_rows]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_leaderboard_deltas", description=_orig_get_leaderboard_deltas.description)
    def get_leaderboard_deltas(season: str | None = None, days: int = 7) -> dict:
        """Scoring leaderboard movers: latest snapshot vs the one from days ago."""
        try:
            res = _orig_get_leaderboard_deltas.invoke({"season": season, "days": days})
            if not isinstance(res, dict):
                res = {"tool": "get_leaderboard_deltas", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_leaderboard_deltas", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["player", "team", "rank_base", "rank_now", "rank_change", "pts_change", "trend"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                for group_key, trend_label in (("climbers", "climber"), ("fallers", "faller"), ("new_entries", "new")):
                    group_items = raw_rows.get(group_key)
                    if isinstance(group_items, list):
                        for item in group_items:
                            if isinstance(item, dict):
                                row = dict(item)
                                row["trend"] = trend_label
                                rows.append(row)
                if not rows:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)


    @tool("get_player_ratings", description=_orig_get_player_ratings.description)
    def get_player_ratings(season: str | None = None, metric: str = "offense", limit: int = 10, min_minutes: int = 1000) -> dict:
        """Qualified player on-court offensive or defensive rating leaderboard."""
        try:
            res = _orig_get_player_ratings.invoke({
                "season": season,
                "metric": metric,
                "limit": limit,
                "min_minutes": min_minutes,
            })
            if not isinstance(res, dict):
                res = {"tool": "get_player_ratings", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_player_ratings", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["PLAYER", "TEAM", "MINUTES", "RATING", "METRIC"]
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

    @tool("get_risers", description=_orig_get_risers.description)
    def get_risers(season: str | None = None, weeks: int = 4) -> dict:
        """Team risers and fallers: last-N weeks win percentage versus season win percentage."""
        try:
            res = _orig_get_risers.invoke({"season": season, "weeks": weeks})
            if not isinstance(res, dict):
                res = {"tool": "get_risers", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_risers", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = ["TEAM", "LAST10", "LAST10_PCT", "SEASON_PCT", "DELTA", "TREND"]
        raw_rows = res.get("rows")
        rows: list[dict] = []
        if res.get("ok"):
            if isinstance(raw_rows, dict):
                for trend_key, trend_label in (("risers", "riser"), ("fallers", "faller")):
                    trend_items = raw_rows.get(trend_key)
                    if isinstance(trend_items, list):
                        for item in trend_items:
                            if isinstance(item, dict):
                                row = dict(item)
                                row["TREND"] = trend_label
                                rows.append(row)
                if not rows:
                    rows = [raw_rows]
            elif isinstance(raw_rows, list):
                rows = [r for r in raw_rows if isinstance(r, dict)]
        cols = list(rows[0].keys()) if rows else default_cols
        res["rows"] = rows
        res["columns"] = cols
        res["ok"] = bool(res.get("ok", False))
        return sanitize_for_wire(res)

    @tool("get_team_four_factors", description=_orig_get_team_four_factors.description)
    def get_team_four_factors(team: str = "", season: str | None = None) -> dict:
        """Full-board or team-specific Four Factors (eFG%, TOV%, ORB%, FT rate, and defensive mirrors)."""
        try:
            res = _orig_get_team_four_factors.invoke({"team": team, "season": season})
            if not isinstance(res, dict):
                res = {"tool": "get_team_four_factors", "ok": False, "error": str(res)}
        except Exception as exc:
            res = {"tool": "get_team_four_factors", "ok": False, "error": f"{type(exc).__name__}: {exc}"}

        default_cols = [
            "TEAM", "GP", "W", "EFG_PCT", "TOV_PCT", "ORB_PCT", "FT_RATE",
            "OPP_EFG_PCT", "OPP_TOV_PCT", "DRB_PCT", "OPP_FT_RATE"
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
            get_contract_value,
            get_trade_check,
            get_trade_value,
            get_situational_splits,
            get_playoff_sim,
            get_playoff_team_ratings,
            get_player_risers,
            get_standings_deep,
            get_warehouse_freshness,
            get_finder,
            get_draft_model,
            get_leaderboard_deltas,
            get_player_ratings,
            get_risers,
            get_team_four_factors,
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
