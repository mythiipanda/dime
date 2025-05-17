"""
Defines Pydantic models (schemas) and Enums for API request validation,
response serialization, and OpenAPI documentation for the NBA analytics backend.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List, Union # Union might not be used, can remove if so
from enum import Enum
import datetime # Used in validators

from backend.config import settings
from backend.core.constants import (
    MIN_PLAYER_SEARCH_LENGTH,
    MAX_SEARCH_RESULTS,
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    LeagueID,
)

# --- Enums for Request Validation and OpenAPI Documentation ---

class SearchTargetEnum(str, Enum):
    """Supported targets for the search endpoint."""
    players = "players"
    teams = "teams"
    games = "games"

class FetchTargetEnum(str, Enum):
    """Supported targets for the generic fetch endpoint."""
    player_info = "player_info"
    player_gamelog = "player_gamelog"
    team_info = "team_info"
    player_career_stats = "player_career_stats"
    find_games = "find_games"

class SeasonTypeEnum(str, Enum):
    """Enum for NBA season types, mapping to nba_api constants."""
    regular_season = SeasonTypeAllStar.regular
    playoffs = SeasonTypeAllStar.playoffs
    pre_season = SeasonTypeAllStar.preseason
    all_star = SeasonTypeAllStar.all_star

class PerModeEnum(str, Enum):
    """Enum for statistical per modes, mapping to nba_api constants."""
    per_game = PerModeDetailed.per_game
    totals = PerModeDetailed.totals
    per_36 = PerModeDetailed.per_36
    per_minute = PerModeDetailed.per_minute
    # Add other PerModeDetailed options if needed

class LeagueIDEnum(str, Enum):
    """Enum for league IDs, mapping to nba_api constants."""
    nba = LeagueID.nba
    wnba = LeagueID.wnba
    g_league = LeagueID.g_league

# --- Request Schemas ---

class PlayerAnalysisRequest(BaseModel):
    """Request schema for the /api/v1/analyze/player endpoint."""
    player_name: str = Field(..., description="Full name of the player to analyze (e.g., 'LeBron James').")
    season: Optional[str] = Field(
        default=None,
        description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in the logic layer if not provided.",
        pattern=r"^\d{4}-\d{2}$"
    )
    season_type: Optional[SeasonTypeEnum] = Field(
        default=SeasonTypeEnum.regular_season,
        description="Type of season for the analysis."
    )
    per_mode: Optional[PerModeEnum] = Field(
        default=PerModeEnum.per_game,
        description="Statistical mode for the analysis (e.g., 'PerGame', 'Totals')."
    )
    league_id: Optional[LeagueIDEnum] = Field(
        default=LeagueIDEnum.nba,
        description="League ID for the analysis."
    )

    @validator('season', pre=True, always=True) # pre=True to catch empty strings before pattern validation
    def validate_optional_season_format(cls, v: Optional[str]) -> Optional[str]:
        """Ensures that if a season is provided, it matches YYYY-YY format. Allows None."""
        if v is not None and v != "": # Allow None, but if string, validate
            if not (isinstance(v, str) and len(v) == 7 and v[4] == '-'):
                # Pydantic's pattern validation will also catch this,
                # but this validator can provide a more specific message or handle empty strings.
                raise ValueError("Season must be in YYYY-YY format if provided and not empty.")
        return v

class FetchRequestParamsPlayerInfo(BaseModel):
    player_name: str = Field(..., description="Full name of the player.")

class FetchRequestParamsPlayerGamelog(BaseModel):
    player_name: str = Field(..., description="Full name of the player.")
    season: str = Field(..., description="NBA season in YYYY-YY format (e.g., '2023-24').", pattern=r"^\d{4}-\d{2}$")
    season_type: Optional[SeasonTypeEnum] = Field(default=SeasonTypeEnum.regular_season, description="Type of season.")

class FetchRequestParamsTeamInfo(BaseModel):
    team_identifier: str = Field(..., description="Team name, abbreviation, or ID.")
    season: Optional[str] = Field(default=None, description="NBA season in YYYY-YY format. Defaults to current season in logic.", pattern=r"^\d{4}-\d{2}$")

class FetchRequestParamsPlayerCareerStats(BaseModel):
    player_name: str = Field(..., description="Full name of the player.")
    per_mode: Optional[PerModeEnum] = Field(default=PerModeEnum.per_game, description="Statistical mode (e.g., 'PerGame', 'Totals', 'Per36').")

class FetchRequestParamsFindGames(BaseModel):
    player_or_team_abbreviation: str = Field(..., description="'P' for Player, 'T' for Team.", pattern=r"^[PT]$")
    player_id_nullable: Optional[int] = Field(None, description="Player's unique ID. Required if player_or_team_abbreviation='P'.")
    team_id_nullable: Optional[int] = Field(None, description="Team's unique ID. Required if player_or_team_abbreviation='T'.")
    season_nullable: Optional[str] = Field(None, description="NBA season in YYYY-YY format.", pattern=r"^\d{4}-\d{2}$")
    season_type_nullable: Optional[SeasonTypeEnum] = Field(None, description="Type of season.")
    league_id_nullable: Optional[LeagueIDEnum] = Field(LeagueIDEnum.nba, description="League ID.")
    date_from_nullable: Optional[str] = Field(None, description="Start date (YYYY-MM-DD).", pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_to_nullable: Optional[str] = Field(None, description="End date (YYYY-MM-DD).", pattern=r"^\d{4}-\d{2}-\d{2}$")

    @validator('date_from_nullable', 'date_to_nullable', pre=True, always=True)
    def validate_optional_date_format(cls, v):
        if v is not None and v != "": 
            try:
                datetime.datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format if provided.")
        return v
        
class FetchRequest(BaseModel):
    target: FetchTargetEnum = Field(..., description="Specifies the type of data to fetch.")
    params: Dict[str, Any] = Field(default_factory=dict, description="A dictionary of parameters specific to the chosen target. See endpoint documentation for required params per target.")

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any] = Field(..., description="The raw data dictionary to be normalized.")

class TeamRequest(BaseModel):
    team_identifier: str = Field(..., description="Team name, abbreviation, or ID.")
    season: Optional[str] = Field(
        default=None, 
        description="NBA season in YYYY-YY format (e.g., '2023-24').", 
        pattern=r"^\d{4}-\d{2}$"
    )

class SearchRequest(BaseModel):
    target: SearchTargetEnum = Field(..., description="The type of entity to search for (players, teams, or games).")
    query: str = Field(..., description=f"The search query string. Minimum length: {MIN_PLAYER_SEARCH_LENGTH} characters for player search.", min_length=MIN_PLAYER_SEARCH_LENGTH)
    limit: int = Field(default=10, description="Maximum number of results to return.", gt=0, le=MAX_SEARCH_RESULTS)
    season: Optional[str] = Field(
        default=None, 
        description="For 'games' target: NBA season in YYYY-YY format (e.g., '2023-24').", 
        pattern=r"^\d{4}-\d{2}$"
    )
    season_type: Optional[SeasonTypeEnum] = Field(
        default=None, 
        description="For 'games' target: Type of season."
    )