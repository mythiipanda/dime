from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/shared/tools/league/cba_cap.py").read_text()


def test_cap_ledger_description_redirects_leaguewide_audits():
    assert "Never answer a league-wide payroll-tier" in SRC
    assert "ONE sql_exec over silver_cap_room" in SRC
    assert "per-team fanout totals produce wrong tier counts" in SRC, (
        "get_cap_ledger must steer league-wide audits away from per-team fanout — "
        "its payroll basis differs from silver_cap_room committed salary (task 041)"
    )


def test_cap_ledger_description_blocks_per_team_sweep():
    assert "Any all-30-teams sweep or league-wide analysis is ONE sql_exec" in SRC
    assert "never per-team calls of this tool" in SRC
