from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from api_tools.franchise_history import get_franchise_history as fetch_franchise_history_data

class FranchiseHistoryInput(BaseModel):
    """Input schema for the NBA Franchise History tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )

@tool("get_nba_franchise_history", args_schema=FranchiseHistoryInput)
def get_nba_franchise_history(
    league_id: str = "00"
) -> str:
    """Fetches comprehensive NBA franchise history data, including team information, time period, performance metrics (wins, losses, win percentage), and achievements (playoff appearances, division/conference/league titles). Allows filtering by league."""
    json_response = fetch_franchise_history_data(
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from api_tools.franchise_players import get_franchise_players as fetch_franchise_players_data

class FranchisePlayersInput(BaseModel):
    """Input schema for the NBA Franchise Players tool."""
    team_id: str = Field(
        description="NBA API team ID (e.g., '1610612747' for Los Angeles Lakers)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    per_mode_detailed: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'All-Star')."
    )

@tool("get_nba_franchise_players", args_schema=FranchisePlayersInput)
def get_nba_franchise_players(
    team_id: str,
    league_id: str = "00",
    per_mode_detailed: str = "Totals",
    season_type_all_star: str = "Regular Season"
) -> str:
    """Fetches comprehensive NBA franchise player roster history, including player info, game stats, shooting stats, and other traditional stats. Allows filtering by team ID, league, per mode (totals or per game), and season type."""
    json_response = fetch_franchise_players_data(
        team_id=team_id,
        league_id=league_id,
        per_mode_detailed=per_mode_detailed,
        season_type_all_star=season_type_all_star,
        return_dataframe=False
    )
    return json_response

from api_tools.franchise_leaders import get_franchise_leaders as fetch_franchise_leaders_data

class FranchiseLeadersInput(BaseModel):
    """Input schema for the NBA Franchise Leaders tool."""
    team_id: str = Field(
        description="NBA API team ID (e.g., '1610612747' for Los Angeles Lakers)."
    )

@tool("get_nba_franchise_leaders", args_schema=FranchiseLeadersInput)
def get_nba_franchise_leaders(team_id: str) -> str:
    """Fetches all-time statistical leaders for a specific NBA franchise, including points, assists, rebounds, blocks, and steals leaders. Requires a team ID."""
    json_response = fetch_franchise_leaders_data(
        team_id=team_id,
        return_dataframe=False
    )
    return json_response