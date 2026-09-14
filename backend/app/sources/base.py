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


def safe(source: str, season: str, fn: Any, *args: Any,
         accept_empty: bool = False, **kwargs: Any) -> FetchResult:
    """Retry wrapper. Empty-but-successful results are retried unless the
    caller opts in to accept_empty (a valid empty answer, e.g. no games
    on a scoreboard date, is not a failure).

    Query-time latency policy: stats.nba.com endpoint-blocks datacenter
    IPs, so retries mostly multiply a guaranteed timeout. Defaults cut
    worst-case stall from ~54s to ~24s; DIME_LIVE_ATTEMPTS /
    DIME_LIVE_BACKOFF_S override for seeding scripts that want patience.
    """
    import os as _os
    import time as _time

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
        if attempt < attempts - 1:
            _time.sleep(backoff * (attempt + 1))
    return empty(source, season, str(last))
