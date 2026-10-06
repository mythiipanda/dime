from typing import Any

from langchain_core.tools import tool

from .league import (
    RERUN_ROW_CAP,
    RERUN_TIMEOUT_S,
    _SQL_TABLES,
    _TABLE_REF_RE,
    rerun_sql,
)

TOOL = "sql_exec"
TABLES = tuple(sorted(_SQL_TABLES))
SOURCE = "warehouse"
MAX_SQL_CHARS = 8000

def tables_in(sql: str) -> list[str]:
    return sorted({a or b for a, b in _TABLE_REF_RE.findall(sql or "")})

def _failure(query: str, message: str) -> dict[str, Any]:
    return {"tool": TOOL, "ok": False, "rows": {},
            "meta": {"sql": query[:500]}, "error": message}

@tool("sql_exec", description='Run one agent-written read-only analytical query over the warehouse.\n\nThe query must be a single SELECT or WITH statement over the declared\nsilver tables. Writes, stacked statements, and tables outside the\ndeclared set are refused before execution. Results are capped at\nRERUN_ROW_CAP rows with a RERUN_TIMEOUT_S statement timeout, and a\nquery that returns nothing fails instead of publishing an empty\nanswer. Alias the primary numeric answer `n` so citations carry a\ndeclared count unit. Returned rows are computed from the supplied\nSQL, never curated table values.')
async def sql_exec(sql: str, season: str | None = None) -> dict[str, Any]:
    query = (sql or "").strip()
    if not query:
        return _failure(query, "sql_exec: sql is required; pass one "
                               "SELECT or WITH statement")
    if len(query) > MAX_SQL_CHARS:
        return _failure(
            query, f"sql_exec: sql is {len(query)} chars, over the "
                   f"{MAX_SQL_CHARS} cap")
    out = await rerun_sql(query)
    if not out.get("ok"):
        return _failure(
            query, f"{out.get('error', 'query failed')}; sql: {query[:500]}")
    rows = out.get("rows") or []
    if not rows:
        return _failure(
            query, "sql_exec: query returned 0 rows, so no answer can be "
                   f"published; sql: {query[:500]}")
    tables = tables_in(query)
    meta: dict[str, Any] = {
        "source": SOURCE,
        "dataset": "warehouse",
        "season": season,
        "sql": query[:500],
        "tables": tables,
        "row_cap": RERUN_ROW_CAP,
        "timeout_s": RERUN_TIMEOUT_S,
        "capped": out.get("capped", False),
        "ms": out.get("ms", 0),
        "result_type": "agent_sql_result",
        "model_projection": False,
        "method": ("agent-written read-only SQL executed under the shared "
                   "kernel rails: SELECT/WITH only, one statement, writes "
                   "blocked, tables limited to the declared set, "
                   f"{RERUN_ROW_CAP} row cap, {RERUN_TIMEOUT_S}s statement "
                   "timeout; rows are computed, not curated"),
        "coverage": (f"Agent-written SQL over "
                     f"{', '.join(tables) if tables else 'no tables'}; "
                     f"computed rows, never a curated table. "
                     f"SQL: {query[:300]}"),
    }
    return {"tool": TOOL, "ok": True, "rows": rows,
            "columns": out.get("columns", []), "sql": query, "meta": meta}
