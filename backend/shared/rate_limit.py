import math
import os
import threading
import time
from collections import deque
from fastapi import HTTPException


class RateLimiter:
    def __init__(self, limit=30, window_s=60):
        self.limit = limit
        self.window_s = window_s
        self._hits = {}
        self._lock = threading.Lock()

    def retry_after(self, key, limit=None, window_s=None):
        lim = self.limit if limit is None else limit
        win = self.window_s if window_s is None else window_s
        now = time.monotonic()
        cutoff = now - win
        with self._lock:
            dq = self._hits.get(key)
            if dq is None:
                dq = deque()
                self._hits[key] = dq
            while dq:
                if dq[0] > cutoff:
                    break
                dq.popleft()
            if len(dq) >= lim:
                wait = dq[0] + win - now
                if wait < 1:
                    wait = 1
                for k, q in list(self._hits.items()):
                    while q:
                        if q[0] > cutoff:
                            break
                        q.popleft()
                    if not q:
                        del self._hits[k]
                return math.ceil(wait)
            dq.append(now)
            if len(self._hits) > 1024:
                for k, q in list(self._hits.items()):
                    while q:
                        if q[0] > cutoff:
                            break
                        q.popleft()
                    if not q:
                        del self._hits[k]
            return None

    def configure(self, limit=None, window_s=None):
        if limit is not None:
            self.limit = limit
        if window_s is not None:
            self.window_s = window_s

    def reset(self):
        with self._lock:
            self._hits.clear()


def _env_limit():
    try:
        value = int(os.environ.get("DIME_SQL_RERUN_RATE_LIMIT", "30"))
    except ValueError:
        return 30
    if value < 1:
        return 30
    return value


def _env_window():
    try:
        value = float(os.environ.get("DIME_SQL_RERUN_RATE_WINDOW_S", "60"))
    except ValueError:
        return 60.0
    if value <= 0:
        return 60.0
    return value


_limiter = RateLimiter()


def configure(limit=None, window_s=None):
    _limiter.configure(limit=limit, window_s=window_s)


def reset():
    _limiter.reset()


def client_ip(request) -> str:
    client = request.client
    if client is None:
        return "unknown"
    host = getattr(client, "host", None)
    if not host:
        return "unknown"
    return str(host)


def check_sql_rerun(ip: str) -> None:
    key = ip if ip else "unknown"
    retry = _limiter.retry_after(key, limit=_env_limit(), window_s=_env_window())
    if retry is not None:
        raise HTTPException(status_code=429, headers={"Retry-After": str(retry)})
