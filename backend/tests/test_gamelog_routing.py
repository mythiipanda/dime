"""Game-log fast-path routing tests.

Demo bug: the planner free-formed a game-log question into text_to_sql,
hit "unknown table or column" on silver_player_gamelogs, and streamed
the red error row before recovering. The triage fast-path in app/graph.py
routes clean single-turn single-player game-log asks straight to
search_game_logs instead.

All hermetic: _triage_seed is driven directly and the real
search_game_logs runs against the local warehouse. No LLM, no network.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph  # noqa: E402
from app.graph import (  # noqa: E402
    DEEP_TOOL_ROUNDS,
    MAX_TOOL_ROUNDS,
    _flatten_tables,
    _gamelog_args,
    _triage_seed,
)


def _drain(question, history=None):
    async def _go():
        state = {"question": question, "history": history or [],
                 "tool_results": [], "calls_made": [], "round": 0}
        async for _e in _triage_seed(question, "primary", "model", state):
            pass
        return state

    return asyncio.run(_go())


def _tool_names(state):
    return [c.split(":")[0] for c in state["calls_made"]]


def _gamelog_args_of(state):
    for c in state["calls_made"]:
        name, _, payload = c.partition(":")
        if name == "search_game_logs":
            return json.loads(payload)
    return None


def test_40_point_games_routes_to_search_game_logs():
    st = _drain("Show me Anthony Edwards' 40-point games this season")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "Anthony Edwards"
    assert args["min_points"] == 40
    assert len(_tool_names(st)) == 1
    # Decisive hit: planner rounds exhausted.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_triple_double_phrasing_sets_flag():
    st = _drain("How many triple-doubles does Luka Doncic have this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "Luka Dončić"
    assert args.get("triple_double") is True
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_double_double_phrasing_sets_flag():
    st = _drain("Show me Nikola Jokic's double-doubles this month")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args.get("double_double") is True
    assert "triple_double" not in args


def test_league_leaders_routes_to_search_game_logs():
    # Ticket B: "who had the most 50-point games this season?" names no
    # player, so the player-scoped fast-path can't fire; the
    # league-wide fast-path must answer from the warehouse instead of
    # letting the planner improvise SQL.
    st = _drain("who had the most 50-point games this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "league-wide fast-path did not fire"
    assert args.get("league_wide") is True
    assert args["min_points"] == 50
    assert "player" not in args
    assert len(_tool_names(st)) == 1
    # Decisive hit: planner rounds exhausted.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)
    # Leaders actually returned as evidence.
    rows = st["tool_results"][0]["rows"][0]["rows"]
    assert rows["league_wide"] is True
    assert rows["total_players"] >= 1
    assert rows["leaders"][0]["count"] >= 1


def test_which_player_most_triple_doubles_routes_league_wide():
    st = _drain("which player had the most triple-doubles this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "league-wide fast-path did not fire"
    assert args.get("league_wide") is True
    assert args.get("triple_double") is True


def test_existence_did_anyone_score_routes_league_wide():
    # Gap A: existence phrasing names no player, so the player-scoped
    # fast-path can't fire; it must take the league-wide fast-path
    # instead of falling through to the planner.
    st = _drain("did anyone score 60 points this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "league-wide fast-path did not fire"
    assert args.get("league_wide") is True
    assert args["min_points"] == 60
    assert "player" not in args
    assert len(_tool_names(st)) == 1
    # Decisive hit: planner rounds exhausted.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_existence_was_there_game_routes_league_wide():
    st = _drain("was there a 60-point game this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "league-wide fast-path did not fire"
    assert args.get("league_wide") is True
    assert args["min_points"] == 60
    assert len(_tool_names(st)) == 1
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_existence_bare_dropped_number_sets_min_points():
    # "has anyone dropped 50 this season?" has no "points" word; the
    # arg parser must still extract the floor from the scoring verb.
    args = _gamelog_args("has anyone dropped 50 this season?", None, [])
    assert args["min_points"] == 50


def test_team_most_50pt_games_routes_team_wide():
    # Gap B: team-population phrasing must group by team, not player.
    st = _drain("which team had the most 50-point games this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "team fast-path did not fire"
    assert args.get("team_wide") is True
    assert args["min_points"] == 50
    assert "player" not in args
    assert len(_tool_names(st)) == 1
    # Decisive hit: planner rounds exhausted.
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)
    rows = st["tool_results"][0]["rows"][0]["rows"]
    assert rows["team_wide"] is True
    leaders = rows["leaders"]
    assert len(leaders) >= 1
    assert all({"team_abbr", "team", "count"} <= set(l)
               for l in leaders)
    counts = [l["count"] for l in leaders]
    assert counts == sorted(counts, reverse=True)
    assert all(c >= 1 for c in counts)


def test_league_leaders_still_player_grouped_not_team_wide():
    # Negative: the plain leaders ask keeps per-player grouping.
    st = _drain("who had the most 50-point games this season?")
    args = _gamelog_args_of(st)
    assert args is not None, "league-wide fast-path did not fire"
    assert args.get("league_wide") is True
    assert args.get("team_wide") is not True
    rows = st["tool_results"][0]["rows"][0]["rows"]
    assert rows["league_wide"] is True
    assert rows.get("team_wide") is not True


def _rs_only_player():
    """A (name, id) with 2025-26 regular-season rows but no playoff rows.

    The background scrape keeps filling silver_playoff_gamelogs, so no
    specific player's playoff emptiness can be hardcoded. The name is
    resolved via the static player list and verified to coerce back to
    the same warehouse id.
    """
    from app import store as _store
    from app.tools._core import coerce_player_id as _coerce
    from app.tools.splits import _resolve_name as _rname
    con = _store.connect(read_only=True)
    try:
        rows = con.execute(
            """SELECT DISTINCT rs.Player_ID FROM silver_player_gamelogs rs
               WHERE rs._season = '2025-26'
               AND NOT EXISTS (
                    SELECT 1 FROM silver_playoff_gamelogs po
                    WHERE po._season = '2025-26'
                      AND po.Player_ID = rs.Player_ID)
                LIMIT 25""").fetchall()
        for (pid,) in rows:
            name = _rname(pid, "")
            if name and _coerce(name) == pid:
                return name, pid
    finally:
        con.close()
    return None


def test_playoff_phrasing_sets_playoffs_flag():
    # Ticket A: the fast-path must not silently drop "in the playoffs".
    q = "Did Jalen Brunson have any triple-doubles in the playoffs?"
    args = _gamelog_args(q, "Jalen Brunson", [])
    assert args.get("playoffs") is True
    assert args.get("triple_double") is True
    st = _drain(q)
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args.get("playoffs") is True
    # A player with no playoff rows gets an explicit refusal, never a
    # silent regular-season 0. The player is picked dynamically (see
    # _rs_only_player) because the scrape keeps filling the playoff table.
    found = _rs_only_player()
    if found is None:
        import pytest as _pt
        _pt.skip("no regular-season-only player in warehouse")
    pname, _pid = found
    st = _drain(f"Did {pname} have any triple-doubles in the playoffs?")
    out = st["tool_results"][-1]
    assert out["ok"] is False
    assert "playoff" in out["error"]


def test_postseason_phrasing_sets_playoffs_flag():
    args = _gamelog_args(
        "Show me Jayson Tatum's 30-point games in the postseason",
        "Jayson Tatum", [])
    assert args.get("playoffs") is True
    assert args["min_points"] == 30


def test_multi_player_does_not_fire():
    st = _drain("who had more 40-point games, LeBron James or Jayson Tatum?")
    assert "search_game_logs" not in _tool_names(st)


def test_averages_phrasing_does_not_fire():
    st = _drain("what does Shai Gilgeous-Alexander average in points "
                "this season")
    assert "search_game_logs" not in _tool_names(st)


def test_opponent_arg_mapping():
    q = "Show me Jayson Tatum's 30-point games vs the Lakers this season"
    args = _gamelog_args(q, "Jayson Tatum", ["Los Angeles Lakers"])
    assert args["opponent"] == "Los Angeles Lakers"
    assert args["min_points"] == 30


def test_month_and_home_arg_mapping():
    q = "LeBron James' triple-doubles at home in March"
    args = _gamelog_args(q, "LeBron James", [])
    assert args.get("triple_double") is True
    assert args.get("home_away") == "home"
    assert args.get("month") == "march"


def _has_rows(rows):
    if isinstance(rows, list):
        return len(rows) > 0
    if isinstance(rows, dict):
        return any(_has_rows(v) for v in rows.values())
    return bool(rows)


def test_fastpath_result_passes_analytics_evidence_gate():
    st = _drain("Show me Anthony Edwards' 40-point games this season")
    evidenced = [
        r for r in _flatten_tables(st["tool_results"])
        if isinstance(r, dict) and _has_rows(r.get("rows"))
        and r.get("tool", "") not in ("resolve_entity", "search_nba")
    ]
    assert len(evidenced) >= 1


def test_best_game_phrasing_routes_to_search_game_logs():
    st = _drain("how many points did ant score in his best game")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "Anthony Edwards"
    assert args.get("best_game") is True
    assert st["round"] in (MAX_TOOL_ROUNDS, DEEP_TOOL_ROUNDS)


def test_career_high_phrasing_routes_despite_no_rx():
    # "career" trips _GAMELOG_NO_RX (meant for career averages); the
    # best-game exemption must still route "career high".
    st = _drain("what is lebron's career high in points")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "LeBron James"
    assert args.get("best_game") is True


def test_season_high_and_most_points_phrasing_route():
    for q in ("what was tatum's season high in points",
              "how many points did curry score in his most points game"):
        st = _drain(q)
        args = _gamelog_args_of(st)
        assert args is not None, f"fast-path did not fire for {q!r}"
        assert args.get("best_game") is True


def test_space_separated_point_threshold_routes():
    st = _drain("lebron 40 point games")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["player"] == "LeBron James"
    assert args["min_points"] == 40


def test_pt_abbreviation_routes():
    st = _drain("lebron 40pt games")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["min_points"] == 40


def test_hyphenated_point_threshold_still_routes():
    st = _drain("lebron 40-point games")
    args = _gamelog_args_of(st)
    assert args is not None, "fast-path did not fire"
    assert args["min_points"] == 40


def test_best_game_tool_returns_max_pts_row():
    from app.tools.gamelog import _load_player_games, search_game_logs

    out = search_game_logs.invoke({"player": "Anthony Edwards",
                                   "best_game": True})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["returned"] == 1
    assert len(rows["matches"]) == 1
    top = rows["matches"][0]
    best = max(_load_player_games(out["rows"]["player_id"], "2025-26"),
               key=lambda g: g["pts"])
    assert top["pts"] == best["pts"]
    assert top["date"] == best["date"].isoformat()


def test_result_rows_counts_game_rows_not_metadata_keys():
    from app.graph import _result_rows

    out = {"tool": "search_game_logs", "ok": True, "rows": {
        "player": "LeBron James", "player_id": 2544,
        "player_team": "LAL", "filters": "40+ points",
        "total": 2, "returned": 2, "capped": False,
        "matches": [{"pts": 42}, {"pts": 40}],
    }}
    assert _result_rows(out) == 2
    out["rows"]["matches"] = [{"pts": 42}]
    assert _result_rows(out) == 1
