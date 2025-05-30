from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from backend.api_tools.contracts_data import (
    get_player_contract as fetch_player_contract_data,
    get_team_payroll as fetch_team_payroll_data,
    get_highest_paid_players as fetch_highest_paid_players_data,
    search_player_contracts as search_player_contracts_data
)

class PlayerContractInput(BaseModel):
    """Input schema for the NBA Player Contract tool."""
    player_id: int = Field(
        description="NBA API player ID."
    )

@tool("get_nba_player_contract", args_schema=PlayerContractInput)
def get_nba_player_contract(player_id: int) -> str:
    """Fetches contract information for a specific NBA player by their player ID."""
    json_response = fetch_player_contract_data(
        player_id=player_id,
        return_dataframe=False
    )
    return json_response

class TeamPayrollInput(BaseModel):
    """Input schema for the NBA Team Payroll tool."""
    team_id: int = Field(
        description="NBA API team ID."
    )

@tool("get_nba_team_payroll", args_schema=TeamPayrollInput)
def get_nba_team_payroll(team_id: int) -> str:
    """Fetches payroll summary for a specific NBA team by their team ID."""
    json_response = fetch_team_payroll_data(
        team_id=team_id,
        return_dataframe=False
    )
    return json_response

class HighestPaidPlayersInput(BaseModel):
    """Input schema for the Highest Paid NBA Players tool."""
    limit: Optional[int] = Field(
        default=50,
        description="Maximum number of players to return (e.g., 5, 10, 25, 50)."
    )

@tool("get_nba_highest_paid_players", args_schema=HighestPaidPlayersInput)
def get_nba_highest_paid_players(limit: int = 50) -> str:
    """Fetches a list of the highest paid NBA players by guaranteed money. Can specify a limit for the number of players returned."""
    json_response = fetch_highest_paid_players_data(
        limit=limit,
        return_dataframe=False
    )
    return json_response

class SearchPlayerContractsInput(BaseModel):
    """Input schema for the Search NBA Player Contracts tool."""
    player_name: str = Field(
        description="Player name to search for (partial matches allowed)."
    )

@tool("search_nba_player_contracts", args_schema=SearchPlayerContractsInput)
def search_nba_player_contracts(player_name: str) -> str:
    """Searches for NBA player contracts by player name, allowing for partial matches."""
    json_response = search_player_contracts_data(
        player_name=player_name,
        return_dataframe=False
    )
    return json_response