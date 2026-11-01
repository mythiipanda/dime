"""Named Dime data operations over MCP stdio. Pi receives a fixed read-only view."""

import asyncio
import json
import os
from pathlib import Path
import sys
from datetime import date, datetime
from decimal import Decimal

# Resolve source imports independently of the private working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


def catalogue():
    from shared.tools.sql_exec import sql_exec
    from shared.tools.league import _get_warehouse_schema
    from shared.tools.season_semantics import annotate_schema
    from langchain_core.tools import tool

    @tool
    def warehouse_schema(tables: list[str] | None = None) -> dict:
        """Read declared warehouse columns, source units and season encodings.

        Pass tables to return only those declared tables. catalog_scope covers
        the returned declared tables and columns only, not the full warehouse
        inventory; a name absent here is not evidence it is absent everywhere.
        """
        _, columns = _get_warehouse_schema()
        if tables is None:
            selected = list(columns)
        else:
            selected = []
            unknown = []
            for name in dict.fromkeys(tables):
                if name in columns:
                    selected.append(name)
                else:
                    unknown.append(name)
            if unknown:
                raise ValueError(
                    "unknown declared table(s) in tables selection: "
                    f"{', '.join(unknown)}; omit tables for the full declared schema")
            if not selected:
                raise ValueError(
                    "tables selection must name at least one declared table; "
                    "omit tables for the full declared schema")
        annotated = annotate_schema(
            {"tables": {name: columns[name] for name in selected}})
        annotated["catalog_scope"] = {
            "kind": "declared_read_only_tables",
            "exhaustive_warehouse_inventory": False,
            "available_table_count": len(columns),
            "returned_table_count": len(selected),
            "negative_claim_scope": "returned declared tables and columns only",
        }
        return annotated

    # Deliberately do not export WAREHOUSE_TOOLS, which includes mutators.
    return {item.name: item for item in (sql_exec, warehouse_schema)}


def wire_default(value):
    # Dataset rows previously crossed FastAPI's JSON encoder. Preserve those
    # date and numeric representations at the explicit MCP boundary.
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value.as_tuple().exponent >= 0 else float(value)
    raise TypeError("Data result is not JSON serializable")


async def main():
    warehouse = Path(os.environ["DIME_WAREHOUSE"])
    if not warehouse.is_absolute() or not warehouse.is_file():
        raise ValueError("DIME_WAREHOUSE must be an explicit existing absolute file")
    from analyst.direct_data import internal_catalogue
    tools = {**catalogue(), **internal_catalogue()}
    async def list_tools(_ctx, _params):
        return ListToolsResult(tools=[Tool(name=item.name, description=item.description,
                     inputSchema=item.args_schema.model_json_schema())
                for item in tools.values()])

    async def call_tool(_ctx, params):
        try:
            # SQL's existing implementation performs blocking DuckDB work. Keep
            # MCP responsive while independent read-only calls execute.
            result = await asyncio.to_thread(
                lambda: asyncio.run(tools[params.name].ainvoke(params.arguments or {})))
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, allow_nan=False, default=wire_default))])
        except Exception as error:
            return CallToolResult(isError=True, content=[TextContent(
                type="text", text=f"{type(error).__name__}: {error}")])

    server = Server("dime-data-engine", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
