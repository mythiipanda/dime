import os
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb

from .. import file_lock


def _pkg():
    return sys.modules[__package__]


@contextmanager
def write_guard(timeout_s: float = 60.0):
    pkg = _pkg()
    Path(pkg.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with open(pkg.LOCK_PATH, "w") as fh:
        while True:
            try:
                file_lock.try_lock_exclusive(fh)
                break
            except BlockingIOError:
                if time.monotonic() - start > timeout_s:
                    raise TimeoutError("warehouse write lock timed out")
                time.sleep(file_lock.POLL_INTERVAL_S)
        fh.seek(0)
        fh.write(str(os.getpid()))
        fh.truncate()
        fh.flush()
        try:
            yield
        finally:
            file_lock.unlock(fh)


def _connect_once(read_only: bool) -> duckdb.DuckDBPyConnection:
    pkg = _pkg()
    db_path = Path(pkg.DB_PATH)
    if read_only:
        return pkg.duckdb.connect(str(db_path), read_only=True)
    if db_path.resolve() == pkg.CANONICAL_DB_PATH:
        raise PermissionError("canonical benchmark warehouse is immutable")
    con = pkg.duckdb.connect(str(db_path))
    con.execute(
        """CREATE TABLE IF NOT EXISTS fetch_log(
        dataset VARCHAR, season VARCHAR, entity VARCHAR,
        source VARCHAR, fetched_at VARCHAR, rows INTEGER)"""
    )
    return con


_LOCK_ERRORS = (duckdb.IOException, duckdb.ConnectionException)
_CONNECT_RETRIES = 6
_CONNECT_BACKOFF_S = 0.2

_pool_state = threading.local()
_pool_lock = threading.Lock()
_pool_registry: list = []


class _PooledConnection:
    def __init__(self, real):
        self._real = real
        self._con = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _pool_drop():
    entry = getattr(_pool_state, "entry", None)
    try:
        _pool_state.entry = None
    except Exception:
        pass
    if entry is not None:
        try:
            with _pool_lock:
                try:
                    _pool_registry.remove(entry[1])
                except ValueError:
                    pass
        except Exception:
            pass
        try:
            entry[1].close()
        except Exception:
            pass


def _pool_evict_all():
    pkg = _pkg()
    try:
        pkg.warehouse_tables_cache_clear()
    except Exception:
        pass
    try:
        with _pool_lock:
            cons = list(_pool_registry)
            del _pool_registry[:]
    except Exception:
        return
    for con in cons:
        try:
            con.close()
        except Exception:
            pass


def _pool_acquire():
    pkg = _pkg()
    entry = getattr(_pool_state, "entry", None)
    if entry is None:
        return None
    if entry[0] != (str(Path(pkg.DB_PATH).resolve()), True):
        _pool_drop()
        return None
    if pkg._warehouse_freshness_key(pkg.DB_PATH) != entry[2]:
        _pool_drop()
        try:
            pkg.warehouse_tables_cache_clear()
        except Exception:
            pass
        return None
    try:
        entry[1].execute("SELECT 1").fetchall()
    except Exception:
        _pool_drop()
        return None
    return _PooledConnection(entry[1])


def _pool_store(con):
    pkg = _pkg()
    freshness = pkg._warehouse_freshness_key(pkg.DB_PATH)
    if freshness is None:
        return con
    _pool_state.entry = ((str(Path(pkg.DB_PATH).resolve()), True), con, freshness)
    try:
        with _pool_lock:
            if con not in _pool_registry:
                _pool_registry.append(con)
    except Exception:
        pass
    return _PooledConnection(con)


def warehouse_pool_clear() -> None:
    _pool_drop()


def read_connect() -> duckdb.DuckDBPyConnection:
    return _pkg().connect(read_only=True)


def connect_to(path: Path | str, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    pkg = _pkg()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        return pkg.duckdb.connect(str(target), read_only=read_only)
    except _LOCK_ERRORS as exc:
        if not read_only:
            raise pkg.WriteConflictError(target) from exc
        raise


def snapshot_warehouse(dest: Path | str | None = None) -> Path:
    pkg = _pkg()
    if dest is None:
        dest = Path(tempfile.mkdtemp(prefix="dime-run-", dir="/tmp")) / "warehouse.duckdb"
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with pkg.write_guard():
        con = pkg.connect(read_only=False)
        try:
            con.execute("CHECKPOINT")
        finally:
            con.close()
        shutil.copyfile(pkg.DB_PATH, target)
        wal_source = Path(str(pkg.DB_PATH) + ".wal")
        if wal_source.exists():
            shutil.copyfile(wal_source, Path(str(target) + ".wal"))
    return target


def connect(read_only: bool | None = None) -> duckdb.DuckDBPyConnection:
    pkg = _pkg()
    db_path = Path(pkg.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if read_only is None:
        read_only = db_path.resolve() == pkg.CANONICAL_DB_PATH
    if not read_only:
        _pool_evict_all()
        try:
            return pkg._connect_once(False)
        except _LOCK_ERRORS as exc:
            raise pkg.WriteConflictError(db_path) from exc
    if not db_path.exists():
        raise pkg._warehouse_absent_error(db_path)
    pooled = _pool_acquire()
    if pooled is not None:
        return pooled
    last: Exception | None = None
    for attempt in range(_CONNECT_RETRIES):
        try:
            return _pool_store(pkg._connect_once(True))
        except _LOCK_ERRORS as exc:
            last = exc
            try:
                if isinstance(exc, duckdb.ConnectionException) and "different configuration" in str(exc):
                    _pool_evict_all()
            except Exception:
                pass
            time.sleep(_CONNECT_BACKOFF_S * (2 ** attempt))
        except duckdb.BinderException as exc:
            if "already attached" not in str(exc):
                raise
            last = exc
            time.sleep(_CONNECT_BACKOFF_S * (2 ** attempt))
    assert last is not None
    raise last


def state_connect() -> duckdb.DuckDBPyConnection:
    pkg = _pkg()
    state_path = Path(pkg.STATE_PATH)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.resolve() == pkg.CANONICAL_DB_PATH:
        raise PermissionError("operational state cannot target canonical warehouse")
    return pkg.duckdb.connect(str(state_path))


@contextmanager
def state_write_guard(timeout_s: float = 60.0):
    pkg = _pkg()
    Path(pkg.STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with open(pkg.STATE_LOCK_PATH, "w") as fh:
        while True:
            try:
                file_lock.try_lock_exclusive(fh)
                break
            except BlockingIOError:
                if time.monotonic() - start > timeout_s:
                    raise TimeoutError("state write lock timed out")
                time.sleep(file_lock.POLL_INTERVAL_S)
        try:
            yield
        finally:
            file_lock.unlock(fh)
