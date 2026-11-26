from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "backend/analyst/skills/trade-evaluation/SKILL.md"
ANTI_PATTERN = "NEVER use 125%+$100k — that rule does not exist in the CBA; the $100k figure is a hallucination trap"


def _skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_trade_evaluation_has_plain_text_salary_band_quick_reference_near_top():
    src = _skill_text()
    assert "outgoing ≤ 7.5M → 200%+250k" in src
    assert "7.5–29M → outgoing+7.5M" in src
    assert ">29M → 125%+250k" in src
    assert "outgoing+7.5M" in src
    assert "125%+250k" in src
    assert src.index("## Salary-matching quick reference") < src.index("## 1. Tools and when they matter")


def test_trade_evaluation_pins_anti_pattern_line_and_anchor():
    src = _skill_text()
    assert ANTI_PATTERN in src
    assert "26,382,060 → 33,882,060" in src
    assert "$26,382,060 + $7,500,000" in src


def test_trade_evaluation_prefers_trade_tools_and_names_cba_owner():
    src = _skill_text()
    assert "`get_trade_check` is the primary legality check" in src
    assert "`get_trade_legality`" in src
    assert "Manual band math is verification/fallback" in src
    assert "`cba-trade-analysis` owns the detailed CBA mechanics" in src
