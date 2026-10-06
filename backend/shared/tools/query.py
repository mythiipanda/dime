
from typing import Any

from langchain_core.tools import tool

from ..query import query_warehouse as _run

@tool("query_warehouse", description='Run your own SELECT or WITH query against the warehouse.\n\nRead-only: one statement, SELECT/WITH only, capped at 500 rows,\ntimed out after 30 seconds. Tables are the silver_* warehouse\ntables. The result carries columns, rows, and a truncated flag\nthat is true when the row cap cut the result short.')
def query_warehouse_tool(sql: str, max_rows: int = 500) -> dict[str, Any]:
    return _run(sql, max_rows=max_rows)
