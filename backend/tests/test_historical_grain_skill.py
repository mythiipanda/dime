from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "backend/analyst/skills/historical-grain-and-time/SKILL.md"


def test_historical_grain_pins_dual_season_column_filter_forms():
    src = SKILL.read_text(encoding="utf-8")
    assert "`_season` is the varchar season label" in src
    assert "`season` is the integer end-year" in src
    assert "WHERE _season = '2024-25'" in src
    assert "for the same 2024-25 season use `WHERE season = 2025`" in src
    assert "Never substitute one for the other" in src
    assert "_season = 2025" in src
    assert "season = '2024-25'" in src
