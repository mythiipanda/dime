import asyncio
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.api import routes
from v2.api.sse import encode_event

FAIL_MESSAGE = "boom-after-replan"

def _install_stubs(monkeypatch, tmp_path):
    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setenv("DIME_V2_ACTIVITY_DIR", str(tmp_path / "activity"))
    monkeypatch.setenv(
        "DIME_CONVERSATION_STORE", str(tmp_path / "conv.sqlite3"))
    from v2.conversations import ConversationStore
    monkeypatch.setattr(
        routes, "_CONVERSATIONS",
        ConversationStore(tmp_path / "c2.sqlite3"))
    providers_mod = types.ModuleType("shared.providers")
    providers_mod.resolve_model_id = lambda model: ("fake", "fake-model")
    monkeypatch.setitem(sys.modules, "shared.providers", providers_mod)

    class _FakePolicy:
        publish = True

        def model_dump(self):
            return {}

    policy_mod = types.ModuleType("v2.runtime.policy")

    class _FakeExecutionPolicy:
        @staticmethod
        def live(**kwargs):
            return _FakePolicy()

        @staticmethod
        def shadow(**kwargs):
            return _FakePolicy()

        @staticmethod
        def model_validate(data):
            return _FakePolicy()

    policy_mod.ExecutionPolicy = _FakeExecutionPolicy
    monkeypatch.setitem(sys.modules, "v2.runtime.policy", policy_mod)
    ledger_mod = types.ModuleType("v2.runtime.ledger")

    class _FakeLedgerKind:
        TOOL_CALL = "tool_call"
        TOOL_RESULT = "tool_result"
        STEP_END = "step_end"

    ledger_mod.LedgerKind = _FakeLedgerKind
    monkeypatch.setitem(sys.modules, "v2.runtime.ledger", ledger_mod)
    adapters_mod = types.ModuleType("v2.adapters")
    adapters_mod.CAPABILITIES = set()
    monkeypatch.setitem(sys.modules, "v2.adapters", adapters_mod)
    assembly_mod = types.ModuleType("v2.runtime.assembly")

    class _BoomRuntime:
        async def run(self, q, run_id=None, context=None):
            raise RuntimeError(FAIL_MESSAGE)

    ledger = types.SimpleNamespace(entries=[
        types.SimpleNamespace(
            kind="step_end", step_id="replan", data={"duration_ms": 12})
    ])
    assembly_mod.build_runtime = lambda **kwargs: (_BoomRuntime(), ledger)
    monkeypatch.setitem(sys.modules, "v2.runtime.assembly", assembly_mod)
    import shared.config as real_config
    monkeypatch.setattr(real_config, "settings", types.SimpleNamespace(
        dime_v2_pre_tool_timeout_s=5.0,
        dime_v2_run_timeout_s=5.0,
        dime_v2_node_timeout_s=5.0))

def _collect(body):
    async def drive():
        resp = await routes.quick_answer_stream(body)
        return [chunk async for chunk in resp.body_iterator]
    return asyncio.run(drive())

def _parsed(chunks):
    out = []
    for chunk in chunks:
        head, _, rest = chunk.partition("\n")
        name = head.replace("event: ", "")
        payload = json.loads(rest.replace("data: ", "").strip())
        out.append((name, payload))
    return out

def test_default_stream_carries_no_run_diagnostic(monkeypatch, tmp_path):
    _install_stubs(monkeypatch, tmp_path)
    events = _parsed(_collect(routes.QuickAnswerBody(q="Who led in assists?")))
    names = [name for name, _ in events]
    assert "run_diagnostic" not in names
    assert "final_answer" in names
    final = [payload for name, payload in events if name == "final_answer"][0]
    assert final["text"] == (
        "I could not verify a publishable answer from the available data. ")
    assert {"kind": "execution_failure", "blocks": []} in final["carry"]["gaps"]

def test_diagnostics_stream_surfaces_run_diagnostic(monkeypatch, tmp_path):
    _install_stubs(monkeypatch, tmp_path)
    body = routes.QuickAnswerBody(q="Who led in assists?", diagnostics=True)
    events = _parsed(_collect(body))
    diag = [payload for name, payload in events if name == "run_diagnostic"]
    assert len(diag) == 1
    assert diag[0]["error_type"] == "RuntimeError"
    assert diag[0]["message"] == FAIL_MESSAGE
    assert diag[0]["last_stage"] == "replan"
    names = [name for name, _ in events]
    assert "final_answer" in names
    final = [payload for name, payload in events if name == "final_answer"][0]
    assert final["text"] == (
        "I could not verify a publishable answer from the available data. ")
    assert {"kind": "execution_failure", "blocks": []} in final["carry"]["gaps"]

def test_run_diagnostic_encode_event_gating():
    from v2.api.events import RunDiagnostic
    event = RunDiagnostic(
        run_id="run-" + "a" * 32,
        error_type="RuntimeError",
        message=FAIL_MESSAGE,
        last_stage="replan")
    assert encode_event(event) is None
    chunk = encode_event(event, diagnostics=True)
    assert chunk is not None
    assert chunk.startswith("event: run_diagnostic\n")
    assert "RuntimeError" in chunk
