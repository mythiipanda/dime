"""Shared live-backend client (stdlib urllib SSE).

Protocol mirrors backend/tests/benchmark/runner.py: POST
{base}/api/v1/chat/stream with {"q": ..., "thread": ...}; the
`final_answer` SSE event carries the answer text.

Also home to the live-eval warehouse contract: the harness grades a
live backend ONLY against the stable fixture warehouse it builds
itself, and verifies BEFORE grading that the backend serves exactly
that file. The backend learns its warehouse location from the
DIME_WAREHOUSE env var (backend/shared/store.py) — the real,
production mechanism, no test-only wiring. The backend reports which
warehouse it bound at startup via GET {base}/api/revision
(startup-frozen sha256 of the warehouse file, v2/api/routes.py); the
harness compares that against the sha256 of its fixture file. Any
live report produced without this verification is INVALID.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
DATA = EVALS_DIR / "data"

#: Stable fixture path. A fixed location (not a per-run tempdir) so the
#: operator can point the backend at it BEFORE the harness runs:
#:   1. python3 backend/evals/run.py --build-fixture
#:   2. DIME_WAREHOUSE=<path> uvicorn app.main:app ...
#:   3. python3 backend/evals/run.py --live-backend <url>
FIXTURE_NAME = "fixture.duckdb"


def fixture_path() -> Path:
    return DATA / FIXTURE_NAME


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# Mirrors the table backend/shared/store.py::_connect_once creates on its
# first read-write open of a non-canonical warehouse. Pre-creating it at
# fixture build time keeps the file bytes stable across later backend
# connects, so the startup-bound sha256 the backend reports stays
# comparable to the harness's sha256 of the same file.
_FETCH_LOG_DDL = (
    "CREATE TABLE IF NOT EXISTS fetch_log("
    "dataset VARCHAR, season VARCHAR, entity VARCHAR, "
    "source VARCHAR, fetched_at VARCHAR, rows INTEGER)"
)


def ensure_fixture(rebuild: bool = False) -> tuple[Path, str]:
    """Build the stable fixture warehouse if missing; return (path, sha256).

    After building, opens the file once in read-write mode to create the
    fetch_log table exactly as the backend's first connect would — so a
    backend pointed at this file never mutates its bytes on first query
    and the sha256 stays stable across runs.
    """
    try:
        import duckdb
    except ImportError:
        raise RuntimeError(
            "duckdb is required to build the live-eval fixture "
            "(pip install duckdb)")
    path = fixture_path()
    if rebuild and path.is_file():
        path.unlink()
    if not path.is_file():
        sys.path.insert(0, str(EVALS_DIR))
        from suites import golden_warehouse as gw
        gw.build_fixture(path)
        con = duckdb.connect(str(path))
        try:
            con.execute(_FETCH_LOG_DDL)
        finally:
            con.close()
    return path, sha256_file(path)


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


def verify_warehouse(base: str, fixture_sha256: str,
                     timeout_s: float = 15.0) -> tuple[bool, str, dict | None]:
    """Confirm the backend serves the fixture warehouse, before grading.

    GET {base}/api/revision carries the backend's startup-frozen
    warehouse identity (sha256 of the DIME_WAREHOUSE file it bound at
    process start). Returns (verified, detail, identity). verified is
    True ONLY when the reported sha256 equals the harness's sha256 of
    the fixture file it will grade against. Anything else — unreachable
    endpoint, bad payload, hash mismatch — means grading would measure
    the wrong warehouse, and the caller must label its report INVALID
    instead of grading.
    """
    url = f"{base.rstrip('/')}/api/revision"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status != 200:
                return (False,
                        f"identity endpoint {url} returned HTTP {resp.status}; "
                        "cannot confirm the backend's warehouse — "
                        "live report INVALID", None)
            try:
                payload = json.loads(resp.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                return (False,
                        f"identity endpoint {url} returned unparsable JSON "
                        f"({exc}); cannot confirm the backend's warehouse — "
                        "live report INVALID", None)
    except Exception as exc:
        return (False,
                f"identity endpoint {url} unreachable ({exc}); cannot "
                "confirm the backend's warehouse — live report INVALID",
                None)
    identity = (payload.get("warehouse") or {}) if isinstance(payload,
                                                             dict) else {}
    reported = identity.get("sha256")
    if not reported:
        return (False,
                "identity endpoint answered but reported no warehouse sha256; "
                "cannot confirm the backend's warehouse — live report "
                "INVALID", identity or None)
    if reported != fixture_sha256:
        wid = identity.get("warehouse_id", "?")
        detail = (f"warehouse sha256 mismatch: backend serves "
                  f"{reported[:16]}… (warehouse_id={wid}) but the grading "
                  f"fixture is {fixture_sha256[:16]}…; point the backend at "
                  f"the fixture (DIME_WAREHOUSE={fixture_path()}) and "
                  "restart it before grading — live report INVALID")
        if wid == "frozen-eval":
            detail += (" (backend is on the canonical benchmark warehouse, "
                       "not the fixture)")
        return False, detail, identity
    return (True,
            f"warehouse verified: backend sha256 == fixture sha256 "
            f"({fixture_sha256[:16]}…)", identity)
