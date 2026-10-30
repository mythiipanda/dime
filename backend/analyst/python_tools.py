"""Explicit read-only Dime tools served over MCP stdio. No profile discovery."""

import asyncio
import json
import os
from pathlib import Path
import sys

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
    def warehouse_schema() -> dict:
        """Read declared warehouse columns, source units and season encodings."""
        _, columns = _get_warehouse_schema()
        return annotate_schema({"tables": columns})

    # Deliberately do not export WAREHOUSE_TOOLS, which includes mutators.
    return {item.name: item for item in (sql_exec, warehouse_schema)}


async def main():
    warehouse = Path(os.environ["DIME_WAREHOUSE"])
    if not warehouse.is_absolute() or not warehouse.is_file():
        raise ValueError("DIME_WAREHOUSE must be an explicit existing absolute file")
    tools = catalogue()
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
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, allow_nan=False))])
        except Exception as error:
            return CallToolResult(isError=True, content=[TextContent(
                type="text", text=f"{type(error).__name__}: {error}")])

    server = Server("dime-readonly", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
