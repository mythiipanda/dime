"""F63-T3: fresh evidence fails on a switch-back turn, but the thread
ledger already holds the payload-extracted fact. Analytics must answer
from the ledger, never 'No <team> data found' over known facts."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as g  # noqa: E402


def _run(state):
    async def go():
        async for _e in g.analytics_agent(state):
            pass
        return state
    return asyncio.run(go())


def test_no_evidence_with_ledger_answers_from_ledger():
    st = {"question": "Back to the Finals - who did the Knicks beat?",
          "tool_results": [{"tool": "get_playoff_intel", "ok": False,
                            "error": "query failed"}],
          "calls_made": [], "history": [], "primary": "p", "model": "m",
          "ledger": ["NBA Finals result: NYK 4 - 1 SAS",
                      "NBA champion: NYK (16-3 playoffs)"]}
    out = _run(st)
    assert "NYK 4 - 1 SAS" in out["analysis"]
    assert "No New York Knicks data found" not in out["analysis"]


def test_no_evidence_no_ledger_still_honest_no_data():
    st = {"question": "How did the Wizards do?",
          "tool_results": [], "calls_made": [], "history": [],
          "primary": "p", "model": "m", "ledger": []}
    out = _run(st)
    assert "No Washington Wizards data found" in out["analysis"]
