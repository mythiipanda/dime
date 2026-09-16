import asyncio

from app import routes


async def _events():
    yield {"type": "tool_call", "data": {"name": "get_standings", "args": {}}}
    yield {"type": "custom_data", "data": {
        "node": "analytics", "tables": [{"tool": "standings", "rows": []}],
    }}
    yield {"type": "final_answer", "data": {"text": "Boston won 61 games."}}
    yield {"type": "graph_end", "data": {}}


def _streamed(monkeypatch, *, mode: str, shadow=None):
    monkeypatch.setenv("DIME_RUNTIME_V2", mode)
    monkeypatch.setattr(routes, "run_chat", lambda *args, **kwargs: _events())
    if shadow is not None:
        monkeypatch.setattr(routes, "_record_v2_shadow", shadow)

    async def collect():
        chunks = [chunk async for chunk in routes._stream("record?", None)]
        await asyncio.sleep(0)
        return chunks

    return asyncio.run(collect())


def test_v1_shadow_runs_silently_without_changing_primary_stream(monkeypatch):
    captured = {}

    async def shadow(question, model, history, primary):
        captured["question"] = question
        captured["outcome"] = await primary

    shadow_chunks = _streamed(monkeypatch, mode="shadow", shadow=shadow)
    off_chunks = _streamed(monkeypatch, mode="off")

    assert shadow_chunks == off_chunks
    assert captured["question"] == "record?"
    assert captured["outcome"].status == "ok"
    assert captured["outcome"].answer == "Boston won 61 games."
    assert captured["outcome"].capabilities == ["standings"]
    assert captured["outcome"].evidence_count == 1
    assert captured["outcome"].supported_claims is None
    assert captured["outcome"].total_claims is None


def test_shadow_failure_cannot_change_primary_stream(monkeypatch):
    async def failed_shadow(*args, **kwargs):
        raise RuntimeError("shadow failed")

    shadow_chunks = _streamed(monkeypatch, mode="shadow", shadow=failed_shadow)
    off_chunks = _streamed(monkeypatch, mode="off")

    assert shadow_chunks == off_chunks


def test_v1_shadow_outcome_marks_error_with_answer_partial():
    result = routes._v1_shadow_outcome(
        answer="partial answer", capabilities=[], evidence_count=0,
        had_error=True, duration_ms=1)
    assert result.status == "partial"


def test_v2_shadow_failure_is_recorded_as_failed_comparison(monkeypatch, tmp_path):
    from v2.runtime.shadow import ShadowStore

    class FailedRuntime:
        async def run(self, *args, **kwargs):
            raise RuntimeError("v2 failed")

    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda model: ("inception", "model"))
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime", lambda **kwargs: (FailedRuntime(), object()))
    store_path = tmp_path / "shadow.jsonl"
    monkeypatch.setenv("DIME_V2_SHADOW_STORE", str(store_path))

    async def exercise():
        loop = asyncio.get_running_loop()
        primary = loop.create_future()
        primary.set_result(routes._v1_shadow_outcome(
            answer="v1 answer", capabilities=[], evidence_count=0,
            had_error=False, duration_ms=1))
        await routes._record_v2_shadow("record?", None, [], primary)

    asyncio.run(exercise())
    records = ShadowStore(store_path).read()
    assert len(records) == 1
    assert records[0].v1.status == "ok"
    assert records[0].v2.status == "failed"
    assert "failure" in records[0].differences


def test_v2_shadow_cancellation_is_recorded_as_cancelled(monkeypatch, tmp_path):
    from v2.runtime.shadow import ShadowStore

    class CancelledRuntime:
        async def run(self, *args, **kwargs):
            raise asyncio.CancelledError()

    monkeypatch.setattr(
        "app.providers.resolve_model_id", lambda model: ("inception", "model"))
    monkeypatch.setattr(
        "v2.runtime.assembly.build_runtime", lambda **kwargs: (CancelledRuntime(), object()))
    store_path = tmp_path / "shadow.jsonl"
    monkeypatch.setenv("DIME_V2_SHADOW_STORE", str(store_path))

    async def exercise():
        loop = asyncio.get_running_loop()
        primary = loop.create_future()
        primary.set_result(routes._v1_shadow_outcome(
            answer="v1 answer", capabilities=[], evidence_count=0,
            had_error=False, duration_ms=1))
        await routes._record_v2_shadow("record?", None, [], primary)

    asyncio.run(exercise())
    records = ShadowStore(store_path).read()
    assert records[0].v2.status == "cancelled"


def test_v1_shadow_projection_is_bounded_and_cannot_break_primary():
    from v2.adapters.capabilities import CAPABILITIES

    tool_names = [item.tool_name for item in CAPABILITIES.values()]
    result = routes._v1_shadow_outcome(
        answer="x" * 250_000,
        capabilities=tool_names + tool_names,
        evidence_count=100,
        had_error=False,
        duration_ms=1,
    )

    assert len(result.answer) == 200_000
    assert len(result.capabilities) <= 32
    assert len(result.capabilities) == len(set(result.capabilities))
