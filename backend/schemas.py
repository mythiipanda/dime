from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import datetime # Added for date validation in FetchRequestParamsFindGames

# Assuming these are defined in your config.py or imported appropriately
from backend.config import (
    CURRENT_SEASON, 
    MIN_PLAYER_SEARCH_LENGTH, 
    MAX_SEARCH_RESULTS,
    SUPPORTED_SEARCH_TARGETS, 
    SUPPORTED_FETCH_TARGETS_FOR_ROUTE
)
# Import from nba_api.stats.library.parameters for default values and potential Enum mapping
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, 
    PerModeDetailed, 
    LeagueID,
    PerModeSimple, 
    PerMode36 
)

# --- Enums for Request Validation and OpenAPI Documentation ---

class SearchTargetEnum(str, Enum):
    players = "players"
    teams = "teams"
    games = "games"

class FetchTargetEnum(str, Enum):
    player_info = "player_info"
    player_gamelog = "player_gamelog"
    team_info = "team_info"
    player_career_stats = "player_career_stats"
    find_games = "find_games"
    # Add other targets from SUPPORTED_FETCH_TARGETS_FOR_ROUTE if they are implemented in routes/fetch.py

class SeasonTypeEnum(str, Enum):
    regular_season = SeasonTypeAllStar.regular # Reverted to .regular
    playoffs = SeasonTypeAllStar.playoffs     
    pre_season = SeasonTypeAllStar.preseason      # Corrected from .pre_season
    all_star = SeasonTypeAllStar.all_star     
    # Add other relevant season types if needed (e.g., .play_in)
    # play_in = SeasonTypeAllStar.play_in # Example if nba_api supports it and it's needed

class PerModeEnum(str, Enum):
    # Using values from PerModeDetailed as a base, can be expanded
    per_game = PerModeDetailed.per_game 
    totals = PerModeDetailed.totals     
    per_36 = PerModeDetailed.per_36 # PerModeDetailed.per_36 is "Per36Minutes"
                                    # PerMode36.per_36 is "Per36" - ensure consistency with tools
    per_minute = PerModeDetailed.per_minute 
    # Consider adding other PerMode options like PerModeSimple.per_game if tools use different sets
    # For example, if a tool specifically uses PerModeSimple:
    # per_game_simple = PerModeSimple.per_game 

class LeagueIDEnum(str, Enum):
    nba = LeagueID.nba 
    wnba = LeagueID.wnba 
    g_league = LeagueID.g_league 

# --- Request Schemas ---

class PlayerAnalysisRequest(BaseModel):
    """Request schema for the /player/analyze endpoint."""
    player_name: str = Field(..., description="Full name of the player to analyze (e.g., 'LeBron James').")
    season: Optional[str] = Field(
        default=None, 
        description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {CURRENT_SEASON} in the logic layer if not provided.",
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

    @validator('season')
    def validate_optional_season_format(cls, v):
        if v is not None:
            if not (isinstance(v, str) and len(v) == 7 and v[4] == '-'):
                raise ValueError("Season must be in YYYY-YY format if provided.")
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

# --- Research Route Schemas ---
class ResearchStreamQueryRequest(BaseModel):
    topic: str = Field(..., description="The main topic for the research workflow.")
    selected_sections_json: Optional[str] = Field(None, alias="selected_sections", description="A URL-encoded JSON string representing a list of specific section names to focus on (e.g., '[\"Player Analysis\", \"Team Comparison\"]'. Optional.")

class PromptSuggestionRequest(BaseModel):
    current_prompt: str = Field(..., description="The user's current research prompt to get suggestions for.")

class PromptSuggestionResponse(BaseModel):
    suggestions: List[str]