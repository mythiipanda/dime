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


def test_numeral_provenance_accepts_percent_scaling_and_rounding():
    state = {"tool_results": [{"rows": {"probability": 0.548,
                                         "margin": 1.98}}]}
    assert _verify_draft_numerals(
        state, "Boston has a 54.8% chance and is favored by 2 points.") == []


def test_presentation_does_not_ship_unverified_figures_clean():
    async def _go():
        state = {"question": "rank them", "analysis": "Wrong has 99.9 points.",
                 "tool_results": [{"tool": "x", "ok": True,
                                   "rows": [{"PLAYER": "Right", "PTS": 10}]}],
                 "calls_made": [], "history": [], "primary": "p", "model": "m"}
        async for event in presentation_agent(state):
            if event.get("type") == "final_answer":
                return event["data"]["text"]

    answer = asyncio.run(_go())
    assert "99.9" not in answer
    assert "could not verify every figure" in answer


def test_game_prediction_publishes_verified_deterministic_summary():
    from app.graph import _triage_seed

    async def _go():
        state = {"question": "Who wins Celtics vs Knicks?", "history": [],
                 "tool_results": [], "calls_made": [], "round": 0}
        async for _ in _triage_seed(
                state["question"], "primary", "model", state):
            pass
        state.update({"analysis": "wrong 99.9", "primary": "p", "model": "m"})
        async for event in presentation_agent(state):
            if event.get("type") == "final_answer":
                return event["data"]["text"]

    answer = asyncio.run(_go())
    assert "54.8%" in answer and "2.0-point edge" in answer
    assert "could not verify" not in answer


def test_deterministic_prediction_suppresses_discarded_draft_caution(monkeypatch):
    from app import graph
    from app.graph import analytics_agent

    async def fake_stream(*args, **kwargs):
        yield {"text": "Model draft derives a 9.6-point probability gap."}

    monkeypatch.setattr(graph, "astream_with_fallback", fake_stream)

    async def _go():
        state = {"question": "Who wins Celtics vs Knicks?", "history": [],
                 "tool_results": [], "calls_made": [], "round": 0,
                 "primary": "p", "model": "m", "ledger": []}
        async for _ in graph._triage_seed(
                state["question"], "primary", "model", state):
            pass
        events = []
        async for event in analytics_agent(state):
            events.append(event)
        return events

    events = asyncio.run(_go())
    cautions = [event for event in events
                if event["type"] == "custom_data"
                and event["data"].get("unverified_numbers")]
    assert cautions == []


def test_wrapped_authoritative_answer_suppresses_discarded_draft_caution(monkeypatch):
    from app import graph
    from app.graph import analytics_agent

    async def fake_stream(*args, **kwargs):
        yield {"text": "Draft invents 022, 1, and 2."}

    monkeypatch.setattr(graph, "astream_with_fallback", fake_stream)

    async def _go():
        state = {"question": "What were Luka Doncic's stats in 2022-23?",
                 "history": [], "tool_results": [], "calls_made": [], "round": 0,
                 "primary": "p", "model": "m", "ledger": []}
        async for _ in graph._triage_seed(
                state["question"], "primary", "model", state):
            pass
        events = []
        async for event in analytics_agent(state):
            events.append(event)
        return state, events

    state, events = asyncio.run(_go())
    assert not [e for e in events if e["type"] == "custom_data"
                and e["data"].get("unverified_numbers")]
    answer = asyncio.run(_final_answer(state))
    assert "32.4 points" in answer and "2022-23" in answer
    assert "could not verify" not in answer


async def _final_answer(state):
    async for event in presentation_agent(state):
        if event.get("type") == "final_answer":
            return event["data"]["text"]
    raise AssertionError("no final answer")
