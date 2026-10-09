from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pytest

from shared import durability
from v2.contracts import EvidenceEnvelope, Plan, PlanNode, RunMode, TaskSpec
from v2.runtime.checkpoints import ExecutionCheckpoint, FileCheckpointStore
from v2.runtime.failures import CandidateStore, FailureObservation
from v2.runtime.ledger import FileLedger, LedgerKind
from v2.tests.compatibility.replay import save_replay

FLAG = "shared.durability.DIRECTORY_FSYNC_SUPPORTED"
PLATFORM_SUPPORTS = durability.DIRECTORY_FSYNC_SUPPORTED

SITE_MODULES = (
    "v2.runtime.failures",
    "v2.runtime.ledger",
    "v2.runtime.checkpoints",
    "v2.tests.compatibility.replay",
)


def observation() -> FailureObservation:
    return FailureObservation(
        source="qa", failure_class="source_provenance", summary="mixed provenance",
        expected_relation="label each claim's source", revision="bad123", trace_id="trace-1",
    )


def task() -> TaskSpec:
    return TaskSpec(goal="answer", mode=RunMode.PROJECT, deliverable="report")


def plan() -> Plan:
    return Plan(nodes=[PlanNode(id="one", description="first", capability_hints=["fake"])])


def checkpoint() -> ExecutionCheckpoint:
    return ExecutionCheckpoint(version=2, run_id="durable", task=task(), plan=plan())


def evidence() -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="ev", capability="ratings", source="fixture",
        observed_at=datetime(2026, 9, 14, tzinfo=UTC), rows={"net": 8.2},
    )


def nothing(tmp_path) -> None:
    return None


def add_candidate(tmp_path) -> None:
    CandidateStore(tmp_path / "state" / "candidates.jsonl").add(observation())


def append_ledger(tmp_path) -> None:
    FileLedger(tmp_path / "state" / "run.jsonl", "run").append(
        LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})


def save_checkpoint(tmp_path) -> None:
    FileCheckpointStore(tmp_path / "state").save(checkpoint())


def seed_checkpoint(tmp_path) -> None:
    store = FileCheckpointStore(tmp_path / "state")
    store.save(checkpoint())


def delete_checkpoint(tmp_path) -> None:
    FileCheckpointStore(tmp_path / "state").delete("durable")


def write_replay(tmp_path) -> None:
    save_replay(tmp_path / "state" / "replay.json", "ratings", "abc123",
                [([evidence()], [{"call_id": "call", "name": "ratings", "args": {},
                                  "status": "ok", "error": None}])])


SITES: list[tuple[str, str, Callable[[Any], None], Callable[[Any], None], int]] = [
    ("failures", "v2.runtime.failures", nothing, add_candidate, 1),
    ("ledger", "v2.runtime.ledger", nothing, append_ledger, 1),
    ("checkpoints-save", "v2.runtime.checkpoints", nothing, save_checkpoint, 1),
    ("checkpoints-delete", "v2.runtime.checkpoints", seed_checkpoint, delete_checkpoint, 0),
    ("replay", "v2.tests.compatibility.replay", nothing, write_replay, 1),
]

SITE_IDS = [site[0] for site in SITES]


def spy_directory_open(monkeypatch) -> list[str]:
    seen: list[str] = []
    real = durability.open_directory_for_fsync

    def spy(path: str | Path) -> int | None:
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(durability, "open_directory_for_fsync", spy)
    return seen


def count_fsyncs(monkeypatch, module: str) -> list[int]:
    calls: list[int] = []
    real = os.fsync

    def record(fd: int) -> None:
        calls.append(fd)
        return real(fd)

    monkeypatch.setattr(f"{module}.os.fsync", record)
    return calls


@pytest.mark.parametrize(
    "name,module,setup,operation,file_fsyncs", SITES, ids=SITE_IDS)
def test_site_reads_platform_fact_from_shared_module(
    name, module, setup, operation, file_fsyncs, tmp_path, monkeypatch,
) -> None:
    setup(tmp_path)
    monkeypatch.setattr(FLAG, False)
    seen = spy_directory_open(monkeypatch)
    calls = count_fsyncs(monkeypatch, module)
    operation(tmp_path)
    assert len(seen) == 1, name
    assert len(calls) == file_fsyncs, name


@pytest.mark.parametrize(
    "name,module,setup,operation,file_fsyncs", SITES, ids=SITE_IDS)
def test_site_opens_the_directory_when_platform_allows_it(
    name, module, setup, operation, file_fsyncs, tmp_path, monkeypatch,
) -> None:
    setup(tmp_path)
    monkeypatch.setattr(FLAG, True)
    seen = spy_directory_open(monkeypatch)
    calls = count_fsyncs(monkeypatch, module)
    if not PLATFORM_SUPPORTS:
        with pytest.raises(OSError):
            operation(tmp_path)
        assert len(seen) == 1, name
        return
    operation(tmp_path)
    assert len(seen) == 1, name
    assert len(calls) == file_fsyncs + 1, name


def test_every_site_module_delegates_instead_of_opening_a_directory() -> None:
    for name in SITE_MODULES:
        module = __import__(name, fromlist=["_"])
        source = inspect.getsource(module)
        assert 'os.name == "posix"' not in source, name
        for line in source.splitlines():
            assert not ("os.open(" in line and "O_RDONLY" in line), f"{name}: {line.strip()}"


def test_open_directory_for_fsync_returns_none_when_unsupported(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(FLAG, False)
    assert durability.open_directory_for_fsync(tmp_path) is None


def test_open_directory_for_fsync_matches_platform_capability(tmp_path) -> None:
    if not PLATFORM_SUPPORTS:
        with pytest.raises(OSError):
            os.open(tmp_path, os.O_RDONLY)
        return
    handle = durability.open_directory_for_fsync(tmp_path)
    assert isinstance(handle, int)
    os.close(handle)


def test_candidate_add_reports_success_once_on_every_platform(tmp_path) -> None:
    store = CandidateStore(tmp_path / "candidates.jsonl")
    first = store.add(observation())
    assert store.read() == [first]
    assert store.add(observation()) == first
    assert len(store.read()) == 1


def test_candidate_add_writes_exactly_one_record_per_distinct_failure(tmp_path) -> None:
    store = CandidateStore(tmp_path / "candidates.jsonl")
    store.add(observation())
    store.add(observation())
    other = observation().model_copy(update={"summary": "another failure shape"})
    store.add(other)
    assert len(store.read()) == 2
