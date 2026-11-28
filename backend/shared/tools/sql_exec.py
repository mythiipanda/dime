import difflib as _difflib
import os as _os
import re as _re
from typing import Any

from langchain_core.tools import tool

from ._core import warehouse_identity_meta
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


_TABLE_GUIDANCE = {
    "silver_hist_shots": (
        "silver_hist_shots has no zone columns and no shot-zone flags; "
        "zone-level analysis belongs in get_shot_zones/get_team_shot_zones/"
        "search_shots, which compute zones from coordinates server-side. "
        "Here, locations are x_legacy/y_legacy (feet) plus shot_distance; "
        "season is an INT end-year (2024), string seasons live in _season."
    ),
}


def _binder_hint(query: str, error: str) -> str:
    generic = ("Call warehouse_schema to verify exact table names, "
               "column names, and season encodings.")
    error = error or ""
    missing = _MISSING_COL.search(error)
    func = _FUNC_MISMATCH.search(error)
    try:
        _present, columns = _get_warehouse_schema()
    except Exception:
        columns = {}
    referenced = [
        t for t in columns
        if _re.search(rf"\b{_re.escape(t)}\b", query, _re.IGNORECASE)]
    if not missing and not func:
        notes = [_TABLE_GUIDANCE[str(t).lower()] for t in referenced
                 if str(t).lower() in _TABLE_GUIDANCE]
        if notes:
            return " ".join(notes + [generic])
        return generic
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
        listed = []
        for t in referenced[:2]:
            names = list(columns.get(t, {}))
            listed.append(
                f"{t}({', '.join(names[:60])}"
                + (", ..." if len(names) > 60 else "") + ")")
        hints.append(
            "Columns on the queried tables: " + "; ".join(listed)
            + ". Rewrite the query against these names; use warehouse_schema for units and notes.")
    for t in referenced:
        note = _TABLE_GUIDANCE.get(str(t).lower())
        if note:
            hints.append(note)
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

_INTROSPECT_RE = _re.compile(
    r"information_schema|warehouse_schema\s*\(|\bDESCRIBE\b|\bSHOW\b|\bEXPLAIN\b|\bPRAGMA\b",
    _re.I)
_NON_SELECT_RE = _re.compile(r"only SELECT/WITH queries are allowed", _re.I)
_UNKNOWN_TABLES_RE = _re.compile(r"unknown or unavailable tables", _re.I)
_GENERIC_HINT = "Call warehouse_schema to verify exact table names, column names, and season encodings."


def _refusal_hint(query: str, error: str) -> str:
    if _NON_SELECT_RE.search(error):
        return ("sql_exec runs one SELECT or WITH statement over declared silver "
                "tables. DESCRIBE, SHOW TABLES, EXPLAIN and PRAGMA are refused; "
                "call warehouse_schema for table and column listings.")
    if _UNKNOWN_TABLES_RE.search(error):
        if _INTROSPECT_RE.search(query):
            return ("information_schema and catalog functions are not in the "
                    "declared table set; call warehouse_schema for the exact "
                    "table and column names instead.")
        names = _re.findall(r"[A-Za-z_][\w.]*", error.partition(":")[2]) if ":" in error else []
        mapped = []
        for name in names[:6]:
            close = _difflib.get_close_matches(
                name.rsplit(".", 1)[-1], list(TABLES), n=2, cutoff=0.5)
            if close:
                mapped.append(f"{name} -> {', '.join(close)}")
        if mapped:
            return ("Every table in the query must come from the declared "
                    "silver set. Closest declared tables: "
                    + "; ".join(mapped)
                    + ". Rewrite against these names; warehouse_schema lists "
                    "the full set with columns.")
        return ("Every table in the query must come from the declared silver "
                "set; call warehouse_schema for the exact names rather than "
                "guessing schema-qualified variants.")
    return _GENERIC_HINT


_LEADING_LINE_COMMENT = _re.compile(r"\s*--[^\n]*(?:\n|$)")
_LEADING_BLOCK_COMMENT = _re.compile(r"\s*/\*.*?\*/", _re.S)
_DESCRIBE_RE = _re.compile(r"(?i)^\s*describe\s+(?:table\s+)?([A-Za-z_][\w]*)\s*;?\s*$")
_SHOW_COLUMNS_RE = _re.compile(r"(?i)^\s*show\s+columns\s+(?:from|in)\s+([A-Za-z_][\w]*)\s*;?\s*$")
_SHOW_TABLES_RE = _re.compile(r"(?i)^\s*show\s+tables\s*;?\s*$")


def _strip_leading_comments(sql: str) -> str:
    out = sql
    while True:
        m = _LEADING_LINE_COMMENT.match(out) or _LEADING_BLOCK_COMMENT.match(out)
        if not m:
            return out.strip()
        out = out[m.end():]


def _schema_rows_for(table: str) -> list[dict[str, Any]] | None:
    try:
        _present, columns = _get_warehouse_schema()
    except Exception:
        columns = {}
    by_lower = {t.lower(): t for t in columns}
    real = by_lower.get(table.lower(), table)
    if real.lower() not in {t.lower() for t in TABLES}:
        return None
    try:
        from .league._helpers import _owned_connection
        with _owned_connection(None, read_only=True) as con:
            info = con.execute(f"PRAGMA table_info({real})").fetchall()
    except Exception:
        info = []
    if not info:
        return None
    catalog = columns.get(real, {})
    rows = []
    for r in info:
        row: dict[str, Any] = {"column_name": r[1], "column_type": str(r[2])}
        meta = catalog.get(r[1], {})
        if meta.get("unit"):
            row["unit"] = meta["unit"]
        if meta.get("note"):
            row["note"] = meta["note"]
        rows.append(row)
    return rows


def _introspection_result(query: str) -> dict[str, Any] | None:
    if _SHOW_TABLES_RE.match(query):
        rows = [{"table_name": t} for t in TABLES]
        return {"tool": TOOL, "ok": True, "rows": rows,
                "columns": ["table_name"], "row_count": len(rows),
                "sql": query,
                "meta": {"source": SOURCE, "dataset": "warehouse",
                         **warehouse_identity_meta(),
                         "sql": query[:500], "tables": [],
                         "result_type": "schema_listing",
                         "coverage": "Declared silver table allowlist; warehouse_schema carries columns, units and season notes per table."}}
    m = _DESCRIBE_RE.match(query) or _SHOW_COLUMNS_RE.match(query)
    if not m:
        return None
    table = m.group(1)
    rows = _schema_rows_for(table)
    if rows is None:
        close = _difflib.get_close_matches(table.lower(), [t.lower() for t in TABLES], n=3, cutoff=0.5)
        hint = ("Closest declared tables: " + ", ".join(close) + ". "
                if close else "") + "warehouse_schema lists every declared table with columns, units and season notes."
        return _failure(query, f"unknown or unavailable table for introspection: {table}", hint)
    cols = list(rows[0].keys()) if rows else ["column_name", "column_type"]
    return {"tool": TOOL, "ok": True, "rows": rows, "columns": cols,
            "row_count": len(rows), "sql": query,
            "meta": {"source": SOURCE, "dataset": "warehouse",
                     **warehouse_identity_meta(),
                     "sql": query[:500], "tables": [table],
                     "result_type": "schema_listing",
                     "coverage": f"Declared columns on {table} with types, units and notes from the warehouse schema catalog."}}


_TABLE_ERROR_RE = _re.compile(r"(?:no such table|table with name)\s*[:=]?\s*[`\"]?([A-Za-z0-9_]+)", _re.I)
_COLUMN_ERROR_RE = _re.compile(r"(?:does not have a column|no such column|column)\s*(?:named\s+|called\s+)?[`\"]?([A-Za-z0-9_]+)", _re.I)
def _error_suggestions(query: str, error: str) -> list[str]:
    try:
        _, columns = _get_warehouse_schema()
    except Exception:
        return []
    declared_tables = [name for name in TABLES if name in columns]
    table_match = _TABLE_ERROR_RE.search(error)
    if table_match:
        return _difflib.get_close_matches(table_match.group(1), declared_tables, n=3, cutoff=0.55)
    column_match = _COLUMN_ERROR_RE.search(error)
    if not column_match:
        return []
    token = column_match.group(1)
    mentioned = [name for name in declared_tables if _re.search(rf"\b{_re.escape(name)}\b", query, _re.I)]
    scope = mentioned or declared_tables
    names = sorted({column for name in scope for column in columns.get(name, {})})
    matches = _difflib.get_close_matches(token, names, n=3, cutoff=0.55)
    if len(mentioned) == 1 and mentioned[0] in columns:
        return [f"{mentioned[0]}.{name}" for name in matches]
    return matches

@tool("sql_exec", description='Run one agent-written read-only analytical query over the warehouse.\n\nThe query must be a single SELECT or WITH statement over the declared\nsilver tables. Writes, stacked statements, and tables outside the\ndeclared set are refused before execution. DESCRIBE <table>, SHOW COLUMNS\nand SHOW TABLES are answered from the schema catalog with column types,\nunits and season notes; information_schema and catalog functions are\nrefused. Results are capped at\nRERUN_ROW_CAP rows with a RERUN_TIMEOUT_S statement timeout; a valid\nquery returning 0 rows returns ok=True, rows=[], row_count=0, and\nmeta.empty_observation=True (unless DIME_STRICT_NONEMPTY_SQL=1).\nName the primary numeric column for what it measures, so a percentage\nanswers as TS_PCT and a count as `n`; the column you alias is the\ncolumn a citation binds to.\n\nEvery ok result also carries meta.basis and meta.profile. If you need\na contributor count for an expression such as AVG, or distinct-value\ncounts, add COUNT(metric) or COUNT(DISTINCT x) columns to your query.')
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
    query = _strip_leading_comments(query)
    introspected = _introspection_result(query)
    if introspected is not None:
        return introspected
    out = await rerun_sql(query)
    if not out.get("ok"):
        err = str(out.get("error", ""))
        hint = _refusal_hint(query, err)
        if hint == _GENERIC_HINT:
            hint = _binder_hint(query, err)
        matches = _error_suggestions(query, err)
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
        **warehouse_identity_meta(),
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
