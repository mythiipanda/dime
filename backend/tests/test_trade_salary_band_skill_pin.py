from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "backend/analyst/skills/trade-evaluation/SKILL.md"


def test_trade_evaluation_has_plain_text_salary_band_quick_reference():
    src = SKILL.read_text()
    assert "Salary-matching quick reference" in src
    assert "outgoing <= $7,500,000: 200% of outgoing + $250,000" in src
    assert "$7,500,000 < outgoing <= $29,000,000: outgoing + $7,500,000" in src
    assert "outgoing > $29,000,000: 125% of outgoing + $250,000" in src
    assert "first apron: at most 100% of outgoing" in src


def test_trade_evaluation_pins_mid_band_anchor_and_rejects_wrong_constant():
    src = SKILL.read_text()
    assert "$26,382,060 + $7,500,000 = $33,882,060" in src
    assert "never use `125% + $100k`" in src
    assert "The high-band rule is `125% + $250k`" in src


def test_trade_evaluation_prefers_trade_tools_and_names_cba_owner():
    src = SKILL.read_text()
    assert "`get_trade_check` is the primary legality check" in src
    assert "`get_trade_legality`" in src
    assert "Manual band math is verification/fallback" in src
    assert "`cba-trade-analysis` owns the detailed CBA mechanics" in src
