import json

from scripts.latency_breakdown import summarize


def _entry(sequence, kind, turn="t", step=None, call=None, data=None, at="2026-10-02T00:00:00+00:00"):
    row = {"sequence": sequence, "run_id": "run", "kind": kind,
           "recorded_at": at, "turn_id": turn, "data": data or {}}
    if step is not None:
        row["step_id"] = step
    if call is not None:
        row["call_id"] = call
    return row


def test_summarize_pairs_stages_models_and_tools():
    lines = [
        _entry(1, "turn/start", data={"request": "q"}),
        _entry(2, "step/start", step="plan"),
        _entry(3, "model/request", call="model:t:1", data={
            "provider": "p", "model": "m", "route": "answer",
            "prompt_hash": "a" * 64, "context_hash": "b" * 64,
            "tool_schema_hash": "c" * 64, "planner_version": "v2"}),
        _entry(4, "assistant/attempt", call="model:t:1", data={
            "status": "accepted", "output": {}, "provider": "p",
            "model": "m", "used_fallback": False, "duration_ms": 40000}),
        _entry(5, "step/end", step="plan",
               data={"reason": "complete", "duration_ms": 41000}),
        _entry(6, "step/start", step="execute"),
        _entry(7, "tool/call", step="execute", call="tool:t:n:1", data={
            "name": "playoffs", "args": {}}),
        _entry(8, "tool/result", step="execute", call="tool:t:n:1", data={
            "status": "ok", "evidence": {}, "duration_ms": 15}),
        _entry(9, "step/end", step="execute",
               data={"reason": "complete", "duration_ms": 20}),
        _entry(10, "turn/end", data={"reason": "complete", "duration_ms": 42000}),
    ]
    text = "\n".join(json.dumps(row) for row in lines)
    report = summarize(text.splitlines())
    assert report["turn_ms"] == 42000
    assert report["stages"] == {"plan": 41000, "execute": 20}
    assert report["llm"]["calls"] == 1
    assert report["llm"]["total_ms"] == 40000
    assert report["tools"]["playoffs"]["calls"] == 1
    assert report["tools"]["playoffs"]["total_ms"] == 15


def test_summarize_counts_failed_attempts_without_output():
    lines = [
        _entry(1, "turn/start", data={"request": "q"}),
        _entry(2, "model/request", call="model:t:1", data={
            "provider": "p", "model": "m", "route": "answer",
            "prompt_hash": "a" * 64, "context_hash": "b" * 64,
            "tool_schema_hash": "c" * 64, "planner_version": "v2"}),
        _entry(3, "assistant/attempt", call="model:t:1", data={
            "status": "failed", "error": "bad", "duration_ms": 5000}),
        _entry(4, "turn/end", data={"reason": "failed", "duration_ms": 6000}),
    ]
    report = summarize("\n".join(json.dumps(row) for row in lines).splitlines())
    assert report["llm"]["calls"] == 1
    assert report["llm"]["total_ms"] == 5000
    assert report["stages"] == {}
