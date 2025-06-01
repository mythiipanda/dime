from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from api_tools.draft_combine_drill_results import get_draft_combine_drill_results as fetch_draft_combine_drill_results_data

class DraftCombineDrillResultsInput(BaseModel):
    """Input schema for the NBA Draft Combine Drill Results tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    season_year: Optional[str] = Field(
        default="2024",
        description="Season year in YYYY format (e.g., '2024')."
    )

@tool("get_nba_draft_combine_drill_results", args_schema=DraftCombineDrillResultsInput)
def get_nba_draft_combine_drill_results(
    league_id: str = "00",
    season_year: str = "2024"
) -> str:
    """Fetches NBA Draft Combine drill results data, including athletic measurements like vertical leap, agility times, sprint times, and bench press. Allows filtering by league and season year."""
    json_response = fetch_draft_combine_drill_results_data(
        league_id=league_id,
        season_year=season_year,
        return_dataframe=False
    )
    return json_response

from api_tools.draft_combine_nonshooting import get_draft_combine_nonshooting as fetch_draft_combine_nonshooting_data

class DraftCombineNonStationaryShootingInput(BaseModel):
    """Input schema for the NBA Draft Combine Non-Stationary Shooting tool."""
    season_year: str = Field(
        description="Season year in YYYY format (e.g., '2023')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )

@tool("get_nba_draft_combine_nonstationary_shooting", args_schema=DraftCombineNonStationaryShootingInput)
def get_nba_draft_combine_nonstationary_shooting(
    season_year: str,
    league_id: str = "00"
) -> str:
    """Fetches NBA Draft Combine non-stationary shooting data, including off-dribble and on-the-move shooting percentages and attempts. Allows filtering by season year and league."""
    json_response = fetch_draft_combine_nonshooting_data(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from api_tools.draft_combine_player_anthro import get_draft_combine_player_anthro as fetch_draft_combine_player_anthro_data

class DraftCombinePlayerAnthroInput(BaseModel):
    """Input schema for the NBA Draft Combine Player Anthropometric tool."""
    season_year: str = Field(
        description="Season year in YYYY format (e.g., '2023')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )

@tool("get_nba_draft_combine_player_anthropometric", args_schema=DraftCombinePlayerAnthroInput)
def get_nba_draft_combine_player_anthropometric(
    season_year: str,
    league_id: str = "00"
) -> str:
    """Fetches NBA Draft Combine player anthropometric data, including physical measurements like height, weight, wingspan, and standing reach. Allows filtering by season year and league."""
    json_response = fetch_draft_combine_player_anthro_data(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from api_tools.draft_combine_stats import get_draft_combine_stats as fetch_draft_combine_stats_data

class DraftCombineStatsInput(BaseModel):
    """Input schema for the NBA Draft Combine Stats tool."""
    season_year: str = Field(
        description="Season year in YYYY-YY format (e.g., '2022-23') or 'All Time'."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )

@tool("get_nba_draft_combine_stats", args_schema=DraftCombineStatsInput)
def get_nba_draft_combine_stats(
    season_year: str,
    league_id: str = "00"
) -> str:
    """Fetches comprehensive NBA Draft Combine statistics, including anthropometric measurements, physical testing results, and shooting statistics. Allows filtering by season year (or 'All Time') and league."""
    json_response = fetch_draft_combine_stats_data(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from api_tools.draft_combine_spot_shooting import get_draft_combine_spot_shooting as fetch_draft_combine_spot_shooting_data

class DraftCombineSpotShootingInput(BaseModel):
    """Input schema for the NBA Draft Combine Spot Shooting tool."""
    season_year: str = Field(
        description="Season year in YYYY format (e.g., '2023')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )

@tool("get_nba_draft_combine_spot_shooting", args_schema=DraftCombineSpotShootingInput)
def get_nba_draft_combine_spot_shooting(
    season_year: str,
    league_id: str = "00"
) -> str:
    """Fetches NBA Draft Combine spot shooting data, including 15-foot, college range, and NBA range shooting percentages and attempts from different spots. Allows filtering by season year and league."""
    json_response = fetch_draft_combine_spot_shooting_data(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from api_tools.draft_combine_drills import get_draft_combine_drills as fetch_draft_combine_drills_data

class DraftCombineDrillsInput(BaseModel):
    """Input schema for the NBA Draft Combine Drills tool."""
    season_year: str = Field(
        description="Season year in YYYY format (e.g., '2023')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )

@tool("get_nba_draft_combine_drills", args_schema=DraftCombineDrillsInput)
def get_nba_draft_combine_drills(
    season_year: str,
    league_id: str = "00"
) -> str:
    """Fetches NBA Draft Combine drill results data, including physical testing metrics like vertical leap, agility times, sprint times, and bench press. Allows filtering by season year and league."""
    json_response = fetch_draft_combine_drills_data(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response