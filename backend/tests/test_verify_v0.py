"""Verify node v0 (Tony's harness redesign, rollout step 1).

(a) Banned-phrase honest end: the F61 text ("I could not compute that
from the dataset - the warehouse query for it did not run. Try a
narrower ask.") was both a canned fallback AND a model-emitted shape.
Neither may ship - the fallback names coverage instead.
(b) Numeral-provenance telemetry: every number in the final answer
traces to the turn's payloads; violations are recorded on
state['_verify'] for the reviewer (no user-visible change in v0).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (_COMPUTE_FALLBACK, _scrub_final_text,  # noqa: E402
                       _verify_draft_numerals, presentation_agent)

BANNED = ("narrower", "did not run", "did not succeed")


def test_canned_dev_text_fallback_is_honest():
    out = _scrub_final_text(
        "NameError: name 'foo' is not defined. Traceback line 4. "
        "NameError again. Traceback. Error. Exception. NameError.")
    for b in BANNED:
        assert b not in out
    assert out == _COMPUTE_FALLBACK
    assert "2025-26" in out and "Finals" in out


def test_model_emitted_f61_shape_rewritten():
    out = _scrub_final_text(
        "I could not compute that from the dataset - the warehouse "
        "query for it did not run. Try a narrower ask.")
    for b in BANNED:
        assert b not in out
    assert out == _COMPUTE_FALLBACK


def test_gap_detection_still_fires_on_new_prefix():
    # The known-gap override keys on the fallback prefix; a compute
    # failure on a known-gap question must still ship the gap note.
    async def _go():
        state = {"question": "what contract types can teams offer?",
                 "analysis": ("NameError: boom. Traceback. Error. "
                              "Exception. NameError. Traceback."),
                 "tool_results": [], "calls_made": [], "history": [],
                 "primary": "p", "model": "m"}
        out = None
        async for e in presentation_agent(state):
            if e.get("type") == "final_answer":
                out = e["data"]["text"]
        return out

    out = asyncio.run(_go())
    assert out and "narrower" not in out and "did not run" not in out
    assert "contract" in out.lower()


def test_numeral_provenance_records_violations():
    state = {"tool_results": [
        {"tool": "get_team_leaders",
         "rows": [{"TEAM": "Denver Nuggets", "PTS": 10010, "GP": 82,
                   "PER_GAME": 122.1}], "meta": {"stat_category": "PTS"}}]}
    bad = _verify_draft_numerals(
        state, "Denver leads with 10010 total points, ahead of 9999.")
    assert bad == ["9999"]
    ok = _verify_draft_numerals(
        {}, "Denver leads with 10010 total PTS (122.1 per game).")
    assert ok == []


def test_numeral_provenance_handles_empty_state():
    assert _verify_draft_numerals({}, "") == []
    assert _verify_draft_numerals({"tool_results": None}, None) == []
