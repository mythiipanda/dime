"""Structured trace logging for eval runs. Starts now.

Every harness run emits one JSONL file under backend/evals/traces/.
The schema is fixed in trace_schema.md; when the product later logs
live traffic, it must conform to the same event names so the monthly
crew pass can mine recurring failures into skill revisions.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACE_DIR = HERE / "traces"

_current = {"run_id": None, "path": None}


def new_run(ctx):
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"{run_id}.jsonl"
    _current["run_id"] = run_id
    _current["path"] = path
    emit("run_started", {
        "flags": {k: v for k, v in ctx.items()
                  if k in ("live_llm", "live_judge", "live_backend")
                  or k == "warehouse" and v},
    })
    return run_id


def emit(event, fields=None):
    """Append one trace event. Never raises; tracing must not break evals."""
    try:
        path = _current.get("path")
        if path is None:
            return
        rec = {"ts": time.time(), "run_id": _current["run_id"], "event": event}
        if fields:
            rec.update(fields)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


def run_id():
    return _current.get("run_id")
