import json
import math

from app.routes import _sanitize_sse_event


def test_tool_result_failure_hides_provider_and_transport_details():
    public = _sanitize_sse_event("tool_result", {
        "node": "tools",
        "name": "web_fetch",
        "status": "fail",
        "rows": 0,
        "error": "ClientError: 403 for https://secret.example/token=abc",
        "sql": "select private_column from internal_table",
        "summary": "provider account secret-name failed",
    })

    assert public == {
        "node": "tools", "name": "web_fetch", "status": "fail",
        "rows": 0, "error": "Tool failed",
    }


def test_successful_tool_result_keeps_public_receipt():
    receipt = {"node": "tools", "name": "standings", "status": "ok", "rows": 30}
    assert _sanitize_sse_event("tool_result", receipt) == receipt


def test_thought_tokens_never_publish_raw_model_reasoning():
    public = _sanitize_sse_event("thought_token", {
        "node": "data_retrieval",
        "agent": "league",
        "text": "I should query private_table then inspect /srv/secrets",
    })

    assert public == {
        "node": "data_retrieval",
        "agent": "league",
        "text": "Working through the evidence...",
    }


def test_tool_call_drops_raw_arguments_at_public_boundary():
    public = _sanitize_sse_event("tool_call", {
        "node": "tools",
        "name": "text_to_sql",
        "label": "Querying the warehouse",
        "summary": "standings for Boston",
        "agent": "league",
        "args": {"sql": "select secret from private_table", "token": "abc"},
    })

    assert public == {
        "node": "tools", "name": "text_to_sql",
        "label": "Querying the warehouse", "summary": "standings for Boston",
        "agent": "league",
    }


def test_successful_tool_result_drops_unknown_internal_fields():
    public = _sanitize_sse_event("tool_result", {
        "node": "tools", "name": "standings", "status": "ok", "rows": 30,
        "internal_trace": "/srv/private", "provider_payload": {"token": "abc"},
    })
    assert public == {
        "node": "tools", "name": "standings", "status": "ok", "rows": 30,
    }


def test_thought_stream_replaces_internal_or_unbounded_text():
    for text in (
        "Traceback: provider failed at /srv/app.py",
        "SELECT secret FROM private_table",
        "x" * 1001,
    ):
        public = _sanitize_sse_event("thought_stream", {
            "node": "data_retrieval", "text": text,
        })
        assert public["text"] == "Working through the evidence..."


def test_curated_thought_stream_status_remains_visible():
    public = _sanitize_sse_event("thought_stream", {
        "node": "data_retrieval", "text": "Reading standings from the warehouse.",
    })
    assert public["text"] == "Reading standings from the warehouse."


def test_draft_answer_tokens_are_not_published_before_final_guard():
    public = _sanitize_sse_event("token", {
        "text": "Boston won 99 games and private evidence says so.",
    })
    assert public == {"text": ""}


def test_remaining_public_events_drop_unknown_internal_fields():
    cases = [
        ("node_update", {"node": "tools", "status": "complete", "plan": "private"},
         {"node": "tools", "status": "complete"}),
        ("custom_data", {"node": "analytics", "tables": [], "ledger": "private"},
         {"node": "analytics", "tables": []}),
        ("final_answer", {"text": "answer", "carry": {"teams": ["Boston"]},
                          "verification": "private"},
         {"text": "answer", "carry": {"teams": ["Boston"]}}),
        ("suggestions", {"items": ["next"], "prompt": "private"},
         {"items": ["next"]}),
        ("graph_end", {"ok": True, "runtime": "private"}, {"ok": True}),
    ]
    for event_type, payload, expected in cases:
        assert _sanitize_sse_event(event_type, payload) == expected


def test_unknown_event_type_fails_closed():
    assert _sanitize_sse_event("internal_debug", {"secret": "value"}) is None


def test_unknown_event_is_not_framed_on_public_stream(monkeypatch):
    import asyncio
    from app import routes

    async def events():
        yield {"type": "internal_debug", "data": {"secret": "value"}}
        yield {"type": "graph_end", "data": {"ok": True}}

    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    monkeypatch.setattr(routes, "run_chat", lambda *args, **kwargs: events())

    async def collect():
        return "".join([chunk async for chunk in routes._stream("q", None)])

    stream = asyncio.run(collect())
    assert "internal_debug" not in stream
    assert "secret" not in stream
    assert "event: graph_end" in stream


def test_structured_public_payloads_are_recursively_bounded():
    nested = {"leaf": "value"}
    for _ in range(10):
        nested = {"child": nested}
    public = _sanitize_sse_event("custom_data", {
        "node": "analytics",
        "tables": [{"tool": "x", "rows": nested}] * 1001,
        "unverified_numbers": ["9" * 250_000],
    })

    assert len(public["tables"]) == 1000
    cursor = public["tables"][0]["rows"]
    for _ in range(6):
        cursor = cursor["child"]
    assert cursor["child"] is None
    assert len(public["unverified_numbers"][0]) == 200_000


def test_public_projection_rejects_non_finite_numbers_before_json_framing():
    from app.sse import emit_sse

    public = _sanitize_sse_event("custom_data", {
        "tables": [{"nan": math.nan, "pos_inf": math.inf,
                    "neg_inf": -math.inf, "valid": 1.5}],
    })

    assert public["tables"] == [{
        "nan": None, "pos_inf": None, "neg_inf": None, "valid": 1.5,
    }]
    payload = emit_sse("custom_data", public).split("data: ", 1)[1].strip()
    assert json.loads(payload) == public
    assert "NaN" not in payload
    assert "Infinity" not in payload


def test_sse_framing_fails_closed_if_projection_is_bypassed():
    import pytest
    from app.sse import emit_sse

    with pytest.raises(ValueError, match="JSON compliant"):
        emit_sse("custom_data", {"value": math.nan})


def test_heartbeat_propagates_inner_stream_failure_without_hanging():
    import asyncio
    import pytest
    from app.sse import with_heartbeat

    async def broken():
        yield "first"
        raise RuntimeError("stream failed")

    async def exercise():
        chunks = []
        with pytest.raises(RuntimeError, match="stream failed"):
            async for chunk in with_heartbeat(broken(), interval_s=0.01):
                chunks.append(chunk)
        return chunks

    assert asyncio.run(asyncio.wait_for(exercise(), timeout=0.2)) == ["first"]


def test_heartbeat_cancellation_closes_inner_stream():
    import asyncio
    from app.sse import with_heartbeat

    closed = asyncio.Event()

    async def hanging():
        try:
            yield "first"
            await asyncio.Event().wait()
        finally:
            closed.set()

    async def exercise():
        stream = with_heartbeat(hanging(), interval_s=10)
        assert await anext(stream) == "first"
        await stream.aclose()
        await asyncio.wait_for(closed.wait(), timeout=0.2)

    asyncio.run(exercise())
