import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from analyst.tools import (
    LIVE_CALL_TIMEOUT_S,
    LIVE_ONLY_TOOLS,
    NETWORK_TOOL_SOURCES,
    PARAM_SCHEMA_DESCRIPTIONS as _PARAM_DESCRIPTIONS,
    TOOL_PARAM_DESCRIPTIONS as _TOOL_PARAM_DESCRIPTIONS,
    TOOL_SCHEMA_DESCRIPTIONS as _TOOL_SCHEMA_DESCRIPTIONS,
    WAREHOUSE_ALTERNATIVES,
    WAREHOUSE_FALLBACK_TOOL,
    WAREHOUSE_QUERY_TOOL,
    briefing as _briefing_tools,
    cba as _cba_tools,
    common as _common,
    core as _core_tools,
    league as _league_tools,
    matchup as _matchup_tools,
    player as _player_tools,
    rankings as _rankings_tools,
    spatial as _spatial_tools,
    team as _team_tools,
)

sanitize_for_wire = _common.sanitize_for_wire
_sanitize_floats = _common._sanitize_floats
wire_default = _common.wire_default
_network_meta = _common._network_meta
_live_timeout_error = _common._live_timeout_error
_timeout_error = _common._timeout_error
_bounded_live_call = _common._bounded_live_call
_execute_tool_bounded = _common._execute_tool_bounded
_row_list_result = _common._row_list_result
_flatten_sections = _common._flatten_sections
_section_object_result = _common._section_object_result
_sectioned_result = _common._sectioned_result

_TOOL_ORDER = (
    "sql_exec",
    "warehouse_schema",
    "get_rapm",
    "get_impact_rank",
    "get_game_prediction",
    "get_wpa_leaders",
    "get_comps",
    "get_lineup_stats",
    "get_win_prob",
    "get_on_off",
    "get_shot_zones",
    "get_four_factors",
    "get_clutch_stats",
    "get_competitive_ratings",
    "get_hustle",
    "get_injuries",
    "get_news_feed",
    "get_team_daily_brief",
    "get_award_results",
    "get_briefing",
    "get_standings",
    "get_rest",
    "get_team_trajectory",
    "get_ratings",
    "get_rookie_leaders",
    "get_cap_ledger",
    "get_leaders",
    "get_lineup_leaders",
    "get_playoffs",
    "get_team_leaders",
    "get_team_compare",
    "get_elo_standings",
    "get_draft_board",
    "get_combine",
    "get_young_player_usage",
    "get_contract_value",
    "get_trade_check",
    "get_trade_value",
    "get_trade_partners",
    "get_situational_splits",
    "get_playoff_sim",
    "get_playoff_team_ratings",
    "get_player_risers",
    "get_standings_deep",
    "get_warehouse_freshness",
    "get_finder",
    "get_draft_model",
    "get_leaderboard_deltas",
    "get_player_ratings",
    "get_risers",
    "get_team_four_factors",
    "get_streaks",
    "get_playtype_profile",
    "get_defensive_matchups",
    "get_head_to_head",
    "get_lineup_matchup_matrix",
    "get_transactions",
    "get_wowy",
    "get_shot_compare",
    "get_raptor_history",
    "get_season_series",
    "get_team_game_log",
    "get_zone_deltas",
    "search_shots",
    "get_stint_timeline",
    "get_possession_log",
    "get_elo",
    "get_team_shot_zones",
    "get_historical_leaders",
    "get_today",
    "get_morning_briefing",
    "get_tracking_profile",
    "get_rest_advantage",
    "get_rapm_prior",
    "search_game_logs",
    "get_dataset",
    "get_dataset_freshness",
    "get_career_arc",
    "run_python",
    "get_matchup_preview",
    "get_matchup_splits",
    "get_regression_check",
    "get_scout_pack",
    "get_opponent_scout",
    "get_rotation_check",
    "get_injury_impact",
    "get_matchup_brief",
    "get_watchlist",
    "get_games_on_date",
    "get_boxscore",
    "get_award_race",
    "get_last_x",
    "get_player_report",
    "get_team_hub",
    "get_lineups",
    "get_splits",
    "get_recap",
    "get_scouting_report",
    "get_free_agents",
    "get_expectations",
)

_REGISTRARS = (
    _core_tools,
    _league_tools,
    _rankings_tools,
    _player_tools,
    _team_tools,
    _spatial_tools,
    _cba_tools,
    _matchup_tools,
    _briefing_tools,
)


def _season_param_doc(default: Any) -> str:
    if isinstance(default, int) or (isinstance(default, str) and default.isdigit()):
        return f"Season year number (e.g. 2025 means the 2025-26 season). Default: {default!r}."
    if default in (None, ""):
        return "Season id 'YYYY-YY' (e.g. '2026-27'); omit for the latest season."
    return f"Season id 'YYYY-YY' (e.g. '2026-27'). Default: {default!r}."


def _param_doc(tool_name: str, field_name: str, field: Any) -> str | None:
    if field_name == "season":
        return _season_param_doc(field.default)
    doc = _TOOL_PARAM_DESCRIPTIONS.get((tool_name, field_name)) or _PARAM_DESCRIPTIONS.get(field_name)
    if doc is None:
        return None
    from pydantic_core import PydanticUndefined
    if "{d}" in doc:
        doc = doc.format(d=field.default)
    elif field.default is not PydanticUndefined:
        doc = f"{doc} Default: {field.default!r}."
    return doc


def _apply_tool_metadata(registry: dict[str, Any]) -> None:
    for network_name in NETWORK_TOOL_SOURCES:
        network_tool = registry[network_name].model_copy(deep=True)
        registry[network_name] = network_tool
        backing = (
            "Live only." if network_name in LIVE_ONLY_TOOLS
            else "Warehouse-backed with live fallback."
        )
        if not network_tool.description.endswith(backing):
            network_tool.description = f"{network_tool.description} {backing}"
    for schema_name, schema_doc in _TOOL_SCHEMA_DESCRIPTIONS.items():
        schema_tool = registry.get(schema_name)
        if schema_tool is not None and schema_tool.args_schema is not None:
            schema_tool.args_schema.__doc__ = schema_doc
    for tool_name, tool in registry.items():
        apply_param_docs(tool_name, tool)


def apply_param_docs(tool_name: str, tool: Any) -> None:
    fields = getattr(tool.args_schema, "model_fields", None)
    if not fields:
        return
    changed = False
    for field_name, field in fields.items():
        if field.description:
            continue
        doc = _param_doc(tool_name, field_name, field)
        if doc:
            field.description = doc
            changed = True
    if changed:
        tool.args_schema.model_rebuild(force=True)


def catalogue() -> dict[str, Any]:
    pool: dict[str, Any] = {}
    for mod in _REGISTRARS:
        pool.update(mod.register())
    registry = {name: pool[name] for name in _TOOL_ORDER}
    _apply_tool_metadata(registry)
    return registry


TOOL_REGISTRY = catalogue


async def main() -> None:
    os.environ.setdefault("DIME_LIVE_ATTEMPTS", "1")
    warehouse = Path(os.environ["DIME_WAREHOUSE"])
    if not warehouse.is_absolute() or not warehouse.is_file():
        raise ValueError("DIME_WAREHOUSE must be an explicit existing absolute file")
    from analyst.direct_data import internal_catalogue
    tools = {**catalogue(), **internal_catalogue()}

    async def list_tools(_ctx: Any, _params: Any) -> ListToolsResult:
        return ListToolsResult(tools=[
            Tool(name=item.name, description=item.description,
                 inputSchema=item.args_schema.model_json_schema())
            for item in tools.values()
        ])

    async def call_tool(_ctx: Any, params: Any) -> CallToolResult:
        try:
            result = await _execute_tool_bounded(tools, params.name, params.arguments or {})
            sanitized = sanitize_for_wire(result)
            return CallToolResult(content=[
                TextContent(type="text", text=json.dumps(sanitized, allow_nan=False, default=wire_default))
            ])
        except Exception as error:
            return CallToolResult(isError=True, content=[
                TextContent(type="text", text=f"{type(error).__name__}: {error}")
            ])

    server = Server("dime-data-engine", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
