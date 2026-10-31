from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import EntityRef, EvidenceEnvelope, RunMode, TaskSpec

def _envelope(evidence_id: str, rows, entities=()) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        capability="standings",
        source="fixture",
        observed_at=datetime.now(UTC),
        season="2025-26",
        entities=list(entities),
        rows=rows,
    )

def _task(entities=()) -> TaskSpec:
    return TaskSpec(
        goal="followup",
        mode=RunMode.QUICK,
        deliverable="text",
        entities=list(entities),
    )

def _seed_parent(store, owner="o", thread="t"):
    store.append_exchange(owner, thread, "first", "answer",
                          run_id="run-1", turn_id="turn-1")
    refs = store.references(owner, thread)
    parent_sequence = refs[0].sequence
    branch = store.create_branch(owner, thread, parent_sequence)
    return branch, parent_sequence

def test_followup_reuses_parent_evidence_without_reexecution(tmp_path) -> None:
    from v2.conversations import ConversationStore

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    branch, _ = _seed_parent(store)
    envelope = _envelope("ev-1", [{"TEAM": "AAA", "WINS": 10}])
    store.attach_branch_evidence("o", "t", branch.branch_id, [envelope])

    calls: list[str] = []

    async def fresh_capability():
        calls.append("called")
        return _envelope("ev-fresh", [{"TEAM": "AAA", "WINS": 10}])

    entities = set()
    decision = store.decide_followup_reuse(
        "o", "t", branch.branch_id, entities,
        fetch_current_rows={"ev-1": [{"TEAM": "AAA", "WINS": 10}]},
    )
    assert [item.evidence_id for item in decision.reused] == ["ev-1"]
    assert decision.fresh_required is False
    assert calls == []
    reuses = store.branch_reuses("o", "t", branch.branch_id)
    assert [item.evidence_id for item in reuses] == ["ev-1"]
    assert reuses[0].parent_turn_id == "turn-1"

def test_followup_with_new_entities_executes_fresh(tmp_path) -> None:
    from v2.conversations import ConversationStore

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    branch, _ = _seed_parent(store)
    parent_entities = (EntityRef(id="1", type="team", display_name="AAA"),)
    store.attach_branch_evidence(
        "o", "t", branch.branch_id,
        [_envelope("ev-1", [{"TEAM": "AAA"}], entities=parent_entities)],
    )
    current = {(entity.type, entity.id) for entity in (
        EntityRef(id="2", type="team", display_name="BBB"),)}
    decision = store.decide_followup_reuse(
        "o", "t", branch.branch_id, current,
        fetch_current_rows={"ev-1": [{"TEAM": "AAA"}]},
    )
    assert decision.reused == []
    assert decision.fresh_required is True

def test_stale_reused_evidence_fails_loud(tmp_path) -> None:
    from v2.conversations import ConversationStore, StaleBranchEvidenceError

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    branch, _ = _seed_parent(store)
    store.attach_branch_evidence(
        "o", "t", branch.branch_id,
        [_envelope("ev-1", [{"TEAM": "AAA", "WINS": 10}])],
    )
    with pytest.raises(StaleBranchEvidenceError, match="ev-1"):
        store.reuse_branch_evidence(
            "o", "t", branch.branch_id,
            fetch_current_rows={"ev-1": [{"TEAM": "AAA", "WINS": 99}]},
        )

def test_branch_creation_never_duplicates_evidence_rows(tmp_path) -> None:
    from v2.conversations import ConversationStore

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    branch, _ = _seed_parent(store)
    store.attach_branch_evidence(
        "o", "t", branch.branch_id,
        [_envelope("ev-1", [{"TEAM": "AAA", "WINS": 10}])],
    )
    with pytest.raises(ValueError, match="duplicate"):
        store.attach_branch_evidence(
            "o", "t", branch.branch_id,
            [_envelope("ev-1", [{"TEAM": "AAA", "WINS": 10}])],
        )
    with pytest.raises(ValueError, match="duplicate"):
        store.attach_branch_evidence(
            "o", "t", branch.branch_id,
            [_envelope("ev-2", [{"TEAM": "AAA", "WINS": 10}])],
        )

def test_branch_names_its_parent_turn(tmp_path) -> None:
    from v2.conversations import ConversationStore

    store = ConversationStore(tmp_path / "conversations.sqlite3")
    branch, parent_sequence = _seed_parent(store)
    assert branch.parent_sequence == parent_sequence
    assert branch.parent_run_id == "run-1"
    assert branch.parent_turn_id == "turn-1"
    with pytest.raises(ValueError, match="parent"):
        store.create_branch("o", "t", 999)


def test_branch_sse_reports_counts_without_internal_ids() -> None:
    import json
    from v2.api.sse import encode_branch_reuse

    chunk = encode_branch_reuse(parent_sequence=3, reused_count=2)
    assert chunk.startswith("event: branch_reuse\n")
    payload = json.loads(chunk.split("data: ", 1)[1].strip())
    assert payload == {"parent_sequence": 3, "reused_count": 2}
