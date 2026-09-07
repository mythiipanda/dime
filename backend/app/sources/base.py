"""Source boundary. Every fetch returns a frame plus fetch metadata."""

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


def safe(source: str, season: str, fn: Any, *args: Any, **kwargs: Any) -> FetchResult:
    import time as _time

    last: Exception | None = None
    for attempt in range(3):
        try:
            frame = fn(*args, **kwargs)
            if getattr(frame, "height", 0) > 0:
                return FetchResult(frame=frame, meta=FetchMeta(source, season))
            last = RuntimeError("empty upstream response")
        except Exception as exc:
            last = exc
        _time.sleep(4 * (attempt + 1))
    return empty(source, season, str(last))
