from datetime import datetime

import pytest

from v2.contracts import EvidenceEnvelope
from v2.domain.evidence import EvidenceIndex


def envelope(evidence_id: str, *, lineage=(), rows=None):
    return EvidenceEnvelope(evidence_id=evidence_id, capability="test", source="fixture",
        observed_at=datetime(2026, 9, 14), rows=rows or [{"PTS": 10}], lineage=list(lineage))


def test_index_resolves_nested_values_and_ancestors():
    index = EvidenceIndex([envelope("raw", rows={"teams": [{"PTS": 10}]}),
                           envelope("derived", lineage=["raw"])])
    assert index.ancestors("derived") == {"raw"}
    assert [(v.path, v.value) for v in index.values(["raw"])] == [("rows.teams[0].PTS", 10)]


@pytest.mark.parametrize("items, message", [
    ([envelope("same"), envelope("same")], "unique"),
    ([envelope("child", lineage=["missing"])], "unknown evidence lineage"),
    ([envelope("a", lineage=["b"]), envelope("b", lineage=["a"])], "acyclic"),
])
def test_index_rejects_invalid_lineage(items, message):
    with pytest.raises(ValueError, match=message):
        EvidenceIndex(items)


def test_source_integrity_rejects_salary_vintage_and_team_conflict():
    from v2.domain.evidence import source_integrity_issues

    salary = EvidenceEnvelope(
        evidence_id="salary", capability="contracts", source="bref",
        observed_at=datetime(2026, 9, 14), season="2026-27",
        rows=[{"PLAYER_NAME": "LeBron James", "TEAM": "PHI",
               "SALARY": 3876529}])
    issues = source_integrity_issues(
        salary, required_season="2025-26",
        expected_teams={"LeBron James": "LAL"})
    assert [issue.code for issue in issues] == [
        "season_mismatch", "team_conflict"]
    assert "2026-27" in issues[0].message
    assert "PHI" in issues[1].message and "LAL" in issues[1].message
