from __future__ import annotations

import json
from pathlib import Path

SUBJECT_A = "Subject Alpha"
SUBJECT_B = "Subject Bravo"
SEASON = "2025-26"
PROBE = "UNPUBLISHED_PROBE_VALUE"
PRIVATE_ID = "internal-identity-3f9c"

def _events(text: str) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name is not None and data is not None:
            parsed.append((name, data))
    return parsed

def _single(text: str, event: str) -> dict:
    found = [payload for name, payload in _events(text) if name == event]
    assert len(found) == 1, f"expected exactly one {event} event, got {len(found)}"
    return found[0]

def _stream(monkeypatch, tmp_path: Path, runtime_factory) -> str:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2.api import routes
    from v2.projects.service import ProjectStore

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setenv("DIME_V2_ACTIVITY_DIR", str(tmp_path / "activity"))
    monkeypatch.setattr(
        "shared.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", runtime_factory)
    routes._CHAT_HITS.clear()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    return TestClient(app).post("/api/v2/chat/stream", json={"q": "x"}).text

def _quiet_result():
    from v2 import contracts
    from v2.runtime.models import ExecutionResult, RuntimeResult

    return RuntimeResult(
        task=contracts.TaskSpec(goal="x", mode="quick", deliverable="x"),
        execution=ExecutionResult(plan=contracts.Plan(nodes=[])),
        draft=contracts.DraftReport(sections=[], claims=[]),
        verification=contracts.VerificationReport(status="pass"),
    )

def _counting_capability(name, rows, calls):
    from v2.runtime.fakes import FakeCapability

    capability = FakeCapability(name, rows)
    original = capability.execute

    async def counting_execute(*args, **kwargs):
        calls.append(args)
        return await original(*args, **kwargs)

    capability.execute = counting_execute
    return capability

class Invocation:
    def __init__(self) -> None:
        self.calls: list = []
        self.observed: list = []
        self.ledger = None
        self.text = ""
        self.route_activity = None

    @property
    def recorded_arguments(self) -> dict:
        from v2.runtime.ledger import LedgerKind

        return next(
            entry.data["args"]["node"]["arguments"] for entry in self.ledger.entries
            if entry.kind == LedgerKind.TOOL_CALL)

    @property
    def ledger_results(self) -> list:
        from v2.runtime.ledger import LedgerKind

        return [entry for entry in self.ledger.entries
                if entry.kind == LedgerKind.TOOL_RESULT]

def _stream_one_invocation(monkeypatch, tmp_path, name, arguments, rows,
                           activity_from_route=True) -> Invocation:
    from v2 import contracts
    from v2.runtime.ledger import RunLedger
    from v2.runtime.recording import RecordedCapability

    result = _quiet_result()
    probe = Invocation()

    class Runtime:
        async def run(self, q, run_id=None, **kwargs):
            activity = (probe.route_activity if activity_from_route
                        else probe.observed.append)
            await RecordedCapability(
                _counting_capability(name, rows, probe.calls),
                probe.ledger, turn_id=run_id, activity=activity,
            ).execute(
                contracts.PlanNode(
                    id="node", description="describe the work",
                    capability_hints=[name], arguments=dict(arguments)),
                result.task, [])
            return result

    def build(**kwargs):
        probe.route_activity = kwargs["activity"]
        probe.ledger = RunLedger(kwargs["run_id"])
        return Runtime(), probe.ledger

    probe.text = _stream(monkeypatch, tmp_path, build)
    return probe

def test_stream_tool_call_publishes_the_arguments_the_ledger_recorded(monkeypatch, tmp_path):
    arguments = {"a": SUBJECT_A, "b": SUBJECT_B, "season": SEASON, "probe_key": PROBE}

    probe = _stream_one_invocation(
        monkeypatch, tmp_path, "player_comparison", arguments, [{"PTS": 30.1}])

    data = _single(probe.text, "tool_call")["data"]
    assert data["name"] == "player_comparison"
    assert data["argument_count"] == 4
    assert data["unknown_argument_count"] == 1
    assert data["arguments"] == [
        {"name": "a", "value": SUBJECT_A},
        {"name": "b", "value": SUBJECT_B},
        {"name": "season", "value": SEASON},
    ]
    assert PROBE not in probe.text
    recorded = probe.recorded_arguments
    assert recorded == arguments
    for item in data["arguments"]:
        assert recorded[item["name"]] == item["value"]
    withheld = set(recorded) - {item["name"] for item in data["arguments"]}
    assert withheld == {"probe_key"}
    assert len(probe.calls) == 1

def test_stream_tool_call_counts_differ_and_agree_with_the_ledger(monkeypatch, tmp_path):
    declared = {"player": SUBJECT_A, "opponent": SUBJECT_B, "season": SEASON}
    arguments = {**declared, "surprise": PROBE, "second_surprise": PROBE}

    probe = _stream_one_invocation(
        monkeypatch, tmp_path, "head_to_head", arguments, [{"PTS": 3}])

    data = _single(probe.text, "tool_call")["data"]
    assert data["argument_count"] == 5
    assert data["unknown_argument_count"] == 2
    assert data["argument_count"] != data["unknown_argument_count"]
    assert {item["name"]: item["value"] for item in data["arguments"]} == declared
    assert probe.recorded_arguments == arguments
    assert PROBE not in probe.text

def test_stream_tool_call_withholds_internal_identity_arguments(monkeypatch, tmp_path):
    arguments = {"player_id": PRIVATE_ID, "team_id": PRIVATE_ID}

    probe = _stream_one_invocation(
        monkeypatch, tmp_path, "four_factors", arguments, [{"EFG": 0.51}])

    data = _single(probe.text, "tool_call")["data"]
    assert data["argument_count"] == 2
    assert data["unknown_argument_count"] == 0
    assert data["arguments"] == []
    assert probe.recorded_arguments == arguments
    assert PRIVATE_ID not in probe.text

def test_stream_refuses_a_capability_invoked_without_required_arguments(monkeypatch, tmp_path):
    probe = _stream_one_invocation(
        monkeypatch, tmp_path, "player_comparison",
        {"a": "", "b": SUBJECT_B}, [{"PTS": 30.1}], activity_from_route=False)

    assert probe.calls == []
    assert probe.ledger_results
    assert all(entry.data["status"] == "failed" for entry in probe.ledger_results)
    assert probe.ledger_results[-1].data["error"] == (
        "ValueError: capability 'player_comparison' is missing required "
        "arguments: a")
    assert [item["kind"] for item in probe.observed] == ["tool_call", "tool_result"]
    assert probe.observed[0]["data"]["arguments"] == [
        {"name": "a", "value": ""}, {"name": "b", "value": SUBJECT_B}]
    assert probe.observed[1]["transition"] == "failed"
    assert probe.recorded_arguments == {"a": "", "b": SUBJECT_B}
    assert _single(probe.text, "tool_call")["data"]["arguments"] == [
        {"name": "a", "value": ""}, {"name": "b", "value": SUBJECT_B}]
    assert _single(probe.text, "tool_result")["status"] == "fail"
    assert '"status":"ok"' not in probe.text
    assert probe.text.count("event: work_log") == 1
    assert '"status":"partial"' in probe.text

def test_executor_refuses_a_plan_node_missing_required_arguments_before_it_runs():
    import asyncio

    from v2 import contracts
    from v2.runtime.executor import PlanExecutor
    from v2.runtime.ledger import RunLedger
    from v2.runtime.recording import RecordedCapability

    calls: list = []
    executor = PlanExecutor({
        "player_comparison": RecordedCapability(
            _counting_capability("player_comparison", [{"PTS": 30.1}], calls),
            RunLedger("run"), turn_id="run")})
    plan = contracts.Plan(nodes=[contracts.PlanNode(
        id="node", description="describe the work",
        capability_hints=["player_comparison"], arguments={"a": SUBJECT_A})])
    task = contracts.TaskSpec(goal="x", mode="deep_dive", deliverable="x")

    try:
        asyncio.run(executor.execute(task, plan))
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("executor accepted a plan missing required arguments")

    assert "player_comparison" in message
    assert "missing required arguments: b" in message
    assert calls == []
