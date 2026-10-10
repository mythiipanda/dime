from datetime import UTC, datetime

import pytest

from v2.contracts import EvidenceEnvelope, PlanNode, RunMode, TaskSpec
from v2.runtime import LedgerKind, RecordedCapability, RunLedger

class Capability:
    name = "standings"

    async def execute(self, node, task, evidence):
        return EvidenceEnvelope(evidence_id="ev", capability=self.name,
            source="fixture", observed_at=datetime.now(UTC), rows={"wins": 61})

@pytest.mark.anyio
async def test_recorded_capability_emits_canonical_call_and_result():
    ledger = RunLedger("run")
    capability = RecordedCapability(Capability(), ledger, turn_id="turn")
    await capability.execute(
        PlanNode(id="record", description="record", capability_hints=["standings"]),
        TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [])

    assert [entry.kind for entry in ledger.entries] == [
        LedgerKind.TOOL_CALL, LedgerKind.TOOL_RESULT]
    assert ledger.entries[0].call_id == ledger.entries[1].call_id
    assert ledger.entries[1].data["evidence"]["evidence_id"] == "ev"
    assert ledger.entries[1].data["duration_ms"] >= 0

@pytest.mark.anyio
async def test_recorded_capability_rejects_untyped_result_and_records_failure():
    class Untyped:
        name = "standings"
        async def execute(self, node, task, evidence):
            return {"wins": 61}

    ledger = RunLedger("run")
    capability = RecordedCapability(Untyped(), ledger, turn_id="turn")
    with pytest.raises(TypeError, match="EvidenceEnvelope"):
        await capability.execute(
            PlanNode(id="record", description="record", capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [],
        )
    assert ledger.entries[-1].data["status"] == "failed"
    assert ledger.entries[-1].data["error"] == (
        "TypeError: capability must return EvidenceEnvelope")
    assert ledger.entries[-1].data["duration_ms"] >= 0

def test_recorded_capability_requires_identity() -> None:
    class Blank(Capability):
        name = " "

    with pytest.raises(ValueError, match="name must be non-empty"):
        RecordedCapability(Blank(), RunLedger("run"), turn_id="turn")
    with pytest.raises(ValueError, match="turn id must be non-empty"):
        RecordedCapability(Capability(), RunLedger("run"), turn_id=" ")

def test_recorded_capability_requires_boolean_season_scope() -> None:
    class Invalid(Capability):
        task_season_scoped = "false"

    with pytest.raises(TypeError, match="task_season_scoped must be boolean"):
        RecordedCapability(Invalid(), RunLedger("run"), turn_id="turn")

@pytest.mark.anyio
async def test_recorded_capability_rejects_wrong_capability_before_admission() -> None:
    class Wrong(Capability):
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="ev", capability="player_report", source="fixture",
                observed_at=datetime.now(UTC), rows={},
            )

    ledger = RunLedger("run")
    capability = RecordedCapability(Wrong(), ledger, turn_id="turn")
    with pytest.raises(ValueError, match="expected 'standings'"):
        await capability.execute(
            PlanNode(id="record", description="record", capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [],
        )
    assert ledger.entries[-1].data["status"] == "failed"
    assert all(entry.data.get("status") != "ok" for entry in ledger.entries)

@pytest.mark.anyio
async def test_recorded_capability_rejects_mislabeled_lineage_before_admission() -> None:
    parent = EvidenceEnvelope(
        evidence_id="parent", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )

    class WrongLineage(Capability):
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="ev", capability=self.name, source="fixture",
                observed_at=datetime.now(UTC), rows={}, lineage=[],
            )

    ledger = RunLedger("run")
    capability = RecordedCapability(WrongLineage(), ledger, turn_id="turn")
    with pytest.raises(ValueError, match="lineage does not match"):
        await capability.execute(
            PlanNode(id="record", description="record", capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [parent],
        )
    assert ledger.entries[-1].data["status"] == "failed"

@pytest.mark.anyio
async def test_recorded_capability_rejects_reused_input_evidence_identity() -> None:
    parent = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={},
    )

    class ReusedIdentity(Capability):
        async def execute(self, node, task, evidence):
            return EvidenceEnvelope(
                evidence_id="ev", capability=self.name, source="fixture",
                observed_at=datetime.now(UTC), rows={}, lineage=["ev"],
            )

    ledger = RunLedger("run")
    capability = RecordedCapability(ReusedIdentity(), ledger, turn_id="turn")
    with pytest.raises(ValueError, match="cannot reuse"):
        await capability.execute(
            PlanNode(id="record", description="record", capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [parent],
        )
    assert ledger.entries[-1].data["status"] == "failed"

@pytest.mark.anyio
async def test_recorded_capability_revalidates_copied_evidence() -> None:
    class Invalid(Capability):
        async def execute(self, node, task, evidence):
            valid = await super().execute(node, task, evidence)
            return valid.model_copy(update={"source": " "})

    ledger = RunLedger("run")
    capability = RecordedCapability(Invalid(), ledger, turn_id="turn")
    with pytest.raises(ValueError, match="evidence identity"):
        await capability.execute(
            PlanNode(id="record", description="record",
                     capability_hints=["standings"]),
            TaskSpec(goal="record", mode=RunMode.QUICK, deliverable="text"), [],
        )
    assert ledger.entries[-1].data["status"] == "failed"

def test_publishable_arguments_publish_the_declared_public_values() -> None:
    from v2.runtime.recording import argument_counts, publishable_arguments

    arguments = {"a": "Subject Alpha", "b": "Subject Bravo",
                 "season": "2025-26", "surprise": "hidden"}

    assert publishable_arguments("player_comparison", arguments) == [
        {"name": "a", "value": "Subject Alpha"},
        {"name": "b", "value": "Subject Bravo"},
        {"name": "season", "value": "2025-26"},
    ]
    assert "hidden" not in str(publishable_arguments("player_comparison", arguments))
    assert argument_counts("player_comparison", arguments) == (4, 1)

def test_publishable_arguments_withhold_declared_identity_arguments() -> None:
    from v2.runtime.recording import argument_counts, publishable_arguments

    arguments = {"player_id": "internal-identity-3f9c",
                 "team_id": "internal-identity-3f9c",
                 "season": "2025-26"}
    rows = publishable_arguments("four_factors", arguments)

    assert rows == [{"name": "season", "value": "2025-26"}]
    assert "internal-identity" not in str(rows)
    assert argument_counts("four_factors", arguments) == (3, 0)

def test_publishable_arguments_withhold_identity_and_secret_arguments() -> None:
    from v2.runtime.recording import publishable_arguments

    fetch_arguments = {"result_rank": 1, "search_evidence_id": "evidence:42"}
    fetch_rows = publishable_arguments("web_fetch", fetch_arguments)

    assert fetch_rows == [{"name": "result_rank", "value": 1}]
    assert "evidence:42" not in str(fetch_rows)

    search_rows = publishable_arguments(
        "web_search", {"query": "luka stats", "api_key": "sk-live-secret",
                       "max_results": 5})

    assert search_rows == [
        {"name": "max_results", "value": 5},
        {"name": "query", "value": "luka stats"},
    ]
    assert "sk-live-secret" not in str(search_rows)

def test_publishable_arguments_withhold_raw_sql_statement_text() -> None:
    from v2.runtime.recording import argument_counts, publishable_arguments

    statements = {
        "sql": "SELECT secret FROM vault",
        "season": "2025-26",
    }
    rows = publishable_arguments("sql_exec", statements)

    assert rows == [{"name": "season", "value": "2025-26"}]
    assert "SELECT" not in str(rows)
    assert "secret FROM vault" not in str(rows)
    assert argument_counts("sql_exec", statements) == (2, 0)

def test_publishable_arguments_withhold_declared_statement_text_suffixes() -> None:
    from v2.runtime.recording import publishable_arguments

    rows = publishable_arguments(
        "sql_exec", {"agent_sql": "SELECT 1", "base_sql": "SELECT 2",
                     "season": "2025-26"})

    assert rows == [{"name": "season", "value": "2025-26"}]
    assert "SELECT" not in str(rows)

def test_publishable_arguments_publish_non_sql_query_arguments() -> None:
    from v2.runtime.recording import publishable_arguments

    search_rows = publishable_arguments(
        "web_search", {"query": "luka stats", "max_results": 5})

    assert search_rows == [
        {"name": "max_results", "value": 5},
        {"name": "query", "value": "luka stats"},
    ]

    resolution_rows = publishable_arguments(
        "entity_resolution", {"query": "luka stats"})

    assert resolution_rows == [{"name": "query", "value": "luka stats"}]

def test_publishable_arguments_publish_normal_player_comparison_args() -> None:
    from v2.runtime.recording import publishable_arguments

    arguments = {"a": "Subject Alpha", "b": "Subject Bravo",
                 "season": "2025-26"}

    assert publishable_arguments("player_comparison", arguments) == [
        {"name": "a", "value": "Subject Alpha"},
        {"name": "b", "value": "Subject Bravo"},
        {"name": "season", "value": "2025-26"},
    ]

def _declare_arguments(monkeypatch, names: set[str]) -> None:
    from v2.runtime.recording import ArgumentSpec

    spec = ArgumentSpec(declared=frozenset(names), required=(),
                        evidence_satisfied=frozenset())
    monkeypatch.setattr("v2.runtime.recording._argument_spec",
                       lambda capability_name: spec)

def test_publishable_arguments_withhold_statement_text_suffixes_when_declared(
    monkeypatch,
) -> None:
    from v2.runtime.recording import argument_counts, publishable_arguments

    _declare_arguments(monkeypatch, {"sql", "agent_sql", "season"})
    statements = {
        "sql": "SELECT secret FROM vault",
        "agent_sql": "SELECT secret FROM vault",
        "season": "2025-26",
    }

    assert argument_counts("sql_exec_fixture", statements) == (3, 0)
    rows = publishable_arguments("sql_exec_fixture", statements)

    assert rows == [{"name": "season", "value": "2025-26"}]
    assert "SELECT" not in str(rows)
    assert "secret FROM vault" not in str(rows)

def test_publishable_arguments_publish_declared_non_sql_keys_when_declared(
    monkeypatch,
) -> None:
    from v2.runtime.recording import argument_counts, publishable_arguments

    _declare_arguments(monkeypatch, {"sql", "agent_sql", "season", "query"})
    statements = {
        "sql": "SELECT secret FROM vault",
        "agent_sql": "SELECT secret FROM vault",
        "season": "2025-26",
        "query": "luka stats",
    }

    assert argument_counts("sql_exec_fixture", statements) == (4, 0)
    rows = publishable_arguments("sql_exec_fixture", statements)

    assert rows == [
        {"name": "query", "value": "luka stats"},
        {"name": "season", "value": "2025-26"},
    ]
    assert "SELECT" not in str(rows)
    assert "secret FROM vault" not in str(rows)
    assert "luka stats" in str(rows)

