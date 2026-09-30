import asyncio
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools._core import (
    COVERAGE_START,
    InvalidSeasonError,
    clamp_season,
    coverage_end,
    last_completed_season,
)

BANNED = (
    "traceback",
    "silver_",
    "endpoint",
    "cache",
    "pipeline",
    "snag",
    "failed",
    "exception",
    "tool_trace",
)


SEED_SEASONS = ["2009-10", "2013-14", "2023-24", "2024-25"]


@pytest.fixture()
def warehouse_seasons(tmp_path, monkeypatch):
    import duckdb

    from shared import store
    from shared.tools import _core as core_mod

    db = tmp_path / "seasons.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)")
    for season in SEED_SEASONS:
        con.execute("INSERT INTO silver_boxscores VALUES (?, ?)",
                    [season, "00200001"])
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    core_mod.last_completed_season_cache_clear()
    yield db
    core_mod.last_completed_season_cache_clear()


def _node_state():
    import app.graph as graph_mod

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
    return state


def _run_node(calls, tools):
    import app.graph as graph_mod

    async def _go():
        state = _node_state()
        state["_pending_calls"] = calls
        graph_mod._supervisor_tools = lambda _s: tools
        events = [e async for e in graph_mod.actual_tool_node(state)]
        return state, events

    return asyncio.run(_go())


class _Echo:
    name = "get_echo"

    async def ainvoke(self, args):
        return {"tool": "get_echo", "ok": True, "rows": [],
                "echo": dict(args)}


def test_clamp_season_accepts_exact_slugs(warehouse_seasons):
    assert last_completed_season() == "2024-25"
    assert clamp_season("2013-14") == "2013-14"
    assert clamp_season("2024-25") == "2024-25"
    assert clamp_season("2009-10") == "2009-10"


def test_clamp_season_normalizes_explicit_ranges(warehouse_seasons):
    assert clamp_season("2014") == "2013-14"
    assert clamp_season("2025") == "2024-25"
    assert clamp_season("2010") == "2009-10"


def test_clamp_season_resolves_empty_to_warehouse_season(warehouse_seasons):
    assert clamp_season(None) == "2024-25"
    assert clamp_season("") == "2024-25"


def test_clamp_season_rejects_without_fallback(warehouse_seasons):
    end = coverage_end()
    for bad in ("1998-99", "2030-31"):
        with pytest.raises(InvalidSeasonError) as info:
            clamp_season(bad)
        assert info.value.requested == bad
        assert info.value.nearest in (COVERAGE_START, end)
    with pytest.raises(InvalidSeasonError):
        clamp_season("1998-99")
    assert last_completed_season() == end


def test_clamp_season_error_is_plain_language(warehouse_seasons):
    end = coverage_end()
    with pytest.raises(InvalidSeasonError) as low:
        clamp_season("1998-99")
    with pytest.raises(InvalidSeasonError) as high:
        clamp_season("2030-31")
    assert low.value.nearest == COVERAGE_START
    assert high.value.nearest == end
    for exc, slug, edge in (
        (low.value, "1998-99", COVERAGE_START),
        (high.value, "2030-31", end),
    ):
        text = str(exc)
        assert slug in text
        assert edge in text
        assert COVERAGE_START in text
        assert end in text
        lowered = text.lower()
        for token in BANNED:
            assert token not in lowered


def test_v1_catalog_lists_season_disambiguation():
    from app.skills import catalog, load_skill

    lines = catalog().strip().splitlines()
    match = [line for line in lines
             if line.startswith("- season_interpretation: ")]
    assert match
    desc = match[0].split(": ", 1)[1]
    assert desc.strip()
    assert len(desc) <= 150
    body = load_skill("season_interpretation")
    assert "2013-14" in body
    assert "ask the user" in body


def test_v2_library_loads_season_disambiguation():
    from v2.skills import SkillLibrary

    library = SkillLibrary()
    entries = library.catalog()
    assert entries
    for entry in entries:
        assert entry["name"]
        assert entry["description"].strip()
    assert all("season" not in entry["name"] for entry in entries)


def test_tool_node_passes_valid_season_through(warehouse_seasons):
    state, _ = _run_node(
        [{"name": "get_echo", "args": {"season": "2024-25"}}], [_Echo()])
    result = state["tool_results"][0]
    assert result.get("ok") is True
    assert result["echo"]["season"] == "2024-25"
    state, _ = _run_node(
        [{"name": "get_echo", "args": {"season": "2014"}}], [_Echo()])
    result = state["tool_results"][0]
    assert result.get("ok") is True
    assert result["echo"]["season"] == "2013-14"


def test_tool_node_converts_bad_season_to_ok_false():
    state, _ = _run_node(
        [{"name": "get_echo", "args": {"season": "1998-99"}}], [_Echo()])
    result = state["tool_results"][0]
    assert result.get("ok") is False
    assert result.get("season_error") is True
    text = str(result.get("error", ""))
    assert "1998-99" in text
    assert COVERAGE_START in text
    lowered = text.lower()
    for token in BANNED:
        assert token not in lowered


def test_season_failure_result_shape(warehouse_seasons):
    state, _ = _run_node(
        [{"name": "get_echo", "args": {"season": "2030-31"}}], [_Echo()])
    result = state["tool_results"][0]
    assert set(result) == {"tool", "ok", "error", "season_error"}
    assert result["ok"] is False
    assert isinstance(result["error"], str) and result["error"].strip()
    assert result["season_error"] is True


def test_user_safe_error_passes_season_message_through():
    import app.graph as graph_mod

    msg = str(InvalidSeasonError("1998-99", nearest="2009-10"))
    kept = graph_mod._user_safe_tool_error("get_award_race", msg)
    assert kept == msg.rstrip(".")
    assert "1998-99" in kept
    assert "2009-10" in kept
    scrubbed = graph_mod._user_safe_tool_error(
        "text_to_sql", "text_to_sql failed: no such column foo")
    assert scrubbed == "that data pull did not complete"


def test_presentation_names_season_without_plumbing():
    import app.graph as graph_mod

    async def _go():
        state = {
            "question": "How did anyone average in the 2013-14 season?",
            "history": [],
            "calls_made": [],
            "ledger": [],
            "primary": "p",
            "model": "m",
            "tool_results": [{
                "tool": "get_season_averages",
                "ok": False,
                "error": (
                    "No season line on file for 2013-14; season lines "
                    "cover 2014-15 through the current season, so this "
                    "one is outside dataset coverage."
                ),
            }],
        }
        async for _ in graph_mod.analytics_agent(state):
            pass
        return state.get("analysis", "")

    out = asyncio.run(_go())
    assert "2013-14" in out
    assert "2014-15" in out
    lowered = out.lower()
    for token in BANNED + ("get_season_averages", "delegate_", "warehouse",):
        assert token not in lowered


def test_no_regex_in_clamp_season_path():
    import shared.tools._core as core_mod

    sources = [
        inspect.getsource(core_mod.clamp_season),
        inspect.getsource(core_mod._canonical_parts),
        inspect.getsource(core_mod._bare_year_slug),
        inspect.getsource(core_mod.season_error_message),
        inspect.getsource(core_mod.InvalidSeasonError),
    ]
    assert sources
    for src in sources:
        assert "import re" not in src
        assert "re." not in src
