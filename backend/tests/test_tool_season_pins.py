from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_history_current_leaders_uses_latest_season_present():
    src = (ROOT / "shared" / "tools" / "history.py").read_text()
    assert "MAX(_season)" in src
    assert "_season = '2025-26'" not in src
    assert "2026 AS season" not in src


def test_draft_capital_lookups_use_latest_season_present():
    src = (ROOT / "shared" / "tools" / "league" / "draft_capital.py").read_text()
    assert "max(_season)" in src
    assert "'2025-26'" not in src
