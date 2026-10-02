#!/usr/bin/env python3
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


def summarize(lines):
    stages = {}
    llm_ms = []
    tools = {}
    turn_ms = None
    open_steps = {}
    open_models = {}
    open_tools = {}
    for line in lines:
        if not str(line or "").strip():
            continue
        try:
            row = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        data = row.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        here = _at(row.get("recorded_at"))
        if kind == "step/start":
            open_steps[(row.get("turn_id"), row.get("step_id"))] = here
        elif kind == "step/end":
            key = (row.get("turn_id"), row.get("step_id"))
            started = open_steps.pop(key, None)
            span = _ms(data.get("duration_ms"))
            if span is None and started is not None and here is not None:
                span = max(0, round((here - started).total_seconds() * 1000))
            if span is not None and row.get("step_id"):
                stages[str(row["step_id"])] = span
        elif kind == "model/request":
            if row.get("call_id"):
                open_models[row["call_id"]] = here
        elif kind == "assistant/attempt":
            started = open_models.pop(row.get("call_id"), None)
            span = _ms(data.get("duration_ms"))
            if span is None and started is not None and here is not None:
                span = max(0, round((here - started).total_seconds() * 1000))
            if span is not None:
                llm_ms.append(span)
        elif kind == "tool/call":
            if row.get("call_id"):
                name = (data.get("name") or "")
                open_tools[row["call_id"]] = (here, str(name))
        elif kind == "tool/result":
            started = open_tools.pop(row.get("call_id"), (None, ""))
            span = _ms(data.get("duration_ms"))
            if span is None and started[0] is not None and here is not None:
                span = max(0, round((here - started[0]).total_seconds() * 1000))
            if span is not None:
                entry = tools.setdefault(started[1] or "unknown",
                                         {"calls": 0, "total_ms": 0, "max_ms": 0})
                entry["calls"] += 1
                entry["total_ms"] += span
                entry["max_ms"] = max(entry["max_ms"], span)
        elif kind == "turn/end":
            span = _ms(data.get("duration_ms"))
            turn_ms = span if turn_ms is None else turn_ms + span
    return {
        "turn_ms": turn_ms,
        "stages": stages,
        "llm": {"calls": len(llm_ms), "total_ms": sum(llm_ms),
                "max_ms": max(llm_ms) if llm_ms else 0},
        "tools": tools,
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
