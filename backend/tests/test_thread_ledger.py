"""Thread evidence ledger (v2 step 2, F62/F63).

Facts are extracted from tool PAYLOADS at ship time (never LLM text),
persisted per-thread, and injected into later turns' planner and
analytics context so follow-ups resolve evidence, not just entities.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (_extract_ledger_facts, _verify_draft_numerals,  # noqa: E402
                       presentation_agent)
from app import store  # noqa: E402

PLAYOFFS = {"tool": "get_playoffs", "ok": True,
            "rows": {"champion": "NYK",
                     "champion_record": {"w": 16, "l": 3},
                     "finals": {"teams": ["NYK", "SAS"],
                                "series_score": "NYK 4 - 1 SAS"}},
            "meta": {}}

TEAM_LEADERS = {"tool": "get_team_leaders", "ok": True, "rows": [{}],
                "meta": {"stat_category": "PTS",
                         "leader_line": "Denver Nuggets lead with 10010 "
                                        "total PTS (122.1 per game over "
                                        "82 games)"}}

GAMELOG_SINGLE = {"tool": "search_game_logs", "ok": True,
                  "rows": {"player": "Jalen Brunson", "scope": "playoffs",
                           "filters": "game 5",
                           "matches": [{"date": "2026-06-13",
                                        "matchup": "NYK @ SAS",
                                        "pts": 45.0, "reb": 3.0,
                                        "ast": 3.0}]},
                  "meta": {}}

GAMELOG_MANY = {"tool": "search_game_logs", "ok": True,
                "rows": {"player": "Jalen Brunson", "filters": "all games",
                         "matches": [{"date": "2026-06-13", "pts": 45.0},
                                     {"date": "2026-06-10", "pts": 30.0}]},
                "meta": {}}


def test_extract_finals_facts():
    facts = _extract_ledger_facts({"tool_results": [PLAYOFFS]})
    assert "NBA Finals result: NYK 4 - 1 SAS" in facts
    assert any(f.startswith("NBA champion: NYK (16-3") for f in facts)


def test_extract_leader_line():
    facts = _extract_ledger_facts({"tool_results": [TEAM_LEADERS]})
    assert facts == ["Denver Nuggets lead with 10010 total PTS "
                     "(122.1 per game over 82 games)"]


def test_extract_single_game_line_only():
    facts = _extract_ledger_facts({"tool_results": [GAMELOG_SINGLE]})
    assert facts == ["Jalen Brunson on 2026-06-13 (NYK @ SAS): "
                     "45 pts, 3 reb, 3 ast"]
    # multi-match with no narrowing filter records nothing specific
    assert _extract_ledger_facts({"tool_results": [GAMELOG_MANY]}) == []


def test_extract_skips_failed_tools():
    bad = dict(PLAYOFFS); bad["ok"] = False
    assert _extract_ledger_facts({"tool_results": [bad]}) == []


def test_store_roundtrip_and_dedupe():
    tid = f"test-ledger-{os.getpid()}"
    store.save_facts(tid, ["Fact A", "Fact B"], owner="test")
    store.save_facts(tid, ["Fact A"], owner="test")  # dupe
    facts = store.thread_facts(tid)
    assert facts == ["Fact A", "Fact B"]
    assert store.thread_facts("") == []


def test_ledger_numerals_are_provenance_valid():
    state = {"tool_results": [],
             "ledger": ["Jalen Brunson on 2026-06-13 (NYK @ SAS): "
                        "45 pts, 3 reb, 3 ast"]}
    v = _verify_draft_numerals(
        state, "As established, Brunson had 45 points in that game.")
    assert "45" not in v


def test_presentation_emits_ledger_facts_event():
    async def _go():
        state = {"question": "who won the finals?", "analysis":
                 "This data covers the 2025-26 season.\nThe NYK won.",
                 "tool_results": [dict(PLAYOFFS)], "calls_made": [],
                 "history": [], "primary": "p", "model": "m"}
        kinds = {}
        async for e in presentation_agent(state):
            kinds[e.get("type")] = e["data"]
        return kinds

    ev = asyncio.run(_go())
    assert "ledger_facts" in ev
    assert any("NYK 4 - 1 SAS" in f for f in ev["ledger_facts"]["facts"])
