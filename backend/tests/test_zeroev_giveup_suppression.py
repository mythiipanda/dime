from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_give_up_steer_suppressed_on_zero_evidence():
    src = (ROOT / "backend/analyst/pi-execution.ts").read_text()
    assert "if (!giveUpSteerUsed && !zeroEvidenceDataAsk)" in src, (
        "the give-up submit-push must not fire while the run still has zero "
        "data evidence — submitting an evidence-free draft can only fail the audit"
    )
