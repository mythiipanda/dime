import difflib
import re
from typing import Any

_MISSING_COLUMN_RES = (
    re.compile(r'Referenced column "([^"]+)" not found', re.IGNORECASE),
    re.compile(r'column "([^"]+)" not found', re.IGNORECASE),
)
_UNKNOWN_TABLE_RES = (
    re.compile(r'Table with name "?([A-Za-z0-9_]+)"? does not exist', re.IGNORECASE),
    re.compile(r'no such table:?\s*([A-Za-z0-9_]+)', re.IGNORECASE),
    re.compile(r'unknown or unavailable tables:?\s*([A-Za-z0-9_,\s]+)', re.IGNORECASE),
)
_ERROR_GATE_TOKENS = (
    "not found",
    "does not exist",
    "no such table",
    "binder error",
    "catalog error",
    "unavailable tables",
)
_MAX_HINT_TABLES = 4
_MAX_HINT_COLUMNS = 40
_MAX_COLUMN_MATCHES = 12
_MAX_DECLARED_TABLES = 48


def _warehouse_columns() -> dict[str, Any]:
    try:
        from shared.tools.league import _get_warehouse_schema
        _present, columns = _get_warehouse_schema()
    except Exception:
        return {}
    return columns if isinstance(columns, dict) else {}


def _column_names(entry: Any) -> list[str]:
    if isinstance(entry, dict):
        return [str(k) for k in entry.keys()]
    if isinstance(entry, (list, tuple)):
        names = []
        for item in entry:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("column")
                if name:
                    names.append(str(name))
        return names
    return []


def _first_capture(patterns: tuple[re.Pattern, ...], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


def _referenced_tables(sql: str, columns: dict[str, Any]) -> list[str]:
    found = []
    for name in columns.keys():
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(str(name)) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, sql, re.IGNORECASE):
            found.append(str(name))
    return found[:_MAX_HINT_TABLES]


def _column_matches(name: str, columns: dict[str, Any]) -> list[str]:
    exact = []
    pool: dict[str, str] = {}
    for table, entry in columns.items():
        for col in _column_names(entry):
            key = col.lower()
            pool.setdefault(key, f"{table}.{col}")
            if key == name.lower():
                exact.append(f"{table}.{col}")
    if exact:
        return sorted(exact)[:_MAX_COLUMN_MATCHES]
    close = difflib.get_close_matches(name.lower(), sorted(pool.keys()), n=_MAX_COLUMN_MATCHES, cutoff=0.75)
    return [pool[key] for key in close]


def schema_hint_for_sql_failure(sql: str, res: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(res, dict) or res.get("ok"):
        return None
    error_text = str(res.get("error") or "")
    low = error_text.lower()
    if not any(token in low for token in _ERROR_GATE_TOKENS):
        return None
    columns = _warehouse_columns()
    if not columns:
        return None
    hint: dict[str, Any] = {}
    referenced = _referenced_tables(sql or "", columns)
    if referenced:
        hint["referenced_tables"] = {
            name: _column_names(columns[name])[:_MAX_HINT_COLUMNS] for name in referenced
        }
    missing_column = _first_capture(_MISSING_COLUMN_RES, error_text)
    if missing_column:
        matches = _column_matches(missing_column, columns)
        if matches:
            hint["missing_column"] = missing_column
            hint["tables_with_column"] = matches
    unknown_table_text = _first_capture(_UNKNOWN_TABLE_RES, error_text)
    if unknown_table_text:
        unknown_names = [part.strip() for part in re.split(r"[,\s]+", unknown_table_text) if part.strip()]
        declared = sorted(str(name) for name in columns.keys())
        declared_by_lower = {name.lower(): name for name in declared}
        similar = []
        for name in unknown_names[:_MAX_HINT_TABLES]:
            for match in difflib.get_close_matches(name.lower(), list(declared_by_lower.keys()), n=3, cutoff=0.6):
                similar.append(declared_by_lower[match])
        hint["unknown_tables"] = unknown_names[:_MAX_HINT_TABLES]
        hint["similar_tables"] = similar[:6]
        if len(hint["similar_tables"]) == 0 and len(declared) <= _MAX_DECLARED_TABLES:
            hint["declared_tables"] = declared
    if not hint:
        return None
    return hint
