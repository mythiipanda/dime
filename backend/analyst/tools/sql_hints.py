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
    "syntax error",
    "parser error",
    "parameter",
    "placeholder",
)
_SYNTAX_RES = (
    re.compile(r'syntax error at or near\s+"([^"]+)"', re.IGNORECASE),
    re.compile(r'syntax error at or near\s+(\S+)', re.IGNORECASE),
)
_PARAM_RES = (
    re.compile(r'values were not provided for parameter', re.IGNORECASE),
    re.compile(r'bound parameters? does not match|unexpected prepared parameter', re.IGNORECASE),
)
_MAX_HINT_TABLES = 4
_MAX_HINT_COLUMNS = 40
_MAX_COLUMN_MATCHES = 12
_MAX_DECLARED_TABLES = 48

_TABLE_CONSTANTS: dict[str, dict[str, Any]] = {
    "silver_hist_shots": {
        "season_type_id": (
            "2=regular season, 4=playoffs, 5=play-in, 6=in-season tournament; "
            "seasons before 2025-26 store NULL (regular-season games only)"
        ),
        "corner_3": "ABS(x_legacy)>=220 AND y_legacy<=92.5",
        "above_the_break_3": "shot_value=3 AND NOT (ABS(x_legacy)>=220 AND y_legacy<=92.5)",
        "rim": "shot_distance<=4",
        "midrange": "shot_value=2 AND shot_distance>4",
        "coords": "x_legacy,y_legacy are in tenths of feet",
    },
    "silver_shots": {
        "SHOT_ZONE_BASIC": (
            "'Left Corner 3','Right Corner 3','Above the Break 3','Mid-Range',"
            "'Restricted Area','In The Paint (Non-RA)','Backcourt'"
        ),
        "corner_3": "SHOT_ZONE_BASIC in ('Left Corner 3','Right Corner 3')",
        "rim": "SHOT_ZONE_BASIC='Restricted Area'",
        "midrange": "SHOT_ZONE_BASIC='Mid-Range'",
        "above_the_break_3": "SHOT_ZONE_BASIC='Above the Break 3'",
    },
    "silver_zone_splits": {
        "ZONE": "'0-3ft','3-10ft','10-16ft','16ft-3P','3P'",
    },
    "silver_clutch": {
        "GROUP_SET": "filter GROUP_SET='Players' for player rows; other group sets multiplex the table",
    },
}


def _constants_for_tables(table_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in table_names:
        consts = _TABLE_CONSTANTS.get(str(name))
        if consts:
            out[str(name)] = dict(consts)
    return out


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
        constants = _constants_for_tables(referenced)
        if constants:
            hint["table_constants"] = constants
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
    if any(rx.search(error_text) for rx in _PARAM_RES):
        hint["parameter_error"] = {
            "rule": "sql_exec takes a raw SQL string - placeholders cannot be bound",
            "fix": "inline the values as SQL literals (quote strings, keep numbers bare) and resubmit without `?` or $N placeholders",
            "example": "sql_exec(\"select PLAYER_NAME, SALARY_2026_27 from silver_salaries where TEAM = 'BOS'\")",
        }
    token = _first_capture(_SYNTAX_RES, error_text)
    if token:
        entry: dict[str, Any] = {
            "offending_token": token,
            "fix": "fix or remove the clause containing this token; check quoting, keyword order, and trailing commas",
        }
        idx = (sql or "").lower().find(token.lower())
        if idx >= 0:
            entry["clause"] = sql[max(0, idx - 60):idx + len(token) + 60].strip()
        hint["syntax_error"] = entry
    if not hint:
        return None
    return hint


def _result_rows(res: dict[str, Any]) -> list[Any]:
    rows = res.get("rows")
    if isinstance(rows, list):
        return rows
    if isinstance(rows, dict):
        return [rows] if rows else []
    return []


def schema_hint_for_sql_empty(sql: str, res: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    if _result_rows(res):
        return None
    columns = _warehouse_columns()
    if not columns:
        return None
    referenced = _referenced_tables(sql or "", columns)
    if not referenced:
        return None
    hint: dict[str, Any] = {
        "empty_result": (
            "query ran but returned 0 rows; check filter values against the "
            "column domains below (encodings, enum values, NULL semantics) "
            "before assuming the data is absent"
        ),
        "referenced_tables": {
            name: _column_names(columns[name])[:_MAX_HINT_COLUMNS] for name in referenced
        },
    }
    constants = _constants_for_tables(referenced)
    if constants:
        hint["table_constants"] = constants
    return hint
