from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Draft Combine and History logic functions
from ..api_tools.draft_combine_drill_results import fetch_draft_combine_drill_results_logic
# fetch_draft_combine_drills_logic seems unused by the toolkit methods
from ..api_tools.draft_combine_nonshooting import fetch_draft_combine_nonshooting_logic
from ..api_tools.draft_combine_player_anthro import fetch_draft_combine_player_anthro_logic
from ..api_tools.draft_combine_spot_shooting import fetch_draft_combine_spot_shooting_logic
from ..api_tools.draft_combine_stats import fetch_draft_combine_stats_logic # Comprehensive combine stats
from ..api_tools.league_draft import fetch_draft_history_logic # General draft history

from nba_api.stats.library.parameters import LeagueID # Used in default args and type hints potentially
from ..config import settings # For potential CURRENT_DRAFT_YEAR or similar

# It's good practice to define a default draft year if settings don't have one specifically for draft combine
# For example, if settings.CURRENT_NBA_SEASON is "2023-24", the relevant draft combine would be for "2024" draft class.
# This logic might be more complex depending on when combines happen relative to seasons.
# For now, using a placeholder or requiring explicit year.
DEFAULT_DRAFT_YEAR = "2024" # Placeholder, adjust as needed or make season_year non-optional

@tool
def get_draft_combine_drill_results(
    season_year: str = DEFAULT_DRAFT_YEAR, # YYYY format
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA Draft Combine athletic drill results for a specific season year.
    Args:
        season_year (str): Season year in YYYY format (e.g., "2024"). Defaults to {DEFAULT_DRAFT_YEAR}.
        league_id (str): League ID. Defaults to "00" (NBA).
        return_dataframe (bool): If True, returns (JSON, {{'DraftCombineDrillResults': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_draft_combine_drill_results for season_year: {season_year}, league_id: {league_id}")
    return fetch_draft_combine_drill_results_logic(
        league_id=league_id,
        season_year=season_year,
        return_dataframe=return_dataframe
    )

@tool
def get_draft_combine_non_stationary_shooting_stats(
    season_year: str, # YYYY format - Made non-optional as per toolkit
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches draft combine non-stationary shooting data for a specific season year.
    Args:
        season_year (str): Season year in YYYY format (e.g., "2024").
        league_id (str): League ID. Defaults to "00" (NBA).
        return_dataframe (bool): If True, returns (JSON, {{'Results': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_draft_combine_non_stationary_shooting_stats for year {season_year}, league_id: {league_id}")
    return fetch_draft_combine_nonshooting_logic(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_draft_combine_player_anthropometrics(
    season_year: str, # YYYY format - Made non-optional as per toolkit
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches draft combine player anthropometric data for a specific season year.
    Args:
        season_year (str): Season year in YYYY format (e.g., "2024").
        league_id (str): League ID. Defaults to "00" (NBA).
        return_dataframe (bool): If True, returns (JSON, {{'Results': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_draft_combine_player_anthropometrics for year {season_year}, league_id: {league_id}")
    return fetch_draft_combine_player_anthro_logic(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_draft_combine_spot_shooting_stats(
    season_year: str, # YYYY format - Made non-optional as per toolkit
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches draft combine spot-up shooting data for a specific season year.
    Args:
        season_year (str): Season year in YYYY format (e.g., "2024").
        league_id (str): League ID. Defaults to "00" (NBA).
        return_dataframe (bool): If True, returns (JSON, {{'Results': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_draft_combine_spot_shooting_stats for year {season_year}, league_id: {league_id}")
    return fetch_draft_combine_spot_shooting_logic(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_comprehensive_draft_combine_stats(
    season_year: str, # YYYY-YY format or "All Time" - Made non-optional as per toolkit
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches comprehensive draft combine statistics for a specific season or all time.
    Args:
        season_year (str): Season year in YYYY-YY format (e.g., "2023-24") or "All Time".
        league_id (str): League ID. Defaults to "00" (NBA).
        return_dataframe (bool): If True, returns (JSON, {{'DraftCombineStats': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_comprehensive_draft_combine_stats for season {season_year}, league_id: {league_id}")
    return fetch_draft_combine_stats_logic(
        season_year=season_year,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_nba_draft_history_detailed(
    # Renamed to avoid conflict with the version in league_tools.py
    # Parameters match the one from league_tools.py / drafthistory.py endpoint
    season_year_nullable: Optional[str] = None, # YYYY format, e.g., "2023"
    league_id_nullable: str = LeagueID.nba, # Defaulted to NBA
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None,
    college_nullable: Optional[str] = None, # Added from drafthistory.py capability
    top_x_nullable: Optional[int] = None,    # Added from drafthistory.py capability
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed NBA draft history with multiple filter options.
    Args:
        season_year_nullable (Optional[str]): Draft season year (YYYY). Defaults to all years.
        league_id_nullable (str): League ID. Defaults to "00" (NBA).
        team_id_nullable (Optional[int]): Filter by team ID.
        round_num_nullable (Optional[int]): Filter by draft round.
        overall_pick_nullable (Optional[int]): Filter by overall pick number.
        college_nullable (Optional[str]): Filter by college.
        top_x_nullable (Optional[int]): Get top X picks for the given filters.
        return_dataframe (bool): If True, returns (JSON, {{'DraftHistory': DataFrame}}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_nba_draft_history_detailed for Season Year: {season_year_nullable or 'All'}")
    return fetch_draft_history_logic(
        season_year_nullable=season_year_nullable, 
        league_id_nullable=league_id_nullable,
        team_id_nullable=team_id_nullable, 
        round_num_nullable=round_num_nullable,
        overall_pick_nullable=overall_pick_nullable,
        college_nullable=college_nullable, # Pass through new param
        top_x_nullable=top_x_nullable,       # Pass through new param
        return_dataframe=return_dataframe
    ) 