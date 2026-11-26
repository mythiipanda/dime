import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "backend/analyst/skills/free-agency-and-cap/SKILL.md"


def test_cap_skill_teaches_leaguewide_scan_composition():
    src = SKILL.read_text()
    assert "Any all-30-team sweep, league-wide scan, payroll-tier count, or cross-team ranking is ONE `sql_exec`" in src
    assert "never 30 per-team tool calls" in src
    assert "Per-team cap tools are for single-team depth after the scan" in src
    assert "silver_cap_room" in src
    assert "silver_salaries" in src


def test_cap_skill_leaguewide_example_uses_warehouse_columns():
    src = SKILL.read_text()
    match = re.search(r"```sql\n(.*?)```", src, re.S)
    assert match, "free-agency-and-cap skill must include a SQL sweep example"
    query = match.group(1)
    assert "FROM silver_cap_room" in query
    for column in (
        "TEAM",
        "CAP_SEASON",
        "COMMITTED_SALARY",
        "PROJECTED_CAP",
        "PROJECTED_TAX",
        "PROJECTED_APRON1",
        "PROJECTED_APRON2",
    ):
        assert column in query
    assert "GROUP BY CAP_SEASON, payroll_tier" in query
    assert "get_cap_ledger" not in query
