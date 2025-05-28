# This file will manage all tools for the Langgraph agent, including NBA API tools, search, crawl, and data science tools. 

import os # Ensure os is imported first
import sys # Ensure sys is imported first
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Tuple, List

# --- Robust Import Handling for Direct Execution & Package Use ---
# 1. Get the absolute path of the current script (tool_manager.py)
#    e.g., /path/to/nba-agent/backend/langgraph_agent/tool_manager.py
_current_script_path = os.path.abspath(__file__)

# 2. Get the directory containing the current script (langgraph_agent)
#    e.g., /path/to/nba-agent/backend/langgraph_agent
_langgraph_agent_dir = os.path.dirname(_current_script_path)

# 3. Get the directory containing 'langgraph_agent' (should be 'backend')
#    e.g., /path/to/nba-agent/backend
_backend_dir = os.path.dirname(_langgraph_agent_dir)

# 4. Get the directory containing 'backend' (should be the project root)
#    e.g., /path/to/nba-agent
_project_root_dir = os.path.dirname(_backend_dir)

# 5. Add the project root directory to sys.path if not already present.
#    This allows absolute imports like 'from backend.api_tools...'
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

# --- Debugging sys.path and target module --- 
print(f"DEBUG: tool_manager.py: sys.path[0] = {sys.path[0] if sys.path else 'EMPTY'}")
print(f"DEBUG: tool_manager.py: _project_root_dir = {_project_root_dir}")
_expected_errors_path = os.path.join(_project_root_dir, 'backend', 'core', 'errors.py')
print(f"DEBUG: tool_manager.py: Expected path for backend.core.errors: {_expected_errors_path}")
print(f"DEBUG: tool_manager.py: Does errors.py exist at expected path? {os.path.exists(_expected_errors_path)}")
_expected_core_init_path = os.path.join(_project_root_dir, 'backend', 'core', '__init__.py')
print(f"DEBUG: tool_manager.py: Does core/__init__.py exist at expected path? {os.path.exists(_expected_core_init_path)}")
# --- End Debugging ---

# --- Now, proceed with imports assuming project root is in sys.path ---
from backend.api_tools.player_common_info import fetch_player_info_logic
from backend.api_tools.team_details import fetch_team_details_logic
from backend.api_tools.utils import find_player_id_or_error, PlayerNotFoundError

# --- Pydantic Schemas for Tool Arguments ---

class GetPlayerInfoArgs(BaseModel):
    player_name: str = Field(description="The name or ID of the player.")
    league_id_nullable: Optional[str] = Field(None, description="The league ID to filter results (e.g., '00' for NBA). Optional.")
    # return_dataframe is handled internally by the wrapper, not exposed to LLM
    # return_dataframe: bool = Field(False, description="Whether to return DataFrames. Always False for LLM.")


class GetTeamDetailsArgs(BaseModel):
    team_id: str = Field(description="The ID of the team (e.g., '1610612747' for Lakers).")
    # return_dataframe is handled internally by the wrapper, not exposed to LLM
    # return_dataframe: bool = Field(False, description="Whether to return DataFrames. Always False for LLM.")

# --- Tool Definitions ---

def player_info_wrapper(player_name: str, league_id_nullable: Optional[str] = None) -> str:
    """Wrapper for fetch_player_info_logic to ensure string output for LLM."""
    try:
        if not player_name.isdigit():
            actual_player_id, _ = find_player_id_or_error(player_name)
            player_identifier = str(actual_player_id)
        else:
            player_identifier = player_name
    except PlayerNotFoundError:
        player_identifier = player_name
    except Exception:
        player_identifier = player_name

    result = fetch_player_info_logic(
        player_name=player_identifier, 
        league_id_nullable=league_id_nullable, 
        return_dataframe=False
    )
    if isinstance(result, tuple):
        return result[0]
    return result

get_player_info_tool = Tool(
    name="get_player_common_info",
    description=(
        "Fetches common player information, headline stats, and available seasons for a given player. "
        "Use this to get basic biographical data, current team, position, and key performance indicators for a player. "
        "Input can be player name (e.g., 'LeBron James') or player ID (e.g., '2544')."
    ),
    func=player_info_wrapper,
    args_schema=GetPlayerInfoArgs
)

def team_details_wrapper(team_id: str) -> str:
    """Wrapper for fetch_team_details_logic to ensure string output for LLM."""
    result = fetch_team_details_logic(team_id=team_id, return_dataframe=False)
    if isinstance(result, tuple):
        return result[0]
    return result

get_team_details_tool = Tool(
    name="get_team_details",
    description=(
        "Fetches comprehensive team details including history, championships, social media, "
        "retired players, and Hall of Fame inductees for a given team ID. "
        "Example Team ID: '1610612747' for Los Angeles Lakers."
    ),
    func=team_details_wrapper,
    args_schema=GetTeamDetailsArgs
)


# --- Tool Registry ---
# This list will hold all tools available to the agent.
# More tools (DuckDuckGo, Firecrawl, PythonREPL, other api_tools) will be added here.
nba_api_tools: List[Tool] = [
    get_player_info_tool,
    get_team_details_tool,
]

all_tools = nba_api_tools
# Later, extend with:
# all_tools.extend(search_tools)
# all_tools.extend(data_analysis_tools)

# Example of how to get a dictionary of tools for Langgraph
# tool_executor = ToolExecutor(all_tools)
# runnable_tools = {tool.name: tool for tool in all_tools}

if __name__ == '__main__':
    print("Testing get_player_common_info tool with player name:")
    try:
        lebron_info = get_player_info_tool.invoke({"player_name": "LeBron James"})
        print("LeBron James Info (name):")
        # print(lebron_info) # Potentially very long
        if isinstance(lebron_info, str) and len(lebron_info) > 200:
            print(f"(Success, output is {len(lebron_info)} chars long, starting with: {lebron_info[:200]}...)")
        else:
            print(lebron_info)
    except Exception as e:
        print(f"Error testing get_player_common_info (name): {e}")

    print("\nTesting get_player_common_info tool with player ID:")
    try:
        bron_id_info = get_player_info_tool.invoke({"player_name": "2544"}) # LeBron's ID
        print("LeBron James Info (ID 2544):")
        if isinstance(bron_id_info, str) and len(bron_id_info) > 200:
            print(f"(Success, output is {len(bron_id_info)} chars long, starting with: {bron_id_info[:200]}...)")
        else:
            print(bron_id_info)
    except Exception as e:
        print(f"Error testing get_player_common_info (ID): {e}")

    print("\nTesting get_team_details tool:")
    try:
        lakers_details = get_team_details_tool.invoke({"team_id": "1610612747"}) # Lakers ID
        print("Lakers Details:")
        if isinstance(lakers_details, str) and len(lakers_details) > 200:
            print(f"(Success, output is {len(lakers_details)} chars long, starting with: {lakers_details[:200]}...)")
        else:
            print(lakers_details)
    except Exception as e:
        print(f"Error testing get_team_details: {e}")

    # Example of manually calling the wrapper
    # print("\nManual wrapper call for Curry:")
    # curry_info_str = player_info_wrapper(player_name="Stephen Curry")
    # print(curry_info_str) 