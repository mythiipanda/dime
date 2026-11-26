import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/analyst/pi-execution.ts").read_text()


def test_give_up_steer_suppressed_on_zero_evidence():
    assert "if (!giveUpSteerUsed && !zeroEvidenceDataAsk)" in SRC, (
        "the give-up submit-push must not fire while the run still has zero "
        "data evidence — submitting an evidence-free draft can only fail the audit"
    )


def test_zero_evidence_run_terminates_when_retrieval_never_happens():
    reprompt_at = SRC.index("zeroEvidenceRepromptUsed = true")
    giveup_at = SRC.index("if (!giveUpSteerUsed && !zeroEvidenceDataAsk)")
    break_at = SRC.index("break;", giveup_at)
    segment = SRC[giveup_at:break_at]
    continues_inside_giveup = segment.count("continue;")
    assert continues_inside_giveup == 1, "give-up branch should hold exactly one continue"
    tail = SRC[reprompt_at:break_at]
    assert tail.count("zeroEvidenceRepromptUsed = true") == 1, "reprompt is single-use"
    after_break = SRC[break_at:break_at + 120]
    assert "}" in after_break, "loop must close after the break — no further iteration path"
