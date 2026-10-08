
from pathlib import Path
from contextlib import contextmanager
import duckdb
import fcntl
import os
import polars as pl
import shutil
import tempfile
import threading
import time
import hashlib

from .sources.base import FetchResult

DB_PATH = Path(os.environ.get("DIME_WAREHOUSE") or
               (Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"))
LOCK_PATH = DB_PATH.parent / ".write.lock"
CANONICAL_DB_PATH = (Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb").resolve()
STATE_PATH = Path(os.environ.get("DIME_STATE_DB") or
                  (Path(__file__).resolve().parent.parent / "data" / "state.duckdb"))
STATE_LOCK_PATH = STATE_PATH.parent / ".state-write.lock"

PROVENANCE_COLS = ["_source", "_season", "_fetched_at"]

def _warehouse_identity_uncached(path: Path, sample: str | None = None) -> dict[str, str]:
    if sample is None:
        try:
            size: int | None = path.stat().st_size
        except OSError:
            size = None
        sample = (_warehouse_sample_hexdigest(path, size)
                  if size is not None else None)
        if sample is None:
            sample = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"warehouse_id": "frozen-eval" if path == CANONICAL_DB_PATH else "configured-runtime",
            "warehouse_sha256": sample}

_warehouse_identity_cache: dict[Path, tuple[tuple[int, int, str], dict[str, str]]] = {}

def warehouse_identity_cache_clear() -> None:
    _warehouse_identity_cache.clear()

_SAMPLE_READ_BYTES = 8192

def _warehouse_sample_hexdigest(path: Path, size: int) -> str | None:
    try:
        h = hashlib.new("sha256")
        h.update(size.to_bytes(8, "little", signed=False))
        with open(path, "rb") as fh:
            for off in (0, size // 2, size - _SAMPLE_READ_BYTES):
                fh.seek(max(off, 0))
                h.update(fh.read(_SAMPLE_READ_BYTES))
        return h.hexdigest()
    except OSError:
        return None

def warehouse_identity() -> dict[str, str]:
    path = DB_PATH.resolve()
    try:
        st = path.stat()
    except OSError:
        return _warehouse_identity_uncached(path)
    sample = _warehouse_sample_hexdigest(path, st.st_size)
    if sample is None:
        return _warehouse_identity_uncached(path)
    key = (st.st_mtime_ns, st.st_size, sample)
    entry = _warehouse_identity_cache.get(path)
    if entry is not None and entry[0] == key:
        return entry[1]
    identity = _warehouse_identity_uncached(path, sample)
    _warehouse_identity_cache[path] = (key, identity)
    return identity

_tables_cache: dict[Path, tuple[tuple[int, int, str], frozenset[str]]] = {}
_tables_lock = threading.RLock()

def _tables_freshness_key(path: Path) -> tuple[int, int, str] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    sample = _warehouse_sample_hexdigest(path, st.st_size)
    if sample is None:
        return None
    return (st.st_mtime_ns, st.st_size, sample)

def warehouse_tables_cache_clear() -> None:
    with _tables_lock:
        _tables_cache.clear()

class WriteConflictError(TimeoutError):
    def __init__(self, warehouse: Path | str) -> None:
        self.warehouse = str(warehouse)
        super().__init__(
            f"warehouse write for {Path(self.warehouse).name} refused: "
            f"another writer holds it; serialize writes through write_guard")

def _connection_db_path(con) -> Path | None:
    try:
        rows = con.execute("PRAGMA database_list").fetchall()
    except Exception:
        return None
    try:
        for row in rows:
            file = row[2] if len(row) > 2 else None
            if file:
                return Path(str(file))
        return None
    except Exception:
        return None

def _tables_uncached(path: Path) -> tuple[frozenset[str], Path | None]:
    if path == DB_PATH.resolve():
        con = read_connect()
    else:
        con = duckdb.connect(str(path), read_only=True)
    try:
        names = frozenset(r[0] for r in con.execute("SHOW TABLES").fetchall())
        return names, _connection_db_path(con)
    finally:
        try:
            con.close()
        except Exception:
            pass

def tables(path: Path | str | None = None) -> set[str]:
    key = DB_PATH if path is None else Path(path)
    freshness = _tables_freshness_key(key)
    with _tables_lock:
        entry = _tables_cache.get(key)
        if freshness is not None and entry is not None and entry[0] == freshness:
            return set(entry[1])
    names, source = _tables_uncached(key)
    with _tables_lock:
        if freshness is not None:
            try:
                matches = source is not None and source.resolve() == key.resolve()
            except OSError:
                matches = False
            if matches:
                _tables_cache[key] = (freshness, names)
        return set(names)

_PLAYED_GAME_TABLE = "silver_hist_gamelogs"

_SEASON_TABLES = (
    _PLAYED_GAME_TABLE,
    "silver_boxscores",
    "silver_team_games",
    "silver_player_gamelogs",
)

_PRESEASON_GAME_ID_PREFIX = "001"

def seasons_with_data(table: str = _PLAYED_GAME_TABLE) -> list[str]:
    con = read_connect()
    try:
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {table} "
            f"WHERE GAME_ID NOT LIKE '{_PRESEASON_GAME_ID_PREFIX}%' "
            "ORDER BY _season"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows if r and r[0]]


def completed_seasons_across_tables() -> list[str]:
    found: set[str] = set()
    for table in _SEASON_TABLES:
        try:
            found.update(seasons_with_data(table))
        except Exception:
            continue
    return sorted(found)


@contextmanager
def write_guard(timeout_s: float = 60.0):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with open(LOCK_PATH, "w") as fh:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout_s:
                    raise TimeoutError("warehouse write lock timed out")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

def _connect_once(read_only: bool) -> duckdb.DuckDBPyConnection:
    if read_only:
        return duckdb.connect(str(DB_PATH), read_only=True)
    if DB_PATH.resolve() == CANONICAL_DB_PATH:
        raise PermissionError("canonical benchmark warehouse is immutable")
    con = duckdb.connect(str(DB_PATH))
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
    try:
        warehouse_tables_cache_clear()
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
    entry = getattr(_pool_state, "entry", None)
    if entry is None:
        return None
    if entry[0] != (str(DB_PATH.resolve()), True):
        _pool_drop()
        return None
    try:
        st = os.stat(DB_PATH)
    except OSError:
        _pool_drop()
        return None
    sample = _warehouse_sample_hexdigest(DB_PATH, st.st_size)
    if sample is None or (st.st_mtime_ns, st.st_size, sample) != (
            entry[2], entry[3], entry[4]):
        _pool_drop()
        try:
            warehouse_tables_cache_clear()
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
    try:
        st = os.stat(DB_PATH)
    except OSError:
        return con
    sample = _warehouse_sample_hexdigest(DB_PATH, st.st_size)
    if sample is None:
        return con
    _pool_state.entry = ((str(DB_PATH.resolve()), True), con,
                         st.st_mtime_ns, st.st_size, sample)
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
    return connect(read_only=True)

def connect_to(path: Path | str,
               read_only: bool = True) -> duckdb.DuckDBPyConnection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        return duckdb.connect(str(target), read_only=read_only)
    except _LOCK_ERRORS as exc:
        if not read_only:
            raise WriteConflictError(target) from exc
        raise

def snapshot_warehouse(dest: Path | str | None = None) -> Path:
    if dest is None:
        dest = (Path(tempfile.mkdtemp(prefix="dime-run-", dir="/tmp"))
                / "warehouse.duckdb")
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with write_guard():
        con = connect(read_only=False)
        try:
            con.execute("CHECKPOINT")
        finally:
            con.close()
        shutil.copyfile(DB_PATH, target)
        wal_source = Path(str(DB_PATH) + ".wal")
        if wal_source.exists():
            shutil.copyfile(wal_source, Path(str(target) + ".wal"))
    return target

def connect(read_only: bool | None = None) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if read_only is None:
        read_only = DB_PATH.resolve() == CANONICAL_DB_PATH
    if not read_only:
        _pool_evict_all()
        try:
            return _connect_once(False)
        except _LOCK_ERRORS as exc:
            raise WriteConflictError(DB_PATH) from exc
    if not DB_PATH.exists():
        raise FileNotFoundError(f"warehouse absent: {DB_PATH}")
    pooled = _pool_acquire()
    if pooled is not None:
        return pooled
    last: Exception | None = None
    for attempt in range(_CONNECT_RETRIES):
        try:
            return _pool_store(_connect_once(True))
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
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STATE_PATH.resolve() == CANONICAL_DB_PATH:
        raise PermissionError("operational state cannot target canonical warehouse")
    return duckdb.connect(str(STATE_PATH))

@contextmanager
def state_write_guard(timeout_s: float = 60.0):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    with open(STATE_LOCK_PATH, "w") as fh:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB); break
            except BlockingIOError:
                if time.time() - start > timeout_s:
                    raise TimeoutError("state write lock timed out")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

def save_frame(
    table: str,
    result: FetchResult,
    entity: str = "",
    replace_season: bool = True,
    _fault: str | None = None,
) -> int:
    frame = result.frame.with_columns(
        [
            pl.lit(result.meta.source).alias("_source"),
            pl.lit(result.meta.season).alias("_season"),
            pl.lit(result.meta.fetched_at).alias("_fetched_at"),
            pl.lit(entity).alias("_entity"),
        ]
    )
    con = connect(read_only=False)
    try:
        with write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                con.register("_incoming", frame.clear().to_arrow())
                try:
                    con.execute(
                        f"""CREATE TABLE IF NOT EXISTS {table} AS
                        SELECT * FROM _incoming LIMIT 0"""
                    )
                    have = {r[1] for r in con.execute(
                        f"PRAGMA table_info({table})").fetchall()}
                    for name, dtype in frame.schema.items():
                        if name not in have:
                            con.execute(
                                f'ALTER TABLE {table} ADD COLUMN "{name}" '
                                f"{_UNIT_DTYPE_SQL.get(dtype, 'VARCHAR')}"
                            )
                    cols = [r[1] for r in con.execute(
                        f"PRAGMA table_info({table})").fetchall()]
                finally:
                    con.unregister("_incoming")
                if replace_season:
                    if entity:
                        con.execute(
                            "DELETE FROM {table} WHERE _season = ? AND _entity = ?"
                            .format(table=table),
                            [result.meta.season, entity],
                        )
                    else:
                        con.execute(
                            f"DELETE FROM {table} WHERE _season = ?",
                            [result.meta.season],
                        )
                if _fault == "after_delete":
                    raise RuntimeError("simulated crash after DELETE")
                if _fault == "hang":
                    time.sleep(120)
                select = ", ".join(
                    f'"{c}"' if c in frame.columns else f'NULL AS "{c}"'
                    for c in cols)
                con.register("_incoming", frame.to_arrow())
                try:
                    con.execute(
                        f"INSERT INTO {table} SELECT {select} FROM _incoming")
                finally:
                    con.unregister("_incoming")
                if _fault == "after_insert":
                    raise RuntimeError("simulated crash after INSERT")
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                    [
                        table,
                        result.meta.season,
                        entity,
                        result.meta.source,
                        result.meta.fetched_at,
                        frame.height,
                    ],
                )
                con.execute("COMMIT")
                return frame.height
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
    finally:
        con.close()

_UNIT_DTYPE_SQL = {
    pl.Int8: "TINYINT", pl.Int16: "SMALLINT",
    pl.Int32: "INTEGER", pl.Int64: "BIGINT",
    pl.UInt8: "UTINYINT", pl.UInt16: "USMALLINT",
    pl.UInt32: "UINTEGER", pl.UInt64: "UBIGINT",
    pl.Float32: "FLOAT", pl.Float64: "DOUBLE",
    pl.Boolean: "BOOLEAN", pl.String: "VARCHAR",
    pl.Date: "DATE", pl.Datetime: "TIMESTAMP",
}

def write_unit(table: str, frame: pl.DataFrame, season: str, source: str,
               entity: str, delete_where: str, delete_params: list,
               _fault: str | None = None) -> int:
    if frame.height == 0:
        return 0
    from datetime import datetime, timezone
    fetched_at = datetime.now(timezone.utc).isoformat()
    frame = frame.with_columns([
        pl.lit(source).alias("_source"),
        pl.lit(season).alias("_season"),
        pl.lit(fetched_at).alias("_fetched_at"),
        pl.lit(entity).alias("_entity"),
    ])
    con = connect(read_only=False)
    try:
        with write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                con.register("_incoming", frame.clear().to_arrow())
                try:
                    con.execute(
                        f"""CREATE TABLE IF NOT EXISTS {table} AS
                        SELECT * FROM _incoming LIMIT 0"""
                    )
                    have = {r[1] for r in con.execute(
                        f"PRAGMA table_info({table})").fetchall()}
                    for name, dtype in frame.schema.items():
                        if name not in have:
                            con.execute(
                                f'ALTER TABLE {table} ADD COLUMN "{name}" '
                                f"{_UNIT_DTYPE_SQL.get(dtype, 'VARCHAR')}"
                            )
                    cols = [r[1] for r in con.execute(
                        f"PRAGMA table_info({table})").fetchall()]
                finally:
                    con.unregister("_incoming")
                con.execute(
                    f"DELETE FROM {table} WHERE {delete_where}", delete_params)
                if _fault == "after_delete":
                    raise RuntimeError("simulated crash after DELETE")
                if _fault == "hang":
                    time.sleep(120)
                select = ", ".join(
                    f'"{c}"' if c in frame.columns else f'NULL AS "{c}"'
                    for c in cols)
                con.register("_incoming", frame.to_arrow())
                try:
                    con.execute(
                        f"INSERT INTO {table} SELECT {select} FROM _incoming")
                finally:
                    con.unregister("_incoming")
                if _fault == "after_insert":
                    raise RuntimeError("simulated crash after INSERT")
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                    [table, season, entity, source, fetched_at, frame.height],
                )
                con.execute("COMMIT")
                return frame.height
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
    finally:
        con.close()

class TableAbsent(LookupError):

    def __init__(self, table: str, warehouse: Path | str) -> None:
        self.table = str(table)
        self.warehouse = str(warehouse)
        super().__init__(
            f"warehouse table {self.table!r} is absent from "
            f"{Path(self.warehouse).name}; an empty read here would be "
            f"indistinguishable from a table that holds no matching rows")

def read_frame(table: str, where: str = "", params: list[object] | None = None) -> pl.DataFrame:
    if table not in tables():
        raise TableAbsent(table, DB_PATH)
    con = read_connect()
    try:
        query = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        rel = con.execute(query, params or [])
        return pl.from_arrow(rel.fetch_arrow_table())
    finally:
        con.close()

def read_frame_optional(table: str, where: str = "",
                        params: list[object] | None = None) -> pl.DataFrame:
    try:
        return read_frame(table, where, params)
    except TableAbsent:
        return pl.DataFrame()

def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, object]]:
    import time as _time

    last: Exception | None = None
    for _ in range(tries):
        try:
            con = read_connect()
            try:
                return (
                    con.execute(sql, params)
                    .fetchdf()
                    .to_dict(orient="records")
                )
            finally:
                con.close()
        except Exception as exc:
            last = exc
            _time.sleep(0.3)
    raise last or RuntimeError("warehouse read failed")

def last_fetch(table: str, season: str, entity: str = "") -> str:
    con = read_connect()
    try:
        row = con.execute(
            """SELECT fetched_at FROM fetch_log
            WHERE dataset = ? AND season = ? AND entity = ?
            ORDER BY fetched_at DESC LIMIT 1""",
            [table, season, entity],
        ).fetchone()
        return row[0] if row else ""
    finally:
        con.close()

def save_chat(thread: str, role: str, text: str, owner: str = "") -> None:
    con = state_connect()
    try:
        with state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS chat_history(
                thread VARCHAR, role VARCHAR, text VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            cols = [r[1] for r in con.execute(
                "PRAGMA table_info(chat_history)").fetchall()]
            if "owner" not in cols:
                con.execute("ALTER TABLE chat_history ADD COLUMN owner VARCHAR DEFAULT ''")
            from datetime import datetime, timezone

            con.execute(
                "INSERT INTO chat_history VALUES (?,?,?,?,?)",
                [thread, role, text[:4000],
                 datetime.now(timezone.utc).isoformat(), owner[:80]],
            )
    finally:
        con.close()

def chat_history(thread: str, limit: int = 6) -> list[dict[str, str]]:
    con = state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return []
        rows = con.execute(
            """SELECT role, text FROM chat_history
            WHERE thread = ? ORDER BY created_at DESC LIMIT ?""",
            [thread, limit],
        ).fetchall()
        return [{"role": r[0], "text": r[1]} for r in reversed(rows)]
    finally:
        con.close()

def save_facts(thread: str, facts: list[str], owner: str = "") -> None:
    if not thread or not facts:
        return
    con = state_connect()
    try:
        with state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS thread_facts(
                thread VARCHAR, fact VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            from datetime import datetime, timezone

            for f in facts:
                f = str(f)[:500]
                dupe = con.execute(
                    "SELECT 1 FROM thread_facts WHERE thread=? AND fact=? "
                    "LIMIT 1", [thread, f]).fetchone()
                if not dupe:
                    con.execute(
                        "INSERT INTO thread_facts VALUES (?,?,?,?)",
                        [thread, f,
                         datetime.now(timezone.utc).isoformat(),
                         owner[:80]],
                    )
    finally:
        con.close()

def thread_facts(thread: str, limit: int = 20) -> list[str]:
    if not thread:
        return []
    con = state_connect()
    try:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall()}
        if "thread_facts" not in tables:
            return []
        rows = con.execute(
            """SELECT fact FROM thread_facts WHERE thread = ?
            ORDER BY created_at DESC LIMIT ?""",
            [thread, limit]).fetchall()
        return [r[0] for r in reversed(rows)]
    except Exception:
        return []
    finally:
        con.close()

def list_threads(owner: str = "") -> list[dict[str, str]]:
    con = state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return []
        cols = {r[1] for r in con.execute(
            "PRAGMA table_info(chat_history)").fetchall()}
        if "owner" in cols:
            rows = con.execute(
                """SELECT thread, MAX(created_at), COUNT(*)
                FROM chat_history WHERE owner = ?
                GROUP BY thread ORDER BY MAX(created_at) DESC LIMIT 100""",
                [owner],
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT thread, MAX(created_at), COUNT(*)
                FROM chat_history GROUP BY thread ORDER BY MAX(created_at) DESC LIMIT 100"""
            ).fetchall()
        out = []
        for r in rows:
            first = con.execute(
                """SELECT text FROM chat_history
                WHERE thread = ? AND role = 'human'
                ORDER BY created_at LIMIT 1""",
                [r[0]],
            ).fetchone()
            title = ((first[0] if first else "") or "")[:90]
            if not title.strip():
                continue
            out.append({"id": r[0], "title": title,
                        "updated": r[1], "turns": r[2]})
        return out
    finally:
        con.close()

def save_run(
    thread: str, question: str, answer: str,
    tables: list[dict], suggestions: list[str], owner: str = "",
    run_id: str = "",
) -> None:
    import json as _json

    con = state_connect()
    try:
        with state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS runs(
                thread VARCHAR, question VARCHAR, answer VARCHAR,
                tables VARCHAR, suggestions VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            cols = [r[1] for r in con.execute(
                "PRAGMA table_info(runs)").fetchall()]
            if "owner" not in cols:
                con.execute("ALTER TABLE runs ADD COLUMN owner VARCHAR DEFAULT ''")
            if "run_id" not in cols:
                con.execute("ALTER TABLE runs ADD COLUMN run_id VARCHAR DEFAULT ''")
            from datetime import datetime, timezone

            con.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                [thread, question[:2000], answer[:8000],
                 _json.dumps(tables, default=str)[:60000],
                 _json.dumps(suggestions)[:2000],
                 datetime.now(timezone.utc).isoformat(), owner[:80],
                 run_id[:80]],
            )
    finally:
        con.close()

def list_runs(thread: str, owner: str = "") -> list[dict]:
    import json as _json

    con = state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "runs" not in tables:
            return []
        cols = {r[1] for r in con.execute(
            "PRAGMA table_info(runs)").fetchall()}
        if "owner" not in cols:
            return []
        has_run_id = "run_id" in cols
        rows = con.execute(
            f"""SELECT question, answer, tables, suggestions, created_at
            {", run_id" if has_run_id else ""}
            FROM runs WHERE thread = ? AND owner = ?
            ORDER BY created_at DESC""",
            [thread, owner[:80]],
        ).fetchall()
        out = []
        for r in rows:
            try:
                tbl = _json.loads(r[2])
            except Exception:
                tbl = []
            try:
                sug = _json.loads(r[3])
            except Exception:
                sug = []
            row = {"question": r[0], "answer": r[1], "tables": tbl,
                   "suggestions": sug, "created_at": r[4]}
            if has_run_id and r[5]:
                row["id"] = r[5]
            out.append(row)
        return out
    finally:
        con.close()

def compact_thread(thread: str, keep_recent: int = 4,
                   threshold: int = 12) -> dict:
    con = state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return {"compacted": False, "kept": 0, "dropped": 0}
        rows = con.execute(
            """SELECT rowid, role, text FROM chat_history
            WHERE thread = ? ORDER BY created_at, rowid""",
            [thread],
        ).fetchall()
    finally:
        con.close()
    if len(rows) <= threshold:
        return {"compacted": False, "kept": len(rows), "dropped": 0}
    keep = rows[-keep_recent:] if keep_recent > 0 else []
    older = rows[:len(rows) - len(keep)]
    transcript = "\n".join(
        f"{r[1]}: {(r[2] or '')[:1000]}" for r in older
    )
    try:
        from .providers import get_llm, resolve_model_id
        from langchain_core.messages import HumanMessage, SystemMessage

        primary, model = resolve_model_id(None)
        client = get_llm(primary, model)
        if client is None:
            return {"compacted": False, "kept": len(rows), "dropped": 0}
        resp = client.invoke([
            SystemMessage(content="You compress chat threads into short memos."),
            HumanMessage(content=(
                "Summarize these older chat turns for an NBA analyst "
                "assistant. Produce three sections: entities discussed, "
                "Q&A pairs (question plus one-line answer each), "
                "open/unresolved items. Keep every entity name and number. "
                "Be concise.\n\n" + transcript
            )),
        ])
        memo = str(getattr(resp, "content", "") or "").strip()
        if not memo:
            return {"compacted": False, "kept": len(rows), "dropped": 0}
    except Exception:
        return {"compacted": False, "kept": len(rows), "dropped": 0}
    con = state_connect()
    try:
        with state_write_guard():
            from datetime import datetime, timezone

            ids = [r[0] for r in older]
            con.execute(
                "DELETE FROM chat_history WHERE rowid IN (%s)"
                % ",".join(["?"] * len(ids)), ids,
            )
            con.execute(
                "INSERT INTO chat_history (thread, role, text, created_at)"
                " VALUES (?,?,?,?)",
                [thread, "summary", ("THREAD SUMMARY: " + memo)[:4000],
                 datetime.now(timezone.utc).isoformat()],
            )
    finally:
        con.close()
    return {"compacted": True, "kept": len(keep), "dropped": len(older)}
