from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.api_tools.team_dash_lineups import (
    fetch_team_lineups_logic,
    VALID_MEASURE_TYPES,
    VALID_PER_MODES,
    VALID_SEASON_TYPES,
    VALID_GROUP_QUANTITIES
)
from backend.api_tools.team_dash_pt_shots import (
    get_team_dash_pt_shots as fetch_team_dash_pt_shots,
    VALID_LEAGUE_IDS,
    VALID_LOCATIONS,
    VALID_OUTCOMES
)
from backend.api_tools.team_dashboard_shooting import (
    fetch_team_dashboard_shooting_splits_logic,
    VALID_MEASURE_TYPES as SHOOTING_MEASURE_TYPES,
    VALID_PER_MODES as SHOOTING_PER_MODES,
    VALID_SEASON_TYPES as SHOOTING_SEASON_TYPES
)
from backend.api_tools.team_details import (
    get_team_details as fetch_team_details,
    VALID_TEAM_IDS
)
from backend.api_tools.team_estimated_metrics import (
    get_team_estimated_metrics as fetch_team_estimated_metrics,
    VALID_LEAGUE_IDS as METRICS_LEAGUE_IDS,
    VALID_SEASON_TYPES as METRICS_SEASON_TYPES
)
from backend.api_tools.team_game_logs import (
    fetch_team_game_logs_logic as fetch_team_game_logs,
    VALID_SEASON_TYPES as GAMELOGS_SEASON_TYPES,
    VALID_PER_MODES as GAMELOGS_PER_MODES,
    VALID_MEASURE_TYPES as GAMELOGS_MEASURE_TYPES,
    VALID_GAME_SEGMENTS,
    VALID_LOCATIONS,
    VALID_OUTCOMES,
    VALID_SEASON_SEGMENTS,
    VALID_CONFERENCES,
    VALID_DIVISIONS
)
from backend.api_tools.team_general_stats import (
    fetch_team_stats_logic,
    _TEAM_GENERAL_VALID_SEASON_TYPES as GENERAL_SEASON_TYPES,
    _TEAM_GENERAL_VALID_PER_MODES as GENERAL_PER_MODES,
    _TEAM_GENERAL_VALID_MEASURE_TYPES as GENERAL_MEASURE_TYPES,
    _TEAM_GENERAL_VALID_LEAGUE_IDS as GENERAL_LEAGUE_IDS
)
from backend.api_tools.team_historical_leaders import (
    fetch_team_historical_leaders_logic,
    _VALID_LEAGUE_IDS_HISTORICAL as HISTORICAL_LEAGUE_IDS
)
from backend.api_tools.team_history import (
    fetch_common_team_years_logic
)
from nba_api.stats.library.parameters import LeagueID
from backend.api_tools.team_info_roster import (
    fetch_team_info_and_roster_logic,
    _TEAM_INFO_VALID_SEASON_TYPES as INFO_SEASON_TYPES,
    _TEAM_INFO_VALID_LEAGUE_IDS as INFO_LEAGUE_IDS
)
from backend.api_tools.team_passing_analytics import (
    fetch_team_passing_stats_logic
)
from backend.api_tools.team_rebounding_tracking import (
    fetch_team_rebounding_stats_logic,
    _TEAM_REB_VALID_SEASON_TYPES as REB_SEASON_TYPES,
    _TEAM_REB_VALID_PER_MODES as REB_PER_MODES
)
from backend.api_tools.team_player_dashboard import (
    fetch_team_player_dashboard_logic,
    _VALID_SEASON_TYPES as PLAYER_DASH_SEASON_TYPES,
    _VALID_PER_MODES as PLAYER_DASH_PER_MODES,
    _VALID_MEASURE_TYPES as PLAYER_DASH_MEASURE_TYPES,
    _VALID_LEAGUE_IDS as PLAYER_DASH_LEAGUE_IDS
)
from backend.api_tools.team_player_on_off_details import (
    fetch_team_player_on_off_details_logic,
    _VALID_SEASON_TYPES as ON_OFF_SEASON_TYPES,
    _VALID_PER_MODES as ON_OFF_PER_MODES,
    _VALID_MEASURE_TYPES as ON_OFF_MEASURE_TYPES,
    _VALID_LEAGUE_IDS as ON_OFF_LEAGUE_IDS,
    _VALID_GAME_SEGMENTS,
    _VALID_LOCATIONS,
    _VALID_OUTCOMES,
    _VALID_SEASON_SEGMENTS,
    _VALID_VS_CONFERENCES,
    _VALID_VS_DIVISIONS
)
from backend.api_tools.teamplayeronoffsummary import (
    fetch_teamplayeronoffsummary_logic,
    _VALID_SEASON_TYPES as ONOFF_SUMMARY_SEASON_TYPES,
    _VALID_PER_MODES as ONOFF_SUMMARY_PER_MODES,
    _VALID_MEASURE_TYPES as ONOFF_SUMMARY_MEASURE_TYPES,
    _VALID_LEAGUE_IDS as ONOFF_SUMMARY_LEAGUE_IDS
)
from backend.api_tools.team_shooting_tracking import (
    fetch_team_shooting_stats_logic,
    _TEAM_SHOOTING_VALID_SEASON_TYPES as SHOOTING_SEASON_TYPES,
    _TEAM_SHOOTING_VALID_PER_MODES as SHOOTING_PER_MODES
)
from backend.api_tools.teamvsplayer import (
    fetch_teamvsplayer_logic,
    _VALID_SEASON_TYPES as VS_PLAYER_SEASON_TYPES,
    _VALID_PER_MODES as VS_PLAYER_PER_MODES,
    _VALID_MEASURE_TYPES as VS_PLAYER_MEASURE_TYPES,
    _VALID_LEAGUE_IDS as VS_PLAYER_LEAGUE_IDS
)

class TeamLineupsInput(BaseModel):
    """Input schema for the Team Lineups tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(VALID_SEASON_TYPES.keys())}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(VALID_MEASURE_TYPES.keys())}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(VALID_PER_MODES.keys())}."
    )
    group_quantity: int = Field(
        5,
        description=f"Number of players in the lineup combination (valid values: {VALID_GROUP_QUANTITIES}). Use 5 for complete lineups, smaller numbers for partial lineup analysis."
    )

class TeamShotsInput(BaseModel):
    """Input schema for the Team Shot Dashboard tool."""
    team_id: str = Field(
        ..., 
        description="Team ID (e.g., '1610612747' for Lakers)."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "",
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: str = Field(
        "",
        description="How to present the statistics ('Totals', 'PerGame')."
    )
    league_id: str = Field(
        "",
        description=f"League ID. Valid options: {', '.join(VALID_LEAGUE_IDS)}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Valid options: {', '.join(VALID_LOCATIONS)}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Valid options: {', '.join(VALID_OUTCOMES)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (MM/DD/YYYY)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (MM/DD/YYYY)."
    )

@tool("get_team_lineups", args_schema=TeamLineupsInput)
def get_team_lineups(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
    group_quantity: int = 5
) -> str:
    """
    Fetches detailed statistics for different lineup combinations of a team. This tool provides comprehensive data about how
    different player combinations perform together, including:
    - Full 5-player lineup statistics
    - Smaller group combinations (2,3,4 players)
    - Various statistical measures (basic stats, advanced metrics, scoring data)
    - Different formats (totals, per game, per minute, etc.)
    
    Useful for:
    - Analyzing team's most effective lineups
    - Understanding player chemistry and combinations
    - Identifying strong/weak lineup patterns
    - Comparing starters vs bench units
    """
    
    json_response = fetch_team_lineups_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        group_quantity=group_quantity,
        return_dataframe=False
    )
    return json_response

class TeamGameLogsInput(BaseModel):
    """Input schema for the Team Game Logs tool."""
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(GAMELOGS_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "PerGame",
        description=f"How to present the statistics. Options: {', '.join(GAMELOGS_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(GAMELOGS_MEASURE_TYPES)}."
    )
    team_id: Optional[str] = Field(
        None,
        description="Filter by specific team ID."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (MM/DD/YYYY)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (MM/DD/YYYY)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join(VALID_GAME_SEGMENTS)}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join(VALID_LOCATIONS)}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join(VALID_OUTCOMES)}."
    )
    season_segment: Optional[str] = Field(
        None,
        description=f"Filter by season segment. Options: {', '.join(VALID_SEASON_SEGMENTS)}."
    )
    vs_conference: Optional[str] = Field(
        None,
        description=f"Filter by opponent conference. Options: {', '.join(VALID_CONFERENCES)}."
    )
    vs_division: Optional[str] = Field(
        None,
        description=f"Filter by opponent division. Options: {', '.join(VALID_DIVISIONS)}."
    )

@tool("get_team_game_logs", args_schema=TeamGameLogsInput)
def get_team_game_logs(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    team_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    season_segment: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None
) -> str:
    """
    Fetches detailed game-by-game statistics for teams. This tool provides comprehensive game logs including:
    - Basic and advanced game statistics
    - Game information (date, matchup, outcome)
    - Detailed performance metrics
    
    Can be filtered by various parameters like:
    - Date range
    - Game location (home/away)
    - Game outcome (wins/losses)
    - Opponent conference/division
    - Season segments or specific game segments
    
    Useful for:
    - Analyzing team performance trends over time
    - Evaluating home vs road performance
    - Studying matchup-specific performance
    - Identifying patterns in wins vs losses
    - Tracking team progress throughout the season
    """
    
    json_response = fetch_team_game_logs(
        season=season or "",
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        team_id=team_id or "",
        date_from=date_from or "",
        date_to=date_to or "",
        game_segment=game_segment or "",
        location=location or "",
        outcome=outcome or "",
        season_segment=season_segment or "",
        vs_conference=vs_conference or "",
        vs_division=vs_division or "",
        return_dataframe=False
    )
    return json_response

class TeamHistoricalLeadersInput(BaseModel):
    """Input schema for the Team Historical Leaders tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season_id: str = Field(
        ...,
        description="Five-digit season ID (e.g., '22022' for 2022-23 season). This specifies the point in time for which to retrieve historical leaders."
    )
    league_id: str = Field(
        "00",
        description=f"League ID. Valid options: {', '.join(HISTORICAL_LEAGUE_IDS)}."
    )

@tool("get_team_historical_leaders", args_schema=TeamHistoricalLeadersInput)
def get_team_historical_leaders(
    team_identifier: str,
    season_id: str,
    league_id: str = "00"
) -> str:
    """
    Fetches historical career statistical leaders for a specific team at a given point in time. This tool provides:
    - All-time team statistical leaders
    - Career records and achievements
    - Historical player rankings
    - Team record holders
    
    The season_id parameter determines the point in time for which you want to see the historical leaders
    (e.g., '22022' shows who the all-time leaders were as of the 2022-23 season).
    
    Useful for:
    - Researching team's greatest players
    - Analyzing historical achievements
    - Comparing players across eras
    - Understanding team records and milestones
    - Identifying franchise statistical leaders
    """
    
    json_response = fetch_team_historical_leaders_logic(
        team_identifier=team_identifier,
        season_id=season_id,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

class TeamPassingStatsInput(BaseModel):
    """Input schema for the Team Passing Stats tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description="Type of season (Regular Season, Playoffs, Pre Season, All Star)."
    )
    per_mode: str = Field(
        "PerGame",
        description="How to present the statistics ('Totals' or 'PerGame')."
    )
    last_n_games: int = Field(
        0,
        description="Number of games to include (0 for all games)."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    vs_conference: Optional[str] = Field(
        None,
        description="Filter by opponent conference ('East' or 'West')."
    )
    vs_division: Optional[str] = Field(
        None,
        description="Filter by opponent division (e.g., 'Atlantic', 'Central', 'Southeast', etc.)."
    )
    location: Optional[str] = Field(
        None,
        description="Filter by game location ('Home' or 'Road')."
    )
    outcome: Optional[str] = Field(
        None,
        description="Filter by game outcome ('W' or 'L')."
    )

@tool("get_team_passing_stats", args_schema=TeamPassingStatsInput)
def get_team_passing_stats(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    last_n_games: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None
) -> str:
    """
    Fetches detailed passing statistics for a team, including both passes made and received. This tool provides:
    - Comprehensive passing data between players
    - Pass frequency and assist metrics
    - Secondary (hockey) assist tracking
    - Player-to-player passing tendencies
    
    Data can be filtered by various parameters to analyze passing patterns in specific situations:
    - Home vs away games
    - Wins vs losses
    - Against specific conferences/divisions
    - Date ranges or last N games
    
    Useful for:
    - Analyzing team ball movement
    - Identifying key playmakers
    - Understanding passing chemistry between players
    - Evaluating offensive strategies
    - Finding successful passing combinations
    """
    
    json_response = fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        last_n_games=last_n_games,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        vs_conference_nullable=vs_conference,
        vs_division_nullable=vs_division,
        location_nullable=location,
        outcome_nullable=outcome,
        return_dataframe=False
    )
    return json_response

class TeamPlayerDashboardInput(BaseModel):
    """Input schema for the Team Player Dashboard tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(PLAYER_DASH_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(PLAYER_DASH_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(PLAYER_DASH_MEASURE_TYPES)}."
    )
    league_id: Optional[str] = Field(
        None,
        description=f"League ID. Valid options: {', '.join(PLAYER_DASH_LEAGUE_IDS)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    game_segment: Optional[str] = Field(
        None,
        description="Filter by game segment ('First Half', 'Second Half', 'Overtime')."
    )
    location: Optional[str] = Field(
        None,
        description="Filter by game location ('Home' or 'Road')."
    )
    outcome: Optional[str] = Field(
        None,
        description="Filter by game outcome ('W' or 'L')."
    )
    pace_adjust: str = Field(
        "N",
        description="Whether to adjust for pace ('Y' or 'N')."
    )
    plus_minus: str = Field(
        "N",
        description="Whether to include plus/minus ('Y' or 'N')."
    )
    rank: str = Field(
        "N",
        description="Whether to include statistical ranks ('Y' or 'N')."
    )

@tool("get_team_player_dashboard", args_schema=TeamPlayerDashboardInput)
def get_team_player_dashboard(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    measure_type: str = "Base",
    league_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N"
) -> str:
    """
    Fetches detailed player statistics and overall team performance from the team player dashboard. This tool provides:
    - Individual player season totals and averages
    - Team-wide performance metrics
    - Various statistical categories (basic, advanced, scoring, etc.)
    - Optional pace-adjusted statistics
    - Plus/minus data when requested
    - Statistical rankings when enabled
    
    Data can be filtered by:
    - Game location (home/away)
    - Game outcomes (wins/losses)
    - Game segments (first half/second half/overtime)
    - Date ranges
    
    Useful for:
    - Analyzing individual player contributions
    - Comparing players within the team
    - Understanding team composition and roles
    - Evaluating lineup effectiveness
    - Identifying leading performers in different categories
    """
    
    json_response = fetch_team_player_dashboard_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=False
    )
    return json_response

class TeamPlayerOnOffSummaryInput(BaseModel):
    """Input schema for the Team Player On/Off Summary tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(ONOFF_SUMMARY_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(ONOFF_SUMMARY_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(ONOFF_SUMMARY_MEASURE_TYPES)}."
    )
    league_id: Optional[str] = Field(
        None,
        description=f"League ID. Valid options: {', '.join(ONOFF_SUMMARY_LEAGUE_IDS)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join([opt for opt in _VALID_GAME_SEGMENTS if opt])}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join([opt for opt in _VALID_LOCATIONS if opt])}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join([opt for opt in _VALID_OUTCOMES if opt])}."
    )
    pace_adjust: str = Field(
        "N",
        description="Whether to adjust for pace ('Y' or 'N')."
    )
    plus_minus: str = Field(
        "N",
        description="Whether to include plus/minus ('Y' or 'N')."
    )
    rank: str = Field(
        "N",
        description="Whether to include statistical ranks ('Y' or 'N')."
    )

@tool("get_team_player_on_off_summary", args_schema=TeamPlayerOnOffSummaryInput)
def get_team_player_on_off_summary(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    measure_type: str = "Base",
    league_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N"
) -> str:
    """
    Fetches summarized statistics comparing team performance when specific players are on vs off the court. This tool provides:
    - Overall team summary statistics
    - Performance metrics with players OFF the court
    - Performance metrics with players ON the court
    - Impact analysis and efficiency comparisons
    
    Data can be filtered by:
    - Game location (home/away)
    - Game outcomes (wins/losses)
    - Game segments
    - Date ranges
    
    Advanced features:
    - Optional pace adjustment for normalized comparisons
    - Plus/minus calculations for direct impact assessment
    - Statistical rankings for league-wide context
    
    Useful for:
    - Evaluating player impact on team performance
    - Identifying most effective player combinations
    - Understanding unit efficiency
    - Analyzing lineup optimization opportunities
    - Making data-driven rotation decisions
    """
    
    json_response = fetch_teamplayeronoffsummary_logic(
        team_identifier=team_identifier,
        season=season,
        season_type_all_star=season_type,
        per_mode_detailed=per_mode,
        measure_type_detailed_defense=measure_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=False
    )
    return json_response

class TeamVsPlayerInput(BaseModel):
    """Input schema for the Team vs Player tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    vs_player_identifier: str = Field(
        ...,
        description="Name or ID of the opposing player to analyze."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(VS_PLAYER_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(VS_PLAYER_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(VS_PLAYER_MEASURE_TYPES)}."
    )
    league_id: Optional[str] = Field(
        None,
        description=f"League ID. Valid options: {', '.join(VS_PLAYER_LEAGUE_IDS)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join([opt for opt in _VALID_GAME_SEGMENTS if opt])}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join([opt for opt in _VALID_LOCATIONS if opt])}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join([opt for opt in _VALID_OUTCOMES if opt])}."
    )
    pace_adjust: str = Field(
        "N",
        description="Whether to adjust for pace ('Y' or 'N')."
    )
    plus_minus: str = Field(
        "N",
        description="Whether to include plus/minus ('Y' or 'N')."
    )
    rank: str = Field(
        "N",
        description="Whether to include statistical ranks ('Y' or 'N')."
    )

@tool("get_team_vs_player_stats", args_schema=TeamVsPlayerInput)
def get_team_vs_player_stats(
    team_identifier: str,
    vs_player_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    measure_type: str = "Base",
    league_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N"
) -> str:
    """
    Fetches detailed statistics comparing team performance against a specific player. This tool provides:
    - Overall matchup statistics
    - Performance with player on/off court
    - Shot area analysis (overall, on-court, off-court)
    - Shot distance breakdowns
    - Head-to-head comparisons
    
    Data includes:
    - Scoring efficiency and volume
    - Shooting percentages by location
    - Defensive impact metrics
    - Playing style indicators
    - Performance differentials
    
    Advanced features:
    - Pace-adjusted statistics
    - Plus/minus calculations
    - Statistical rankings
    
    Useful for:
    - Matchup analysis and strategy
    - Defensive game planning
    - Understanding player impact
    - Identifying favorable/unfavorable situations
    - Historical head-to-head performance
    """
    
    json_response = fetch_teamvsplayer_logic(
        team_identifier=team_identifier,
        vs_player_identifier=vs_player_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=False
    )
    return json_response

class TeamShootingStatsInput(BaseModel):
    """Input schema for the Team Shooting Stats tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(SHOOTING_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "PerGame",
        description=f"How to present the statistics. Options: {', '.join(SHOOTING_PER_MODES)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join([opt for opt in _VALID_GAME_SEGMENTS if opt])}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join([opt for opt in _VALID_LOCATIONS if opt])}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join([opt for opt in _VALID_OUTCOMES if opt])}."
    )
    vs_conference: Optional[str] = Field(
        None,
        description=f"Filter by opponent conference. Options: {', '.join([opt for opt in _VALID_VS_CONFERENCES if opt])}."
    )
    vs_division: Optional[str] = Field(
        None,
        description=f"Filter by opponent division. Options: {', '.join([opt for opt in _VALID_VS_DIVISIONS if opt])}."
    )

@tool("get_team_shooting_stats", args_schema=TeamShootingStatsInput)
def get_team_shooting_stats(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None
) -> str:
    """
    Fetches detailed team shooting statistics broken down by various factors. This tool provides:
    - Overall shooting metrics
    - General shooting splits
    - Shot clock timing analysis
    - Dribble count breakdown
    - Defender distance impact
    - Touch time statistics
    
    Data includes:
    - Field goal attempts and percentages
    - Effective field goal percentage
    - Points per shot
    - Assisted shot rates
    - Shot frequency by category
    
    Data can be filtered by:
    - Game location (home/away)
    - Game outcomes (wins/losses)
    - Game segments
    - Conference/division matchups
    - Date ranges
    
    Useful for:
    - Analyzing shooting patterns
    - Identifying optimal shot conditions
    - Understanding defensive impact
    - Evaluating shot selection
    - Developing offensive strategies
    """
    
    json_response = fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        vs_conference_nullable=vs_conference,
        vs_division_nullable=vs_division,
        return_dataframe=False
    )
    return json_response

class TeamPlayerOnOffDetailsInput(BaseModel):
    """Input schema for the Team Player On/Off Details tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(ON_OFF_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(ON_OFF_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(ON_OFF_MEASURE_TYPES)}."
    )
    league_id: Optional[str] = Field(
        None,
        description=f"League ID. Valid options: {', '.join(ON_OFF_LEAGUE_IDS)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join([opt for opt in _VALID_GAME_SEGMENTS if opt])}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join([opt for opt in _VALID_LOCATIONS if opt])}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join([opt for opt in _VALID_OUTCOMES if opt])}."
    )
    vs_conference: Optional[str] = Field(
        None,
        description=f"Filter by opponent conference. Options: {', '.join([opt for opt in _VALID_VS_CONFERENCES if opt])}."
    )
    vs_division: Optional[str] = Field(
        None,
        description=f"Filter by opponent division. Options: {', '.join([opt for opt in _VALID_VS_DIVISIONS if opt])}."
    )
    pace_adjust: str = Field(
        "N",
        description="Whether to adjust for pace ('Y' or 'N')."
    )
    plus_minus: str = Field(
        "N",
        description="Whether to include plus/minus ('Y' or 'N')."
    )
    rank: str = Field(
        "N",
        description="Whether to include statistical ranks ('Y' or 'N')."
    )

@tool("get_team_player_on_off_details", args_schema=TeamPlayerOnOffDetailsInput)
def get_team_player_on_off_details(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    measure_type: str = "Base",
    league_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N"
) -> str:
    """
    Fetches detailed statistics comparing team performance when specific players are on vs off the court. This tool provides:
    - Overall team performance metrics
    - Statistics when each player is ON the court
    - Statistics when each player is OFF the court
    - Impact analysis of player presence
    
    Data can be filtered by various parameters:
    - Game location (home/away)
    - Game outcomes (wins/losses)
    - Game segments
    - Conference/division
    - Date ranges
    
    Advanced features:
    - Optional pace adjustment
    - Plus/minus calculations
    - Statistical rankings
    
    Useful for:
    - Analyzing player impact on team performance
    - Understanding lineup effectiveness
    - Identifying key contributors
    - Evaluating player-team fit
    - Strategic rotation planning
    """
    
    json_response = fetch_team_player_on_off_details_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        league_id_nullable=league_id,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        vs_conference_nullable=vs_conference,
        vs_division_nullable=vs_division,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=False
    )
    return json_response

class TeamReboundingStatsInput(BaseModel):
    """Input schema for the Team Rebounding Stats tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(REB_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "PerGame",
        description=f"How to present the statistics. Options: {', '.join(REB_PER_MODES)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter games from this date (YYYY-MM-DD)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter games until this date (YYYY-MM-DD)."
    )
    vs_conference: Optional[str] = Field(
        None,
        description="Filter by opponent conference ('East' or 'West')."
    )
    vs_division: Optional[str] = Field(
        None,
        description="Filter by opponent division (e.g., 'Atlantic', 'Central', etc.)."
    )
    location: Optional[str] = Field(
        None,
        description="Filter by game location ('Home' or 'Road')."
    )
    outcome: Optional[str] = Field(
        None,
        description="Filter by game outcome ('W' or 'L')."
    )

@tool("get_team_rebounding_stats", args_schema=TeamReboundingStatsInput)
def get_team_rebounding_stats(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None
) -> str:
    """
    Fetches comprehensive team rebounding statistics broken down by various categories. This tool provides:
    - Overall rebounding metrics
    - Shot type-based rebounding stats (jump shots, layups, etc.)
    - Contested vs uncontested rebounds
    - Shot distance analysis
    - Rebound distance patterns
    
    Data can be filtered by various parameters to analyze rebounding in specific contexts:
    - Home vs away games
    - Wins vs losses
    - Against specific conferences/divisions
    - Custom date ranges
    
    Useful for:
    - Evaluating team rebounding effectiveness
    - Analyzing offensive vs defensive rebounding
    - Understanding rebounding patterns by shot type
    - Identifying strengths/weaknesses in different situations
    - Comparing performance across different contexts
    """
    
    json_response = fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        date_from_nullable=date_from,
        date_to_nullable=date_to,
        vs_conference_nullable=vs_conference,
        vs_division_nullable=vs_division,
        location_nullable=location,
        outcome_nullable=outcome,
        return_dataframe=False
    )
    return json_response

class TeamInfoRosterInput(BaseModel):
    """Input schema for the Team Info and Roster tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(INFO_SEASON_TYPES)}."
    )
    league_id: str = Field(
        LeagueID.nba,
        description=f"League ID. Valid options: {', '.join(INFO_LEAGUE_IDS)}."
    )

@tool("get_team_info_and_roster", args_schema=TeamInfoRosterInput)
def get_team_info_and_roster(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team information including basic details, rankings, current roster, and coaching staff.
    This tool provides:
    - Basic team information (arena, conference, division, etc.)
    - Conference and division rankings
    - Full roster with player details
    - Complete coaching staff list
    
    Useful for:
    - Getting current team composition and structure
    - Understanding team performance rankings
    - Analyzing coaching staff organization
    - Viewing complete player roster
    - Checking team standings and stats
    """
    
    json_response = fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

class TeamHistoryInput(BaseModel):
    """Input schema for the Team History tool."""
    league_id: str = Field(
        LeagueID.nba,
        description="League ID. Valid options: '00' (NBA), '10' (WNBA), '20' (G-League)."
    )

@tool("get_team_history", args_schema=TeamHistoryInput)
def get_team_history(
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches historical information about all teams in a league, showing when teams existed and their active periods.
    Useful for understanding:
    - When teams entered the league
    - Team relocations and name changes
    - Historical franchise timelines
    - Active years for each team
    - League expansion history
    
    The data includes team names and their corresponding years of existence, making it valuable for:
    - Historical research
    - Franchise timeline analysis
    - League expansion studies
    - Team relocation tracking
    """
    
    json_response = fetch_common_team_years_logic(
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

class TeamGeneralStatsInput(BaseModel):
    """Input schema for the Team General Stats tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(GENERAL_SEASON_TYPES)}."
    )
    per_mode: str = Field(
        "PerGame",
        description=f"How to present the statistics. Options: {', '.join(GENERAL_PER_MODES)}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(GENERAL_MEASURE_TYPES)}."
    )
    league_id: str = Field(
        "00",
        description=f"League ID. Options: {', '.join(GENERAL_LEAGUE_IDS)}."
    )
    date_from: Optional[str] = Field(
        None,
        description="Filter stats from this date (MM/DD/YYYY)."
    )
    date_to: Optional[str] = Field(
        None,
        description="Filter stats until this date (MM/DD/YYYY)."
    )
    game_segment: Optional[str] = Field(
        None,
        description=f"Filter by game segment. Options: {', '.join(VALID_GAME_SEGMENTS)}."
    )
    location: Optional[str] = Field(
        None,
        description=f"Filter by game location. Options: {', '.join(VALID_LOCATIONS)}."
    )
    outcome: Optional[str] = Field(
        None,
        description=f"Filter by game outcome. Options: {', '.join(VALID_OUTCOMES)}."
    )

@tool("get_team_general_stats", args_schema=TeamGeneralStatsInput)
def get_team_general_stats(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    league_id: str = "00",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    game_segment: Optional[str] = None,
    location: Optional[str] = None,
    outcome: Optional[str] = None
) -> str:
    """
    Fetches comprehensive team statistics including both current season dashboard stats and historical year-by-year
    performance. This tool provides:
    - Current season detailed statistics with various filters
    - Historical performance data across seasons
    - Multiple statistical categories (basic, advanced, scoring, etc.)
    - Filtered views by date range, game location, outcome
    
    Useful for:
    - Analyzing team performance in different contexts
    - Comparing current season stats to historical averages
    - Evaluating team trends over time
    - Understanding home vs away performance
    - Analyzing win/loss patterns
    - Tracking statistical progression across seasons
    """
    
    json_response = fetch_team_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        league_id=league_id,
        date_from=date_from,
        date_to=date_to,
        game_segment_nullable=game_segment,
        location_nullable=location,
        outcome_nullable=outcome,
        return_dataframe=False
    )
    return json_response

class TeamEstimatedMetricsInput(BaseModel):
    """Input schema for the Team Estimated Metrics tool."""
    league_id: str = Field(
        "",
        description=f"League ID. Valid options: {', '.join(METRICS_LEAGUE_IDS)}."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "",
        description=f"Type of season. Options: {', '.join(METRICS_SEASON_TYPES)}."
    )

@tool("get_team_estimated_metrics", args_schema=TeamEstimatedMetricsInput)
def get_team_estimated_metrics(
    league_id: str = "",
    season: Optional[str] = None,
    season_type: str = ""
) -> str:
    """
    Fetches advanced estimated metrics and analytics for teams. This tool provides comprehensive team metrics including:
    - Offensive and defensive ratings
    - Net rating and pace
    - Assist ratio and turnover percentage
    - Offensive and defensive rebounding percentages
    - League-wide rankings for each metric
    
    Useful for:
    - Analyzing team performance with advanced metrics
    - Comparing teams using standardized measures
    - Understanding offensive and defensive efficiency
    - Evaluating team pace and playing style
    - Identifying strengths and weaknesses in specific areas
    - Tracking team rankings in various statistical categories
    """
    
    json_response = fetch_team_estimated_metrics(
        league_id=league_id,
        season=season or "",
        season_type=season_type,
        return_dataframe=False
    )
    return json_response

class TeamShootingSplitsInput(BaseModel):
    """Input schema for the Team Shooting Splits Dashboard tool."""
    team_identifier: str = Field(
        ...,
        description="Name, abbreviation, or ID of the team (e.g., 'Lakers', 'LAL', '1610612747')."
    )
    season: Optional[str] = Field(
        None,
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: str = Field(
        "Regular Season",
        description=f"Type of season. Options: {', '.join(SHOOTING_SEASON_TYPES.keys())}."
    )
    measure_type: str = Field(
        "Base",
        description=f"Statistical category to analyze. Options: {', '.join(SHOOTING_MEASURE_TYPES.keys())}."
    )
    per_mode: str = Field(
        "Totals",
        description=f"How to present the statistics. Options: {', '.join(SHOOTING_PER_MODES.keys())}."
    )

@tool("get_team_shooting_splits", args_schema=TeamShootingSplitsInput)
def get_team_shooting_splits(
    team_identifier: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """
    Fetches detailed team shooting statistics broken down by various categories. This tool provides comprehensive
    shooting analysis including:
    - Overall shooting stats
    - Shot type breakdowns (jump shots, layups, etc.)
    - Shot area analysis (restricted area, paint, mid-range, etc.)
    - Shot distance patterns (0-5 ft, 5-8 ft, etc.)
    - Assisted vs unassisted shot analysis
    
    Useful for:
    - Analyzing team shooting patterns and tendencies
    - Identifying high-efficiency shot locations
    - Understanding team offensive strategy
    - Evaluating shot selection
    - Analyzing assist patterns and team ball movement
    """
    
    json_response = fetch_team_dashboard_shooting_splits_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=False
    )
    return json_response

class TeamDetailsInput(BaseModel):
    """Input schema for the Team Details tool."""
    team_id: str = Field(
        ...,
        description=f"ID of the team. Valid options: {', '.join(list(VALID_TEAM_IDS)[:5])} and others."
    )

@tool("get_team_details", args_schema=TeamDetailsInput)
def get_team_details(
    team_id: str
) -> str:
    """
    Fetches comprehensive team information and historical data. This tool provides detailed data including:
    - Basic team information (arena, ownership, management)
    - Team history and background
    - Social media presence
    - Championship history (NBA, Conference, Division)
    - Retired jersey numbers
    - Hall of Fame players
    
    Useful for:
    - Researching team history and achievements
    - Finding franchise milestones and records
    - Getting current team management information
    - Learning about team's legendary players
    - Understanding team's historical significance
    """
    
    json_response = fetch_team_details(
        team_id=team_id,
        return_dataframe=False
    )
    return json_response

@tool("get_team_shot_dashboard", args_schema=TeamShotsInput)
def get_team_shot_dashboard(
    team_id: str,
    season: Optional[str] = None,
    season_type: str = "",
    per_mode: str = "",
    league_id: str = "",
    location: Optional[str] = None,
    outcome: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches detailed team shooting statistics and patterns. This tool provides comprehensive shot-related data including:
    - Shot types and frequencies
    - Shooting percentages by zone
    - 2-point vs 3-point distribution
    - Efficiency metrics (eFG%)
    - Situational shooting stats
    
    Can be filtered by various parameters like game location, outcome, and date range.
    Useful for analyzing team shooting tendencies, identifying strengths/weaknesses, and comparing shooting patterns
    in different situations.
    """
    
    json_response = fetch_team_dash_pt_shots(
        team_id=team_id,
        season=season or "",
        season_type_all_star=season_type,
        per_mode_simple=per_mode,
        league_id=league_id,
        location_nullable=location or "",
        outcome_nullable=outcome or "",
        date_from_nullable=date_from or "",
        date_to_nullable=date_to or "",
        return_dataframe=False
    )
    return json_response