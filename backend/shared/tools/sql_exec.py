import difflib as _difflib
import os as _os
import re as _re
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

_MISSING_COL = _re.compile(
    r"(?:referenced column|does not have a column named|column)\s+\"?([A-Za-z_][\w.]*)\"?",
    _re.IGNORECASE)
_FUNC_MISMATCH = _re.compile(
    r"no function matches the given name and argument types\s+'?([a-z_]+)",
    _re.IGNORECASE)


def _binder_hint(query: str, error: str) -> str:
    generic = ("Call warehouse_schema to verify exact table names, "
               "column names, and season encodings.")
    error = error or ""
    missing = _MISSING_COL.search(error)
    func = _FUNC_MISMATCH.search(error)
    if not missing and not func:
        return generic
    try:
        _present, columns = _get_warehouse_schema()
    except Exception:
        columns = {}
    referenced = [
        t for t in columns
        if _re.search(rf"\b{_re.escape(t)}\b", query, _re.IGNORECASE)]
    hints = []
    if missing:
        name = missing.group(1).split(".")[-1]
        candidates = [c for t in referenced for c in columns.get(t, {})]
        close = _difflib.get_close_matches(
            name, candidates, n=3, cutoff=0.5)
        hint = f"Column '{name}' was not found."
        if close:
            hint += f" Did you mean: {', '.join(close)}?"
        hints.append(hint)
    if func:
        hints.append(
            f"'{func.group(1)}' has no overload for the argument type "
            "passed; CAST the column to a numeric type "
            "(e.g. CAST(x AS DOUBLE)) or check its type first.")
    if referenced:
        shown = "; ".join(
            f"{t}: {', '.join(columns[t])}" for t in referenced[:3])
        hints.append(f"Columns on queried tables — {shown}")
    hints.append(generic)
    return " ".join(hints)


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
        return _failure(
            query,
            f"{out.get('error', 'query failed')}; sql: {query[:500]}",
            _binder_hint(query, out.get("error", "")),
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
