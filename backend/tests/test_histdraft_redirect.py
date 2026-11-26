from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_histdraft_schema_note_redirects_value_curve_asks():
    src = (ROOT / "backend/shared/tools/league/sql_schema.py").read_text()
    assert "silver_hist_draft" in src
    assert "value-curve, median-career-WAR-by-slot" in src
    assert "silver_draft_value_curve" in src
