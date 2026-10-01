import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as G

RESULTS = [
    {"tool": "get_leaders", "ok": True,
     "rows": [{"PLAYER": "Nikola Jokic", "APG": 10.72},
              {"PLAYER": "Trae Young", "APG": 10.1}],
     "meta": {"source": "warehouse:silver_hist_player_seasons",
              "season": "2024-25"}},
    {"tool": "delegate_team", "ok": False,
     "error": "timed out after 25s"},
]


def test_watchdog_partial_names_found_and_missing():
    text = G._watchdog_partial(RESULTS)
    assert "Nikola Jokic" in text
    assert "warehouse:silver_hist_player_seasons" in text
    assert "rather than guessed" in text
    assert "I could not find that in the dataset" not in text
    assert "timed out before finishing" not in text
    assert "get_leaders" not in text
    assert "delegate_team" not in text
    scrubbed = G._scrub_final_text(text)
    assert "Nikola Jokic" in scrubbed
    assert "rather than guessed" in scrubbed


def test_watchdog_partial_empty_results_still_contentful():
    text = G._watchdog_partial([])
    assert len(text.split()) >= 5
    assert "rather than guessed" in text
    assert "timed out before finishing" not in text


def test_turn_budget_fits_client_window():
    assert G.TURN_HARD_CAP_S <= 110
    assert min(G.DEEP_TURN_BUDGET_S, G.TURN_HARD_CAP_S) <= 110


def test_analytics_skips_llm_on_watchdog():
    state = {
        "question": "Who are the top 5 MVP candidates by on/off?",
        "tool_results": list(RESULTS),
        "calls_made": ["get_leaders", "delegate_team"],
        "ledger": [],
        "_watchdog_tripped": True,
        "analysis": "",
    }

    async def run():
        events = []
        async for event in G.analytics_agent(state):
            events.append(event)
        return events

    asyncio.run(run())
    assert "Nikola Jokic" in state["analysis"]
    assert "Scouting teams" in state["analysis"]
    assert state.get("_analysis_final") is True


def test_analytics_normal_path_unchanged():
    state = {
        "question": "q",
        "tool_results": [],
        "calls_made": [],
        "ledger": ["Jokic leads at 10.72 assists per game in 2024-25."],
        "analysis": "",
    }

    async def run():
        async for _ in G.analytics_agent(state):
            pass

    asyncio.run(run())
    assert "2024-25" in state["analysis"]
    assert state.get("_analysis_final") is not True
