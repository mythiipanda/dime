from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from backend.api_tools.fantasy_widget import get_fantasy_widget as fetch_fantasy_widget_data

class FantasyWidgetInput(BaseModel):
    """Input schema for the NBA Fantasy Widget tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    active_players: Optional[str] = Field(
        default="N",
        description="Filter for active players ('Y' for yes, 'N' for no)."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of last games to consider (e.g., 5, 10, 0 for all games)."
    )
    todays_opponent: Optional[str] = Field(
        default="0",
        description="Filter for today's opponent ('0' for no filter, '1' for filter)."
    )
    todays_players: Optional[str] = Field(
        default="N",
        description="Filter for today's players ('Y' for yes, 'N' for no)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="NBA API team ID to filter by."
    )
    position: Optional[str] = Field(
        default=None,
        description="Player position to filter by (e.g., 'F', 'C', 'G', 'F-C', 'F-G', 'G-F', 'C-F')."
    )

@tool("get_nba_fantasy_widget_data", args_schema=FantasyWidgetInput)
def get_nba_fantasy_widget_data(
    league_id: str = "00",
    season: str = "2024-25",
    season_type: str = "Regular Season",
    active_players: str = "N",
    last_n_games: int = 0,
    todays_opponent: str = "0",
    todays_players: str = "N",
    team_id: Optional[str] = None,
    position: Optional[str] = None
) -> str:
    """Fetches comprehensive fantasy basketball data, including player info, game stats, fantasy points, and traditional stats. Allows filtering by league, season, season type, active players, last N games, today's opponent, today's players, team ID, and position."""
    json_response = fetch_fantasy_widget_data(
        league_id=league_id,
        season=season,
        season_type=season_type,
        active_players=active_players,
        last_n_games=last_n_games,
        todays_opponent=todays_opponent,
        todays_players=todays_players,
        team_id=team_id,
        position=position,
        return_dataframe=False
    )
    return json_response