"""Direct warehouse SQL tool. The agent writes the SQL; no LLM in between."""

from typing import Any

from langchain_core.tools import tool

from ..query import query_warehouse as _run


@tool("query_warehouse")
def query_warehouse_tool(sql: str, max_rows: int = 500) -> dict[str, Any]:
    """Run your own SELECT or WITH query against the warehouse.

    Read-only: one statement, SELECT/WITH only, capped at 500 rows,
    timed out after 30 seconds. Tables are the silver_* warehouse
    tables. The result carries columns, rows, and a truncated flag
    that is true when the row cap cut the result short.
    """
    return _run(sql, max_rows=max_rows)
