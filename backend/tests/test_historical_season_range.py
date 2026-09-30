import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb

from shared import store

SEASONS = ("2014-15", "2024-25", "2025-26")
FLOOR = "2014-15"


def _seed_boxscores(path, seasons=SEASONS):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_boxscores ("
            "GAME_ID VARCHAR, _season VARCHAR, "
            "_source VARCHAR, _fetched_at VARCHAR)"
        )
        for i, season in enumerate(seasons):
            con.execute(
                "INSERT INTO silver_boxscores VALUES (?, ?, ?, ?)",
                [f"002{season[2:4]}000{(i + 1):03d}", season,
                 "synthetic", "2026-01-01T00:00:00Z"],
            )
    finally:
        con.close()
    return path


def _warehouse(monkeypatch, tmp_path, seasons=SEASONS):
    path = tmp_path / "synthetic.duckdb"
    _seed_boxscores(path, seasons)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    return path


def _drain_analytics(state):
    import app.graph as graph_mod

    async def _go():
        async for _ in graph_mod.analytics_agent(state):
            pass
        return state.get("analysis", "")

    return asyncio.run(_go())


def _failure_state(question, results):
    return {
        "question": question,
        "history": [],
        "calls_made": [],
        "ledger": [],
        "primary": "p",
        "model": "m",
        "tool_results": results,
    }


def test_synthetic_floor_is_computed(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    seasons = store.seasons_with_data()
    assert seasons[0] == FLOOR
    assert seasons[-1] == "2025-26"
    assert "2013-14" not in seasons


def test_season_averages_out_of_range_2013_14(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as player_mod

    out = player_mod.get_season_averages.invoke(
        {"player_id": "LeBron James", "season": "2013-14"})
    assert out.get("ok") is False
    text = str(out.get("error", ""))
    assert "2013-14" in text
    assert FLOOR in text
    assert out.get("rows") in (None, [])


def test_season_averages_in_range_miss_names_span(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as player_mod

    out = player_mod.get_season_averages.invoke(
        {"player_id": "LeBron James", "season": "2025-26"})
    assert out.get("ok") is False
    text = str(out.get("error", ""))
    assert "2025-26" in text
    assert FLOOR in text


def test_player_intel_out_of_range_2013_14(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as player_mod

    out = player_mod.get_player_intel.invoke(
        {"player_id": "LeBron James", "season": "2013-14"})
    assert out.get("ok") is False
    text = str(out.get("error", ""))
    assert "2013-14" in text
    assert FLOOR in text


def test_find_out_of_range_picks_marker(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    import app.graph as graph_mod
    from shared.sources.base import empty as _empty
    from shared.sources import cbb as _cbb
    from shared.tools.league import get_draft_board

    monkeypatch.setattr(
        _cbb, "get_player_stats",
        lambda yr=2025: _empty("barttorvik", str(yr), "blocked"))

    span = graph_mod._TOOL_SEASON_COVERAGE["get_draft_board"]
    assert span[0] == "1996-97"
    assert "get_draft_board" in graph_mod._SEASON_CLAMP_EXEMPT

    async def _go():
        state = graph_mod.DimeState(
            question="q",
            primary="p",
            model="m",
            round=0,
            tool_results=[],
            calls_made=[],
            history=[],
            analysis="",
            suggestions=[],
        )
        state["_pending_calls"] = [
            {"name": "get_draft_board", "args": {"season": "1990"}}]
        graph_mod._supervisor_tools = lambda _s: [get_draft_board]
        events = [e async for e in graph_mod.actual_tool_node(state)]
        return state, events

    state, _ = asyncio.run(_go())
    result = state["tool_results"][0]
    assert result.get("ok") is False
    assert result.get("season_error") is not True
    assert "1989-90" not in str(result.get("error", ""))


def test_honest_answer_names_floor_and_nearest():
    from shared.tools._core import InvalidSeasonError

    out = _drain_analytics(_failure_state(
        "How did Jordan play in the 1998-99 season?",
        [{
            "tool": "get_award_race",
            "ok": False,
            "error": str(InvalidSeasonError("1998-99", nearest="2009-10")),
            "season_error": True,
        }],
    ))
    assert "1998-99" in out
    assert "2009-10" in out
    lowered = out.lower()
    for token in ("traceback", "silver_", "endpoint", "cache", "pipeline",
                  "snag", "failed", "exception", "tool_trace"):
        assert token not in lowered


def test_no_data_assembly_names_season_and_floor(monkeypatch, tmp_path):
    _warehouse(monkeypatch, tmp_path)
    from shared.tools import player as player_mod

    out = player_mod.get_season_averages.invoke(
        {"player_id": "LeBron James", "season": "2013-14"})
    text = _drain_analytics(_failure_state(
        "How did LeBron play in the 2013-14 season?",
        [dict(out, tool="get_season_averages")],
    ))
    assert "2013-14" in text
    assert FLOOR in text
