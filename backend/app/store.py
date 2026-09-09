"""Warehouse. DuckDB file with bronze raw plus silver analyst tables.

Provenance columns ride every silver row: _source, _season, _fetched_at.
Watermarks in fetch_log drive incremental refresh.
"""

from pathlib import Path
from contextlib import contextmanager
import duckdb
import fcntl
import polars as pl
import time

from .sources.base import FetchResult

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
LOCK_PATH = DB_PATH.parent / ".write.lock"

PROVENANCE_COLS = ["_source", "_season", "_fetched_at"]


@contextmanager
def write_guard(timeout_s: float = 60.0):
    """Serialize DuckDB writers across threads and processes."""
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


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        return duckdb.connect(str(DB_PATH), read_only=True)
    try:
        con = duckdb.connect(str(DB_PATH))
    except duckdb.IOException:
        return duckdb.connect(str(DB_PATH), read_only=True)
    con.execute(
        """CREATE TABLE IF NOT EXISTS fetch_log(
        dataset VARCHAR, season VARCHAR, entity VARCHAR,
        source VARCHAR, fetched_at VARCHAR, rows INTEGER)"""
    )
    return con


def save_frame(
    table: str,
    result: FetchResult,
    entity: str = "",
    replace_season: bool = True,
) -> int:
    frame = result.frame.with_columns(
        [
            pl.lit(result.meta.source).alias("_source"),
            pl.lit(result.meta.season).alias("_season"),
            pl.lit(result.meta.fetched_at).alias("_fetched_at"),
            pl.lit(entity).alias("_entity"),
        ]
    )
    con = connect()
    try:
        with write_guard():
            con.register("_incoming", frame.to_arrow())
            con.execute(
                f"""CREATE TABLE IF NOT EXISTS {table} AS
                SELECT * FROM _incoming LIMIT 0"""
            )
            have = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            incoming = frame.columns
            if set(have) != set(incoming):
                con.execute(f"DROP TABLE {table}")
                con.execute(f"CREATE TABLE {table} AS SELECT * FROM _incoming")
            cols = ", ".join(f'"{c}"' for c in have) if set(have) == set(incoming) else "*"
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
            con.execute(f"INSERT INTO {table} SELECT {cols} FROM _incoming")
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
            return frame.height
    finally:
        con.close()


def read_frame(table: str, where: str = "", params: list[object] | None = None) -> pl.DataFrame:
    con = connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return pl.DataFrame()
        query = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        rel = con.execute(query, params or [])
        return pl.from_arrow(rel.fetch_arrow_table())
    finally:
        con.close()


def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, object]]:
    """Warehouse read with retries. Concurrent writers briefly lock the file."""
    import time as _time

    last: Exception | None = None
    for _ in range(tries):
        try:
            con = connect()
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
    con = connect()
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


def save_chat(thread: str, role: str, text: str) -> None:
    con = connect()
    try:
        with write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS chat_history(
                thread VARCHAR, role VARCHAR, text VARCHAR, created_at VARCHAR)"""
            )
            from datetime import datetime, timezone

            con.execute(
                "INSERT INTO chat_history VALUES (?,?,?,?)",
                [thread, role, text[:4000],
                 datetime.now(timezone.utc).isoformat()],
            )
    finally:
        con.close()


def chat_history(thread: str, limit: int = 6) -> list[dict[str, str]]:
    con = connect()
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


def list_threads() -> list[dict[str, str]]:
    con = connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return []
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
    tables: list[dict], suggestions: list[str],
) -> None:
    import json as _json

    con = connect()
    try:
        with write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS runs(
                thread VARCHAR, question VARCHAR, answer VARCHAR,
                tables VARCHAR, suggestions VARCHAR, created_at VARCHAR)"""
            )
            from datetime import datetime, timezone

            con.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?)",
                [thread, question[:2000], answer[:8000],
                 _json.dumps(tables, default=str)[:60000],
                 _json.dumps(suggestions)[:2000],
                 datetime.now(timezone.utc).isoformat()],
            )
    finally:
        con.close()


def list_runs(thread: str) -> list[dict]:
    import json as _json

    con = connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "runs" not in tables:
            return []
        rows = con.execute(
            """SELECT question, answer, tables, suggestions, created_at
            FROM runs WHERE thread = ? ORDER BY created_at DESC""",
            [thread],
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
            out.append({"question": r[0], "answer": r[1], "tables": tbl,
                        "suggestions": sug, "created_at": r[4]})
        return out
    finally:
        con.close()
