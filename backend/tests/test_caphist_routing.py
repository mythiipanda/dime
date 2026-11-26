from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_routing_bullet_names_silver_cap_history():
    src = (ROOT / "backend/analyst/runtime.ts").read_text()
    assert "silver_cap_history via sql_exec" in src
    assert "max_salary_tier_low/mid/high_pct" in src
