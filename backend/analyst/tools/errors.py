from typing import Any

from .schemas import WAREHOUSE_ALTERNATIVES

_SQL_TOKENS = (
    "binder error",
    "catalog error",
    "parser error",
    "syntax error",
    "referenced column",
    "does not have a column",
    "column ",
    "select/with",
    "disallowed keyword",
    "sql ",
)

_TABLE_TOKENS = (
    "unknown declared table",
    "tables selection",
    "no such table",
    "does not exist",
    "table ",
    "warehouse unavailable",
)

_SEASON_TOKENS = (
    "season",
    "coverage",
    "yyyy-yy",
    "not in this dataset",
)

_ENTITY_TOKENS = (
    "unknown player",
    "unknown team",
    "unknown award",
    "not found",
    "10-digit",
    "no player",
    "no team",
)

_TIMEOUT_TOKENS = (
    "timed out",
    "timeout",
)

_OFFLINE_TOKENS = (
    "offline mode",
    "pi_offline",
)


def _has_any(low: str, needles: tuple[str, ...]) -> bool:
    return any(token in low for token in needles)


def _error_summary(tool_name: str, error_text: str) -> str:
    first_line = error_text.strip().splitlines()[0] if error_text.strip() else "tool error"
    short = first_line[:160]
    return f"{tool_name} failed: {short}"


def _recovery_guidance(tool_name: str, error_text: str) -> tuple[str, list[str]]:
    low = error_text.lower()
    if _has_any(low, _TABLE_TOKENS):
        return (
            "Call warehouse_schema() to inspect declared table names and check get_warehouse_freshness() for populated tables.",
            ["warehouse_schema", "get_warehouse_freshness"],
        )
    if _has_any(low, _SQL_TOKENS):
        return (
            "Inspect exact declared table and column names with warehouse_schema(tables=[...]) before retrying sql_exec.",
            ["warehouse_schema", "get_dataset_freshness"],
        )
    if tool_name == "run_python":
        return (
            "Fix the error on the marked line of the submitted code and rerun run_python; verify table and column names with warehouse_schema() if the code queries the warehouse.",
            ["warehouse_schema"],
        )
    if _has_any(low, _SEASON_TOKENS):
        return (
            "Pass a valid season format such as '2024-25' or '2025-26' and verify available seasons via get_warehouse_freshness().",
            ["get_warehouse_freshness", "get_dataset_freshness"],
        )
    if _has_any(low, _ENTITY_TOKENS):
        return (
            "Verify the player name, team abbreviation/id, or game_id against get_standings(), get_leaders(), or warehouse_schema().",
            ["get_standings", "get_leaders"],
        )
    if _has_any(low, _OFFLINE_TOKENS):
        return (
            "Live fetching is disabled in offline mode; query warehouse-backed tools such as get_dataset or sql_exec.",
            ["get_dataset", "sql_exec"],
        )
    if _has_any(low, _TIMEOUT_TOKENS):
        alt = WAREHOUSE_ALTERNATIVES.get(tool_name, "get_dataset")
        return (
            f"Retry {tool_name} or fall back to the warehouse-backed {alt} tool.",
            [alt, "get_warehouse_freshness"],
        )
    return (
        f"Check arguments passed to {tool_name} or inspect available data using warehouse_schema() and get_warehouse_freshness().",
        ["warehouse_schema", "get_warehouse_freshness"],
    )


def enrich_error(tool_name: str, res: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(res, dict) or res.get("ok"):
        return res
    if res.get("ok") is not False and not res.get("error"):
        return res
    name = str(res.get("tool") or tool_name)
    res.setdefault("tool", name)
    error_text = str(res.get("error") or f"{name} failed")
    res.setdefault("error", error_text)
    hint, actions = _recovery_guidance(name, error_text)
    res.setdefault("summary", _error_summary(name, error_text))
    if "arg_miss" not in res:
        res.setdefault("recovery_hint", hint)
        res.setdefault("next_actions", actions)
    return res
