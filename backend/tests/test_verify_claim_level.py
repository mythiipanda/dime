"""Claim-level numeral verification (work order 2026-09-26).

A derived number must carry its operands (typed calculation `N (a op b)`
or inline `N = a op b`) in the same sentence; operands must be evidence
numerals and must recompute to N. On mismatch only the failing sentence
is dropped - never the whole answer.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (  # noqa: E402
    _team_row,
    _verify_draft_numerals,
    _verify_numeral_claims,
    presentation_agent,
)

EVIDENCE = [{"tool": "x", "ok": True, "rows": [{"PTS": 18}, {"PTS": 12}]}]


def _state(**kw):
    s = {"question": "q", "tool_results": EVIDENCE, "ledger": [],
         "calls_made": [], "history": [], "primary": "p", "model": "m"}
    s.update(kw)
    return s


def test_derived_number_with_correct_operands_passes():
    assert _verify_numeral_claims(
        _state(), "The bench scored 30 (18 + 12) points.") == []
    assert _verify_numeral_claims(_state(), "Total 30 = 18 + 12.") == []
    # chained operands also fine (all operands must be evidence numerals)
    assert _verify_numeral_claims(
        _state(), "Combined 42 (18 + 12 + 12).") == []


def test_mismatch_flags_only_failing_sentence():
    text = "Right scored 18. Wrong claims 30 (18 + 11) points."
    claims = _verify_numeral_claims(_state(), text)
    # the derived 30 fails (operands do not recompute); 11 is not an
    # evidence numeral either - both live in the same failing sentence
    assert claims
    assert all("Wrong" in sent for sent, _ in claims)
    assert {num for _, num in claims} == {"30", "11"}
    assert _verify_draft_numerals(_state(), text) == ["30", "11"]


def test_plain_evidence_numbers_still_pass():
    assert _verify_numeral_claims(_state(), "Scored 18, then 12.") == []


def test_derived_with_non_evidence_operand_fails():
    assert _verify_numeral_claims(
        _state(), "The bench scored 30 (25 + 5) points.") != []


def test_presentation_drops_only_failing_sentence():
    async def _go():
        state = _state(analysis=("Right has 18 points. "
                                 "Wrong has 30 (18 + 11) points."))
        async for event in presentation_agent(state):
            if event.get("type") == "final_answer":
                return event["data"]["text"]

    answer = asyncio.run(_go())
    assert "18 points" in answer
    assert "30 (18 + 11)" not in answer
    assert "30" not in answer


def test_reversed_direction_margin_flagged_despite_operands():
    # Direction-operand bypass: a directional margin claim passes ONLY
    # when _margin_directed_ok binds it. The generic operand check must
    # NOT rescue a claim whose direction fails. DET leads SAS on NET
    # (2.4 vs 1.1), so "trails" is wrong even with recomputing operands.
    state = _state(tool_results=[{"tool": "x", "rows": [
        {"TEAM": "DET", "NET": 2.4}, {"TEAM": "SAS", "NET": 1.1}]}])
    rows = state["tool_results"][0]["rows"]
    assert _team_row(rows, "DET") == {"TEAM": "DET", "NET": 2.4}
    assert _team_row(rows, "SAS") == {"TEAM": "SAS", "NET": 1.1}
    assert [n for _, n in _verify_numeral_claims(
        state, "DET trails SAS by 1.3")] == ["1.3"]
    assert _verify_numeral_claims(state, "DET leads SAS by 1.3") == []
    assert [n for _, n in _verify_numeral_claims(
        state, "DET trails SAS by 1.3 (2.4 - 1.1 = 1.3).")] == ["1.3"], \
        "operand check rescued a direction-failing margin claim"
    assert _verify_numeral_claims(
        state, "DET leads SAS by 1.3 (2.4 - 1.1 = 1.3).") == []
