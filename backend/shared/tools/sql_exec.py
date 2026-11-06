from typing import Any

from langchain_core.tools import tool

from .count_evidence import count_evidence_meta
from .league import (
    RERUN_ROW_CAP,
    RERUN_TIMEOUT_S,
    _SQL_TABLES,
    _TABLE_REF_RE,
    _get_warehouse_schema,
    rerun_sql,
)
from .season_semantics import annotate_result, annotate_schema

TOOL = "sql_exec"
TABLES = tuple(sorted(_SQL_TABLES))
SOURCE = "warehouse"
MAX_SQL_CHARS = 8000

def tables_in(sql: str) -> list[str]:
    return sorted({a or b for a, b in _TABLE_REF_RE.findall(sql or "")})

def _failure(query: str, message: str) -> dict[str, Any]:
    return {"tool": TOOL, "ok": False, "rows": {},
            "meta": {"sql": query[:500]}, "error": message}

@tool("sql_exec", description='Run one agent-written read-only analytical query over the warehouse.\n\nThe query must be a single SELECT or WITH statement over the declared\nsilver tables. Writes, stacked statements, and tables outside the\ndeclared set are refused before execution. Results are capped at\nRERUN_ROW_CAP rows with a RERUN_TIMEOUT_S statement timeout, and a\nquery that returns nothing fails instead of publishing an empty\nanswer. Name the primary numeric column for what it measures, so a\npercentage answers as TS_PCT and a count as `n`; the column you\nalias is the column a citation binds to. Returned rows are computed\nfrom the supplied SQL, never curated table values.\n\nEvery ok result also carries meta.basis and meta.profile. meta.basis\nis a local, best-effort classification of the query’s own SELECT\nlist, by 0-based column ordinal into the result’s column list: it\nreports which projected expressions are direct COUNT aggregates —\nCOUNT(*) (number of input rows in each returned group; ungrouped, the total input rows), COUNT(column) (number of non-null input values of that column in each group), and COUNT(DISTINCT ...)\n(never an entity count; a scalar distinct argument skips NULLs, a composite tuple value may include NULL components). If any projection cannot\nbe accounted for — stars, duplicates, wrapped or nested counts,\nsetops, parse doubt — basis fails closed to status="unavailable" and\nsays nothing about your numbers. meta.profile reports only the\nreturned (post-cap) rows: how many rows were returned and, per\ncolumn, how many returned values were non-null. It never reports\npre-cap totals or entity counts. Both describe only what was\nreturned, not what your query means, and neither validates your\nlogic. If you need a contributor count for an expression such as\nAVG, or distinct-value counts, add COUNT(metric) or COUNT(DISTINCT x)\ncolumns to your own query — the warehouse answers those\ndirectly.')
async def sql_exec(sql: str) -> dict[str, Any]:
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
    result = {"tool": TOOL, "ok": True, "rows": rows,
              "columns": out.get("columns", []), "sql": query, "meta": meta}
    out_columns = out.get("columns", [])
    result["meta"].update(count_evidence_meta(query, out_columns, rows))
    schema_tables: dict[str, Any] = {}
    if tables:
        _present, columns = _get_warehouse_schema()
        for name in tables:
            if name in columns:
                schema_tables[name] = columns[name]
            elif name.lower() in columns:
                schema_tables[name] = columns[name.lower()]
    return annotate_result(result, annotate_schema({"tables": schema_tables}))
