
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import atexit
import json
import os
import polars as pl

@dataclass
class FetchMeta:
    source: str
    season: str
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

@dataclass
class FetchResult:
    frame: pl.DataFrame
    meta: FetchMeta
    ok: bool = True
    error: str = ""

def empty(source: str, season: str, error: str) -> FetchResult:
    return FetchResult(
        frame=pl.DataFrame(),
        meta=FetchMeta(source=source, season=season),
        ok=False,
        error=error[:300],
    )

_TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "data" / "seed-telemetry"
_fetch_records: dict[tuple[str, str], dict] = {}


def _outcomes() -> dict:
    return {
        "ok": 0,
        "empty_response": 0,
        "client_error": 0,
        "throttled": 0,
        "parse_error": 0,
        "fetch_error": 0,
    }


def record_fetch(source: str, season: str, outcome: str,
                 status_code: int | None = None) -> None:
    key = (source, season)
    rec = _fetch_records.setdefault(
        key, {"source": source, "season": season, "status_codes": {}, **_outcomes()}
    )
    rec[outcome] = rec.get(outcome, 0) + 1
    if isinstance(status_code, int):
        bucket = str(status_code)
        rec["status_codes"][bucket] = rec["status_codes"].get(bucket, 0) + 1


def flush_seed_telemetry(directory: Path | None = None) -> Path | None:
    if not _fetch_records:
        return None
    target = (directory or _TELEMETRY_DIR)
    payload = {
        "pid": os.getpid(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "fetches": sorted(
            (dict(rec) for rec in _fetch_records.values()),
            key=lambda rec: (rec["source"], rec["season"]),
        ),
    }
    with suppress(Exception):
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = target / f"{stamp}-{os.getpid()}.json"
        path.write_text(json.dumps(payload, indent=2))
        _fetch_records.clear()
        return path
    return None


def reset_seed_telemetry() -> None:
    _fetch_records.clear()


atexit.register(flush_seed_telemetry)


def safe(source: str, season: str, fn: Any, *args: Any,
         accept_empty: bool = False, **kwargs: Any) -> FetchResult:
    import os as _os
    import time as _time

    try:
        import duckdb as _duckdb
        _permanent_duckdb = (
            _duckdb.CatalogException,
            _duckdb.ParserException,
        )
    except Exception:
        _permanent_duckdb = ()

    attempts = int(_os.environ.get("DIME_LIVE_ATTEMPTS", "2"))
    backoff = float(_os.environ.get("DIME_LIVE_BACKOFF_S", "2"))
    last: Exception | None = None
    last_status: int | None = None
    saw_throttle = False
    for attempt in range(attempts):
        try:
            frame = fn(*args, **kwargs)
            if getattr(frame, "height", 0) > 0 or accept_empty:
                record_fetch(source, season, "ok")
                return FetchResult(frame=frame, meta=FetchMeta(source, season))
            last = RuntimeError("empty upstream response")
            last_status = None
        except Exception as exc:
            last = exc
            _status = getattr(getattr(exc, "response", None), "status_code", None)
            last_status = _status if isinstance(_status, int) else None
            if last_status == 429:
                saw_throttle = True
            if isinstance(_status, int) and 400 <= _status <= 499 and _status != 429:
                record_fetch(source, season, "client_error", _status)
                return empty(source, season, str(last))
            if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
                record_fetch(source, season, "parse_error")
                return empty(source, season, str(last))
            if _permanent_duckdb and isinstance(exc, _permanent_duckdb):
                record_fetch(source, season, "parse_error")
                return empty(source, season, str(last))
        if attempt < attempts - 1:
            _time.sleep(backoff * (attempt + 1))
    if isinstance(last, RuntimeError) and str(last) == "empty upstream response":
        record_fetch(source, season, "empty_response")
    elif saw_throttle:
        record_fetch(source, season, "throttled", 429)
    else:
        record_fetch(source, season, "fetch_error", last_status)
    return empty(source, season, str(last))
