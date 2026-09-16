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
