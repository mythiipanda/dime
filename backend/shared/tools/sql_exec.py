import difflib
import os as _os
import re
from typing import Any

from langchain_core.tools import tool

from .count_evidence import count_evidence_meta
from .league import (
    RERUN_ROW_CAP,
    RERUN_TIMEOUT_S,
    _SQL_TABLES,
    _get_warehouse_schema,
    rerun_sql,
)
from .season_semantics import annotate_result, annotate_schema

TOOL = "sql_exec"
TABLES = tuple(sorted(_SQL_TABLES))
SOURCE = "warehouse"
MAX_SQL_CHARS = 32000

def _failure(query: str, message: str, recovery_hint: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "tool": TOOL,
        "ok": False,
        "rows": {},
        "meta": {"sql": query[:500]},
        "error": message,
    }
    if recovery_hint:
        out["recovery_hint"] = recovery_hint
    return out

_TABLE_ERROR_RE = re.compile(r"(?:no such table|table with name)\s*[:=]?\s*[`\"]?([A-Za-z0-9_]+)", re.I)
_COLUMN_ERROR_RE = re.compile(r"(?:does not have a column|no such column|column)\s*(?:named\s+|called\s+)?[`\"]?([A-Za-z0-9_]+)", re.I)

def _error_suggestions(query: str, error: str) -> list[str]:
    try:
        _, columns = _get_warehouse_schema()
    except Exception:
        return []
    declared_tables = [name for name in TABLES if name in columns]
    table_match = _TABLE_ERROR_RE.search(error)
    if table_match:
        return difflib.get_close_matches(table_match.group(1), declared_tables, n=3, cutoff=0.55)
    column_match = _COLUMN_ERROR_RE.search(error)
    if not column_match:
        return []
    token = column_match.group(1)
    mentioned = [name for name in declared_tables if re.search(rf"\b{re.escape(name)}\b", query, re.I)]
    scope = mentioned or declared_tables
    names = sorted({column for name in scope for column in columns.get(name, {})})
    matches = difflib.get_close_matches(token, names, n=3, cutoff=0.55)
    if len(mentioned) == 1 and mentioned[0] in columns:
        return [f"{mentioned[0]}.{name}" for name in matches]
    return matches

@tool("sql_exec", description='Run one agent-written read-only analytical query over the warehouse.\n\nThe query must be a single SELECT or WITH statement over the declared\nsilver tables. Writes, stacked statements, and tables outside the\ndeclared set are refused before execution. Results are capped at\nRERUN_ROW_CAP rows with a RERUN_TIMEOUT_S statement timeout; a valid\nquery returning 0 rows returns ok=True, rows=[], row_count=0, and\nmeta.empty_observation=True (unless DIME_STRICT_NONEMPTY_SQL=1).\nName the primary numeric column for what it measures, so a percentage\nanswers as TS_PCT and a count as `n`; the column you alias is the\ncolumn a citation binds to.\n\nEvery ok result also carries meta.basis and meta.profile. If you need\na contributor count for an expression such as AVG, or distinct-value\ncounts, add COUNT(metric) or COUNT(DISTINCT x) columns to your query.')
async def sql_exec(sql: str) -> dict[str, Any]:
    query = (sql or "").strip()
    if not query:
        return _failure(
            query,
            "sql_exec: sql is required; pass one SELECT or WITH statement",
            "Pass a single SELECT or WITH query; inspect tables with warehouse_schema.",
        )
    if len(query) > MAX_SQL_CHARS:
        return _failure(
            query,
            f"sql_exec: sql is {len(query)} chars, over the {MAX_SQL_CHARS} cap",
        )
    out = await rerun_sql(query)
    if not out.get("ok"):
        hint = "Call warehouse_schema to verify exact table names, column names, and season encodings."
        matches = _error_suggestions(query, str(out.get("error", "")))
        if matches:
            hint += " Closest declared matches: " + ", ".join(matches) + "."
        return _failure(
            query,
            f"{out.get('error', 'query failed')}; sql: {query[:500]}",
            hint,
        )
    rows = out.get("rows") or []
    if not rows and _os.environ.get("DIME_STRICT_NONEMPTY_SQL") == "1":
        return _failure(
            query,
            f"sql_exec: query returned 0 rows, so no answer can be published; sql: {query[:500]}",
        )
    tables = out["tables"]
    meta: dict[str, Any] = {
        "source": SOURCE,
        "dataset": "warehouse",
        "sql": query[:500],
        "tables": tables,
        "row_cap": RERUN_ROW_CAP,
        "timeout_s": RERUN_TIMEOUT_S,
        "capped": out.get("capped", False),
        "ms": out.get("ms", 0),
        "empty_observation": len(rows) == 0,
        "result_type": "agent_sql_result",
        "model_projection": False,
        "method": (
            "agent-written read-only SQL executed under the shared kernel rails: "
            "SELECT/WITH only, one statement, writes blocked, tables limited to "
            f"the declared set, {RERUN_ROW_CAP} row cap, {RERUN_TIMEOUT_S}s "
            "statement timeout; rows are computed, not curated"
        ),
        "coverage": (
            f"Agent-written SQL over {', '.join(tables) if tables else 'no tables'}; "
            f"computed rows, never a curated table. SQL: {query[:300]}"
        ),
    }
    out_columns = out.get("columns", [])
    result = {
        "tool": TOOL,
        "ok": True,
        "rows": rows,
        "columns": out_columns,
        "row_count": len(rows),
        "sql": query,
        "meta": meta,
    }
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
