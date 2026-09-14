"""Finals-result pin (QA #74 / F60).

"Who won the 2026 Finals?" - the marquee phrasing - dead-ended to the
generic fallback under planner variance (8s/2 tools) while the longer
phrasing worked. The playoffs payload carries the finals block
deterministically, so the pin calls get_playoffs directly.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _triage_seed  # noqa: E402


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


def test_finals_short_phrasing_pinned():
    st = _drain("Who won the 2026 Finals?")
    assert "get_playoffs" in _tool_names(st)
    rows = st["tool_results"][-1].get("rows") or []
    payload = rows[0].get("rows") if rows else None
    finals = (payload or {}).get("finals") or {}
    assert finals.get("winner") == "NYK"
    assert finals.get("series_score") == "NYK 4 - 1 SAS"


def test_finals_variants_pinned():
    for q in ("Who won the 2026 NBA Finals and what was the series score?",
              "who took the finals this year",
              "2026 NBA champion"):
        st = _drain(q)
        assert "get_playoffs" in _tool_names(st), q


def test_finals_pin_guards():
    # Finals MVP belongs to the award known-gap
    st = _drain("Who won the 2026 Finals MVP?")
    assert "get_playoffs" not in _tool_names(st)
    # future/prediction phrasing stays out
    st = _drain("who will win the 2027 finals")
    assert "get_playoffs" not in _tool_names(st)
    # player-named finals asks stay with player routes
    st = _drain("how did Jalen Brunson do in the finals")
    assert "get_playoffs" not in _tool_names(st)
