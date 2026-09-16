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
