from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from api_tools.synergy_tools import (
    fetch_synergy_play_types_logic,
    VALID_PLAY_TYPES,
    VALID_TYPE_GROUPINGS
)
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar
)

class SynergyPlayTypesInput(BaseModel):
    """Input schema for the Synergy Play Types tool."""
    play_type: str = Field(
        ...,
        description=f"The play type to analyze. Required. Valid options: {', '.join(VALID_PLAY_TYPES)}."
    )
    type_grouping: Optional[str] = Field(
        None,
        description=f"Whether to get offensive or defensive stats. Valid options: {', '.join(VALID_TYPE_GROUPINGS)}."
    )
    player_or_team: str = Field(
        PlayerOrTeamAbbreviation.team,
        description="Whether to get player ('P') or team ('T') data."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        SeasonTypeAllStar.regular,
        description="The type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: str = Field(
        PerModeSimple.per_game,
        description="Statistical mode ('Totals' or 'PerGame')."
    )
    league_id: str = Field(
        LeagueID.nba,
        description="League ID ('00' for NBA, '10' for WNBA, '20' for G-League)."
    )
    player_id: Optional[int] = Field(
        None,
        description="Optional player ID to filter results for a specific player."
    )
    team_id: Optional[int] = Field(
        None,
        description="Optional team ID to filter results for a specific team."
    )

@tool("get_synergy_play_types", args_schema=SynergyPlayTypesInput)
def get_synergy_play_types(
    play_type: str,
    type_grouping: Optional[str] = None,
    player_or_team: str = PlayerOrTeamAbbreviation.team,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    league_id: str = LeagueID.nba,
    player_id: Optional[int] = None,
    team_id: Optional[int] = None
) -> str:
    """
    Fetches Synergy Sports play type statistics for players or teams. Provides detailed statistics about specific play types
    (e.g., isolation, post-up, pick-and-roll) including frequency, points per possession, and scoring efficiency.
    This data is particularly useful for analyzing offensive and defensive tendencies and effectiveness.

    Examples of play types include:
    - "Isolation" - One-on-one plays
    - "PostUp" - Plays initiated in the post
    - "PRBallHandler" - Pick and roll ball handler
    - "Transition" - Fast break opportunities
    - "SpotUp" - Spot-up shooting situations
    """
    
    json_response = fetch_synergy_play_types_logic(
        league_id=league_id,
        per_mode=per_mode,
        player_or_team=player_or_team,
        season_type=season_type,
        season=season,
        play_type_nullable=play_type,
        type_grouping_nullable=type_grouping,
        player_id_nullable=player_id,
        team_id_nullable=team_id,
        return_dataframe=False
    )
    return json_response