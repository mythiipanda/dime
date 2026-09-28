"""Shared live-backend client (stdlib urllib SSE).

Protocol mirrors backend/tests/benchmark/runner.py: POST
{base}/api/v1/chat/stream with {"q": ..., "thread": ...}; the
`final_answer` SSE event carries the answer text.
"""

from __future__ import annotations

import json
import time
import urllib.request
import uuid


def ask(base: str, question: str, timeout_s: float = 200.0) -> dict:
    body = json.dumps({"q": question,
                       "thread": f"evals-{uuid.uuid4().hex[:10]}"}).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/v1/chat/stream", data=body,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    text, tool_calls, streamed = "", 0, 0
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        event = None
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
                continue
            if line.startswith("data: ") and event:
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    data = {}
                if event == "final_answer":
                    text = str(data.get("text", ""))
                elif event == "tool_call":
                    tool_calls += 1
                elif event in ("token", "thought_token"):
                    streamed += len(str(data.get("text", "")))
                event = None
    return {"text": text, "seconds": round(time.time() - t0, 2),
            "tool_calls": tool_calls, "streamed_chars": streamed}
