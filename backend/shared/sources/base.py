
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
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
    for attempt in range(attempts):
        try:
            frame = fn(*args, **kwargs)
            if getattr(frame, "height", 0) > 0 or accept_empty:
                return FetchResult(frame=frame, meta=FetchMeta(source, season))
            last = RuntimeError("empty upstream response")
        except Exception as exc:
            last = exc
            _status = getattr(getattr(exc, "response", None), "status_code", None)
            if isinstance(_status, int) and 400 <= _status <= 499 and _status != 429:
                return empty(source, season, str(last))
            if isinstance(exc, (ValueError, TypeError, KeyError, AttributeError)):
                return empty(source, season, str(last))
            if _permanent_duckdb and isinstance(exc, _permanent_duckdb):
                return empty(source, season, str(last))
        if attempt < attempts - 1:
            _time.sleep(backoff * (attempt + 1))
    return empty(source, season, str(last))
