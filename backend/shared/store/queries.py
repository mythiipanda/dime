import sys
import threading
import time as _time
from datetime import datetime, timezone

import polars as pl

from ..sources.base import FetchResult


def _pkg():
    return sys.modules[__package__]


_UNIT_DTYPE_SQL = {
    pl.Int8: "TINYINT",
    pl.Int16: "SMALLINT",
    pl.Int32: "INTEGER",
    pl.Int64: "BIGINT",
    pl.UInt8: "UTINYINT",
    pl.UInt16: "USMALLINT",
    pl.UInt32: "UINTEGER",
    pl.UInt64: "UBIGINT",
    pl.Float32: "FLOAT",
    pl.Float64: "DOUBLE",
    pl.Boolean: "BOOLEAN",
    pl.String: "VARCHAR",
    pl.Date: "DATE",
    pl.Datetime: "TIMESTAMP",
}


def _ensure_table_columns(con, table: str, frame: pl.DataFrame) -> list[str]:
    con.register("_incoming", frame.clear().to_arrow())
    try:
        con.execute(
            f"""CREATE TABLE IF NOT EXISTS {table} AS
            SELECT * FROM _incoming LIMIT 0"""
        )
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, dtype in frame.schema.items():
            if name not in have:
                con.execute(
                    f'ALTER TABLE {table} ADD COLUMN "{name}" '
                    f"{_UNIT_DTYPE_SQL.get(dtype, 'VARCHAR')}"
                )
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    finally:
        con.unregister("_incoming")


def _insert_frame(con, table: str, frame: pl.DataFrame, cols: list[str]) -> None:
    select = ", ".join(
        f'"{c}"' if c in frame.columns else f'NULL AS "{c}"' for c in cols
    )
    con.register("_incoming", frame.to_arrow())
    try:
        con.execute(f"INSERT INTO {table} SELECT {select} FROM _incoming")
    finally:
        con.unregister("_incoming")


_WRITE_MUTEX = threading.RLock()


def _commit_frame_write(
    table: str,
    frame: pl.DataFrame,
    season: str,
    source: str,
    entity: str,
    fetched_at: str,
    delete_where: str | None,
    delete_params: list,
    _fault: str | None,
) -> int:
    with _WRITE_MUTEX:
        return _commit_frame_write_inner(
            table, frame, season, source, entity, fetched_at,
            delete_where, delete_params, _fault,
        )


def _commit_frame_write_inner(
    table: str,
    frame: pl.DataFrame,
    season: str,
    source: str,
    entity: str,
    fetched_at: str,
    delete_where: str | None,
    delete_params: list,
    _fault: str | None,
) -> int:
    pkg = _pkg()
    con = pkg.connect(read_only=False)
    try:
        with pkg.write_guard():
            con.execute("BEGIN TRANSACTION")
            try:
                cols = _ensure_table_columns(con, table, frame)
                if delete_where is not None:
                    con.execute(f"DELETE FROM {table} WHERE {delete_where}", delete_params)
                if _fault == "after_delete":
                    raise RuntimeError("simulated crash after DELETE")
                if _fault == "hang":
                    _time.sleep(120)
                _insert_frame(con, table, frame, cols)
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
    delete_where: str | None = None
    delete_params: list = []
    if replace_season:
        if entity:
            delete_where = "_season = ? AND _entity = ?"
            delete_params = [result.meta.season, entity]
        else:
            delete_where = "_season = ?"
            delete_params = [result.meta.season]
    return _commit_frame_write(
        table,
        frame,
        result.meta.season,
        result.meta.source,
        entity,
        result.meta.fetched_at,
        delete_where,
        delete_params,
        _fault,
    )


def write_unit(
    table: str,
    frame: pl.DataFrame,
    season: str,
    source: str,
    entity: str,
    delete_where: str,
    delete_params: list,
    _fault: str | None = None,
) -> int:
    if frame.height == 0:
        return 0
    fetched_at = datetime.now(timezone.utc).isoformat()
    annotated = frame.with_columns(
        [
            pl.lit(source).alias("_source"),
            pl.lit(season).alias("_season"),
            pl.lit(fetched_at).alias("_fetched_at"),
            pl.lit(entity).alias("_entity"),
        ]
    )
    return _commit_frame_write(
        table,
        annotated,
        season,
        source,
        entity,
        fetched_at,
        delete_where,
        delete_params,
        _fault,
    )


def read_frame(
    table: str, where: str = "", params: list[object] | None = None
) -> pl.DataFrame:
    pkg = _pkg()
    if table not in pkg.tables():
        raise pkg.TableAbsent(table, pkg.DB_PATH)
    con = pkg.read_connect()
    try:
        query = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        rel = con.execute(query, params or [])
        try:
            return pl.from_arrow(rel.fetch_arrow_table())
        except (ModuleNotFoundError, Exception):
            cols = [desc[0] for desc in rel.description]
            rows = rel.fetchall()
            if not rows:
                return pl.DataFrame(schema=cols)
            return pl.DataFrame(rows, schema=cols, orient="row")
    finally:
        con.close()


def read_frame_optional(
    table: str, where: str = "", params: list[object] | None = None
) -> pl.DataFrame:
    pkg = _pkg()
    try:
        return pkg.read_frame(table, where, params)
    except pkg.TableAbsent:
        return pl.DataFrame()


def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, object]]:
    pkg = _pkg()
    last: Exception | None = None
    for _ in range(tries):
        try:
            con = pkg.read_connect()
            try:
                return con.execute(sql, params).fetchdf().to_dict(orient="records")
            finally:
                con.close()
        except Exception as exc:
            last = exc
            _time.sleep(0.3)
    raise last or RuntimeError("warehouse read failed")


def last_fetch(table: str, season: str, entity: str = "") -> str:
    con = _pkg().read_connect()
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
