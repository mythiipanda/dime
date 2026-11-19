from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import duckdb

from shared import store
from shared.query import _check, _run_with_timeout


def connection(path: Path | None = None):
    con = duckdb.connect(str(path or store.DB_PATH), read_only=True)
    try:
        con.execute("SET enable_external_access=false")
        con.execute("SET threads=2")
        con.execute("SET memory_limit='512MB'")
    except BaseException:
        con.close()
        raise
    return con


def validate(con, sql: str) -> str:
    from shared.tools.league import _SQL_TABLES

    present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    allowed = present.intersection(_SQL_TABLES)
    if not allowed:
        raise ValueError("Warehouse has no allowlisted queryable tables")
    if not sql.strip().strip(";").strip():
        raise ValueError("SQL must contain a SELECT or WITH query")
    return _check(sql, allowed)


def execute(sql: str, params: dict[str, Any], page: int, page_size: int) -> dict:
    start = time.monotonic()
    with connection() as con:
        statement = validate(con, sql)
        columns, rows, over_cap = _run_with_timeout(
            con, statement, 30, 5000, params=params, typed=True)
    start_row = page * page_size
    kept = rows[:5000]
    def value(item):
        if isinstance(item, float) and not math.isfinite(item):
            return None
        if isinstance(item, dict):
            return {key: value(nested) for key, nested in item.items()}
        if isinstance(item, (list, tuple)):
            return [value(nested) for nested in item]
        return item
    return {"columns": columns, "rows": [dict(zip([c["name"] for c in columns], map(value, row))) for row in kept[start_row:start_row + page_size]],
            "page": page, "page_size": page_size,
            "has_more": start_row + page_size < len(kept),
            "ms": int((time.monotonic() - start) * 1000), "truncated": over_cap}
