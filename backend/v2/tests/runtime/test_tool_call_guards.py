from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import EntityRef, Plan, PlanNode, RunMode, SeasonRef, TaskSpec
from v2.domain.evidence import post_result_denials, pre_call_denials


def _task(**overrides):
    base = dict(goal="answer", mode=RunMode.QUICK, deliverable="text")
    base.update(overrides)
    return TaskSpec(**base)

def _season_task(value="2025-26", **overrides):
    return _task(season=SeasonRef(value=value, source="user", confidence=1), **overrides)


def test_pre_call_denials_name_contradiction_without_execution():
    task = _season_task()
    denials = pre_call_denials(task, "standings", {"season": "2024-25"})
    assert len(denials) == 1
    assert denials[0].capability == "standings"
    assert denials[0].check == "season_mismatch"
    assert "2024-25" in denials[0].message
    assert "2025-26" in denials[0].message


def test_post_result_denials_pass_for_matching_scope():
    from v2.contracts import EvidenceEnvelope

    task = _season_task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="standings",
        source="fake",
        observed_at=datetime.now(UTC),
        season="2025-26",
        rows=[{"WINS": 61, "season": "2025-26"}],
    )
    assert post_result_denials(task, envelope) == []

def test_empty_forbidden_by_contract_fails_loud():
    from v2.contracts import EvidenceEnvelope

    task = _season_task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="sql_exec",
        source="fake",
        observed_at=datetime.now(UTC),
        season="2025-26",
        rows=[],
    )
    denials = post_result_denials(task, envelope)
    assert [item.check for item in denials] == ["empty_rows_forbidden"]
    assert denials[0].capability == "sql_exec"

def test_empty_allowed_by_contract_stays_allowed():
    from v2.contracts import EvidenceEnvelope

    task = _task()
    envelope = EvidenceEnvelope(
        evidence_id="ev",
        capability="injuries",
        source="fake",
        observed_at=datetime.now(UTC),
        rows=[],
    )
    assert post_result_denials(task, envelope) == []


@pytest.fixture
def anyio_backend():
    return "asyncio"
