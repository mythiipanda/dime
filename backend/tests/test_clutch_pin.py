"""Clutch-scorer leaderboard pin (sweep3).

"Who are the best clutch scorers this season?" spent 16.8s on a
delegate fan-out for a board the warehouse already serves. The pin
calls get_clutch directly and builds the answer from the payload.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402


def _drain(question):
    async def _go():
        state = {"question": question, "history": [],
                 "tool_results": [], "calls_made": [], "round": 0}
        async for _e in _triage_seed(question, "primary", "model", state):
            pass
        return state

    return asyncio.run(_go())


def test_clutch_leaderboard_pinned():
    st = _drain("Who are the best clutch scorers this season?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_clutch"]
    meta = st["tool_results"][-1].get("meta") or {}
    ans = meta.get("deterministic_answer") or ""
    assert "Shai Gilgeous-Alexander" in ans and "175" in ans
    assert "final 5 minutes" in ans


def test_clutch_variants_pinned():
    for q in ("top clutch scorers", "clutch scoring leaders 2025-26"):
        st = _drain(q)
        assert "get_clutch" in [c.split(":")[0] for c in st["calls_made"]], q


def test_team_scope_clutch_not_pinned():
    # "best clutch teams" asks for team scope; the pin is player-only.
    st = _drain("best clutch teams this season")
    assert "get_clutch" not in [c.split(":")[0] for c in st["calls_made"]]


def test_team_clutch_fails_closed_without_team_rows():
    from app.tools.league import get_clutch
    out = get_clutch.invoke({"scope": "team", "season": "2025-26"})
    assert out["ok"] is False
    assert out["rows"] == []
    assert "team-level" in out["error"]
