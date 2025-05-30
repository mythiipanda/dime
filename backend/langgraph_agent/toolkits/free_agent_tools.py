from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from backend.api_tools.free_agents_data import (
    get_free_agent_info as fetch_free_agent_info_data,
    get_team_free_agents as fetch_team_free_agents_data,
    get_top_free_agents as fetch_top_free_agents_data,
    search_free_agents as search_free_agents_data
)

class FreeAgentInfoInput(BaseModel):
    """Input schema for the NBA Free Agent Info tool."""
    player_id: int = Field(
        description="NBA API player ID."
    )

@tool("get_nba_free_agent_info", args_schema=FreeAgentInfoInput)
def get_nba_free_agent_info(player_id: int) -> str:
    """Fetches free agent information for a specific NBA player by their player ID."""
    json_response = fetch_free_agent_info_data(
        player_id=player_id,
        return_dataframe=False
    )
    return json_response

class TeamFreeAgentsInput(BaseModel):
    """Input schema for the NBA Team Free Agents tool."""
    team_id: int = Field(
        description="NBA API team ID."
    )

@tool("get_nba_team_free_agents", args_schema=TeamFreeAgentsInput)
def get_nba_team_free_agents(team_id: int) -> str:
    """Fetches a list of all free agents who previously played for a specific NBA team by their team ID."""
    json_response = fetch_team_free_agents_data(
        team_id=team_id,
        return_dataframe=False
    )
    return json_response

class TopFreeAgentsInput(BaseModel):
    """Input schema for the NBA Top Free Agents tool."""
    position: Optional[str] = Field(
        default=None,
        description="Optional position to filter by (e.g., 'G', 'F', 'C')."
    )
    free_agent_type: Optional[str] = Field(
        default=None,
        description="Optional free agent type filter ('UFA' for Unrestricted Free Agent, 'RFA' for Restricted Free Agent)."
    )
    limit: Optional[int] = Field(
        default=50,
        description="Maximum number of results to return (default: 50)."
    )

@tool("get_nba_top_free_agents", args_schema=TopFreeAgentsInput)
def get_nba_top_free_agents(
    position: Optional[str] = None,
    free_agent_type: Optional[str] = None,
    limit: int = 50
) -> str:
    """Fetches a list of top NBA free agents ranked by Points Per Game (PPG). Can filter by position, free agent type (UFA/RFA), and limit the number of results."""
    json_response = fetch_top_free_agents_data(
        position=position,
        free_agent_type=free_agent_type,
        limit=limit,
        return_dataframe=False
    )
    return json_response

class SearchFreeAgentsInput(BaseModel):
    """Input schema for the Search NBA Free Agents tool."""
    player_name: str = Field(
        description="Player name to search for (partial matches allowed)."
    )

@tool("search_nba_free_agents", args_schema=SearchFreeAgentsInput)
def search_nba_free_agents(player_name: str) -> str:
    """Searches for NBA free agents by player name, allowing for partial matches."""
    json_response = search_free_agents_data(
        player_name=player_name,
        return_dataframe=False
    )
    return json_response