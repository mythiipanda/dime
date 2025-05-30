from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.api_tools.shot_charts import fetch_player_shot_chart as fetch_player_shot_chart_data

class PlayerShotChartInput(BaseModel):
    """Input schema for the Player Shot Chart tool."""
    player_name: str = Field(
        ..., description="The full name of the player (e.g., 'LeBron James')."
    )
    season: Optional[str] = Field(
        None, description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: Optional[str] = Field(
        "Regular Season",
        description="The type of season. Options: 'Regular Season', 'Playoffs', 'Pre Season', 'All Star'."
    )
    context_measure: Optional[str] = Field(
        "FGA",
        description="The statistical measure for the shot chart. Options: 'FGA', 'FGM', 'FG_PCT', etc."
    )
    last_n_games: Optional[int] = Field(
        0,
        description="Number of most recent games to include (0 for all games in the season)."
    )

@tool("get_player_shot_chart", args_schema=PlayerShotChartInput)
def get_player_shot_chart(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    context_measure: str = "FGA",
    last_n_games: int = 0
) -> str:
    """Fetches detailed shot chart data for a specific NBA player, including shot locations, makes/misses, and zone analysis compared to league averages. Useful for understanding a player's shooting tendencies and efficiency from different areas of the court."""
    
    json_response = fetch_player_shot_chart_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        context_measure=context_measure,
        last_n_games=last_n_games,
        return_dataframe=False
    )
    return json_response