import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def _ms(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

def _at(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed

def _span(data, started, here):
    span = _ms(data.get("duration_ms"))
    if span is None and started is not None and here is not None:
        span = max(0, round((here - started).total_seconds() * 1000))
    return span

def _step_start(row, data, here, acc):
    acc["open_steps"][(row.get("turn_id"), row.get("step_id"))] = here

def _step_end(row, data, here, acc):
    key = (row.get("turn_id"), row.get("step_id"))
    started = acc["open_steps"].pop(key, None)
    span = _span(data, started, here)
    if span is not None and row.get("step_id"):
        acc["stages"][str(row["step_id"])] = span

def _model_request(row, data, here, acc):
    if row.get("call_id"):
        acc["open_models"][row["call_id"]] = here

def _assistant_attempt(row, data, here, acc):
    started = acc["open_models"].pop(row.get("call_id"), None)
    span = _span(data, started, here)
    if span is not None:
        acc["llm_ms"].append(span)

def _tool_call(row, data, here, acc):
    if row.get("call_id"):
        acc["open_tools"][row["call_id"]] = (here, str(data.get("name") or ""))

def _tool_result(row, data, here, acc):
    started = acc["open_tools"].pop(row.get("call_id"), (None, ""))
    span = _span(data, started[0], here)
    if span is None:
        return
    entry = acc["tools"].setdefault(started[1] or "unknown",
                                     {"calls": 0, "total_ms": 0, "max_ms": 0})
    entry["calls"] += 1
    entry["total_ms"] += span
    entry["max_ms"] = max(entry["max_ms"], span)

def _turn_end(row, data, here, acc):
    span = _ms(data.get("duration_ms"))
    acc["turn_ms"] = span if acc["turn_ms"] is None else acc["turn_ms"] + span

_HANDLERS = {
    "step/start": _step_start,
    "step/end": _step_end,
    "model/request": _model_request,
    "assistant/attempt": _assistant_attempt,
    "tool/call": _tool_call,
    "tool/result": _tool_result,
    "turn/end": _turn_end,
}

def _row(line):
    if not str(line or "").strip():
        return None
    try:
        row = json.loads(line)
    except (TypeError, ValueError):
        return None
    return row if isinstance(row, dict) else None

def _ledger():
    return {"turn_ms": None, "stages": {}, "llm_ms": [], "tools": {},
            "open_steps": {}, "open_models": {}, "open_tools": {}}

def summarize(lines):
    acc = _ledger()
    for line in lines:
        row = _row(line)
        if row is None:
            continue
        handler = _HANDLERS.get(row.get("kind"))
        if handler is None:
            continue
        data = row.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        handler(row, data, _at(row.get("recorded_at")), acc)
    llm_ms = acc["llm_ms"]
    return {
        "turn_ms": acc["turn_ms"],
        "stages": acc["stages"],
        "llm": {"calls": len(llm_ms), "total_ms": sum(llm_ms),
                "max_ms": max(llm_ms) if llm_ms else 0},
        "tools": acc["tools"],
    }

def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("ledger", help="ledger JSONL path")
    ns = args.parse_args()
    report = summarize(Path(ns.ledger).read_text().splitlines())
    print("turn_ms: %s" % report["turn_ms"])
    for name, span in report["stages"].items():
        print("stage %s: %dms" % (name, span))
    llm = report["llm"]
    print("llm: calls=%d total_ms=%d max_ms=%d" % (
        llm["calls"], llm["total_ms"], llm["max_ms"]))
    for name, entry in sorted(report["tools"].items()):
        print("tool %s: calls=%d total_ms=%d max_ms=%d" % (
            name, entry["calls"], entry["total_ms"], entry["max_ms"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
