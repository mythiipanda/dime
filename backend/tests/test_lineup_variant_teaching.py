from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schema_note_teaches_variant_row_multiplication():
    src = (ROOT / "backend/shared/tools/league/sql_schema.py").read_text()
    assert "2x7x2" in src
    assert "multiply minutes and possessions" in src
    assert "measure_type" in src and "advanced" in src


def test_routing_bullet_teaches_variant_filtering():
    src = (ROOT / "backend/analyst/runtime.ts").read_text()
    assert "silver_hist_lineups carries up to 28 variant rows" in src
    assert "measure_type='advanced'" in src
    assert "multiplies minutes and possessions" in src
