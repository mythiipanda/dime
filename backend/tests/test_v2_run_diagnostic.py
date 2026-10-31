import asyncio
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.api.sse import encode_event

FAIL_MESSAGE = "boom-after-replan"



def _parsed(chunks):
    out = []
    for chunk in chunks:
        head, _, rest = chunk.partition("\n")
        name = head.replace("event: ", "")
        payload = json.loads(rest.replace("data: ", "").strip())
        out.append((name, payload))
    return out



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
