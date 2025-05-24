from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Game specific stats logic functions
from ..api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic,
    fetch_boxscore_misc_logic,
    fetch_boxscore_playertrack_logic,
    fetch_boxscore_scoring_logic,
    fetch_boxscore_hustle_logic
)
from ..api_tools.game_boxscore_matchups import fetch_game_boxscore_matchups_logic
from ..api_tools.game_playbyplay import fetch_playbyplay_logic
from ..api_tools.game_rotation import fetch_game_rotation_logic
# Alias fetch_shotchart_logic to avoid clash if shot_chart_toolkit is also converted and imported
from ..api_tools.game_visuals_analytics import fetch_shotchart_logic as fetch_game_shotchart_data_logic, fetch_win_probability_logic

from ..config import settings # May not be used directly, but good for consistency
from nba_api.stats.library.parameters import (
    EndPeriod, EndRange, RangeType, StartPeriod, StartRange, RunType # Parameters used by game endpoints
)


@tool
def get_game_boxscore_traditional(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Traditional Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0 (full game).
        end_period (int, optional): Ending period. Defaults to 0 (full game).
        start_range (int, optional): Start range in seconds. Defaults to StartRange.default.
        end_range (int, optional): End range in seconds. Defaults to EndRange.default.
        range_type (int, optional): Type of range. Defaults to RangeType.default.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_traditional called for game_id {game_id}")
    return fetch_boxscore_traditional_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type,
        return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_advanced(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    # range_type is not in the original toolkit method for advanced, assuming not used by logic
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Advanced Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0 (full game).
        end_period (int, optional): Ending period. Defaults to 0 (full game).
        start_range (int, optional): Start range in seconds. Defaults to StartRange.default.
        end_range (int, optional): End range in seconds. Defaults to EndRange.default.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_advanced called for game_id {game_id}")
    return fetch_boxscore_advanced_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_four_factors(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    # start_range, end_range, range_type not in original toolkit method for four_factors
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Four Factors Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0 (full game).
        end_period (int, optional): Ending period. Defaults to 0 (full game).
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_four_factors called for game_id {game_id}")
    return fetch_boxscore_four_factors_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_usage(
    game_id: str,
    # Period/Range filters not in original toolkit method for usage
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Usage Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_usage called for game_id {game_id}")
    return fetch_boxscore_usage_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_defensive(
    game_id: str,
    # Period/Range filters not in original toolkit method for defensive
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Defensive Box Score data (V2) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_defensive called for game_id {game_id}")
    return fetch_boxscore_defensive_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_summary(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a comprehensive summary box score (V2) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_summary called for game_id {game_id}")
    return fetch_boxscore_summary_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_misc(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Miscellaneous Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0.
        end_period (int, optional): Ending period. Defaults to 0.
        start_range (int, optional): Start range. Defaults to StartRange.default.
        end_range (int, optional): End range. Defaults to EndRange.default.
        range_type (int, optional): Range type. Defaults to RangeType.default.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_misc called for game_id {game_id}")
    return fetch_boxscore_misc_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type,
        return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_player_tracking(
    game_id: str,
    # Period/Range filters not in original toolkit method for player_tracking
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Player Tracking Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_player_tracking called for game_id {game_id}")
    return fetch_boxscore_playertrack_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_scoring(
    game_id: str,
    start_period: int = StartPeriod.default,
    end_period: int = EndPeriod.default,
    start_range: int = StartRange.default,
    end_range: int = EndRange.default,
    range_type: int = RangeType.default,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Scoring Box Score data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0.
        end_period (int, optional): Ending period. Defaults to 0.
        start_range (int, optional): Start range. Defaults to StartRange.default.
        end_range (int, optional): End range. Defaults to EndRange.default.
        range_type (int, optional): Range type. Defaults to RangeType.default.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_scoring called for game_id {game_id}")
    return fetch_boxscore_scoring_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        start_range=start_range, end_range=end_range, range_type=range_type,
        return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_hustle(
    game_id: str,
    # Period/Range filters not in original toolkit method for hustle
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Hustle Box Score data (V2) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_boxscore_hustle called for game_id {game_id}")
    return fetch_boxscore_hustle_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_boxscore_matchups(
    game_id: str,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Box Score Matchups data for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        return_dataframe (bool, optional): If True, returns (JSON, {'Matchups': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_game_boxscore_matchups called for game_id {game_id}")
    return fetch_game_boxscore_matchups_logic(
        game_id=game_id, return_dataframe=return_dataframe
    )

@tool
def get_game_play_by_play(
    game_id: str,
    start_period: int = 0, # As per toolkit default
    end_period: int = 0,   # As per toolkit default
    # Parameters below are based on common PBP filters, ensure logic function supports them
    event_types_nullable: Optional[List[str]] = None, # e.g. ["shot", "foul"]
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None, # Could be team_tricode as well depending on API
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Play-By-Play data (V3) for a given game_id.
    Args:
        game_id (str): The 10-digit ID of the game.
        start_period (int, optional): Starting period. Defaults to 0 (full game).
        end_period (int, optional): Ending period. Defaults to 0 (full game).
        event_types_nullable (Optional[List[str]], optional): Filter by specific event types.
        player_id_nullable (Optional[int], optional): Filter by events involving a specific player.
        team_id_nullable (Optional[int], optional): Filter by events involving a specific team.
        return_dataframe (bool, optional): If True, returns (JSON, {'PlayByPlay': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_game_play_by_play called for game_id {game_id}")
    # Construct a filters dictionary for the logic function if it expects one
    filters = {}
    if event_types_nullable:
        filters['event_types'] = event_types_nullable
    if player_id_nullable:
        filters['player_id'] = player_id_nullable
    if team_id_nullable:
        filters['team_id'] = team_id_nullable

    return fetch_playbyplay_logic(
        game_id=game_id, start_period=start_period, end_period=end_period,
        # Pass other filters based on how fetch_playbyplay_logic is implemented
        # For example, it might take **filters or specific named arguments.
        # Assuming it takes named arguments for now:
        event_types_nullable=event_types_nullable, 
        player_id_nullable=player_id_nullable, 
        team_id_nullable=team_id_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_game_rotation_data(
    game_id: str,
    league_id: str = "00", # As per toolkit param
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches game rotation data, showing player substitutions and time on court.
    Args:
        game_id (str): The 10-digit ID of the game.
        league_id (str, optional): League ID. Defaults to "00".
        return_dataframe (bool, optional): If True, returns (JSON, {'HomeTeamRotation': df, 'AwayTeamRotation': df}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_game_rotation_data called for game_id {game_id}")
    return fetch_game_rotation_logic(
        game_id=game_id, league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_game_shotchart_data(
    game_id: str,
    team_id_nullable: Optional[int] = None,
    player_id_nullable: Optional[int] = None,
    # Add other filters from fetch_shotchart_logic: season, season_type, context_measure, etc.
    # These might be implicitly game-specific if the logic function derives them from game_id
    # or might need to be passed if the logic is more generic.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches shot chart data for a specific game, optionally filtered by team or player.
    Args:
        game_id (str): The 10-digit ID of the game.
        team_id_nullable (Optional[int], optional): Filter by team ID.
        player_id_nullable (Optional[int], optional): Filter by player ID.
        return_dataframe (bool, optional): If True, returns (JSON, {'ShotChart': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_game_shotchart_data for game_id {game_id}, Team: {team_id_nullable}, Player: {player_id_nullable}")
    # The logic function `fetch_game_shotchart_data_logic` (aliased from fetch_shotchart_logic)
    # might require more parameters like context_measure, season, season_type. 
    # These might be derivable from game_id or needed explicitly.
    # For now, passing only the core identifiers.
    return fetch_game_shotchart_data_logic(
        game_id=game_id, 
        team_id_nullable=team_id_nullable, 
        player_id_nullable=player_id_nullable,
        # Ensure all required parameters for the logic function are passed.
        # Example: context_measure="FGM" might be a typical default if not specified.
        return_dataframe=return_dataframe
    )

@tool
def get_game_win_probability(
    game_id: str,
    run_type: str = RunType.default, # Not clear what this is from snippet, using default
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches win probability data throughout a game.
    Args:
        game_id (str): The 10-digit ID of the game.
        run_type (str, optional): Run type parameter. Defaults to RunType.default.
        return_dataframe (bool, optional): If True, returns (JSON, {'WinProbData': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_game_win_probability called for game_id {game_id}")
    return fetch_win_probability_logic(
        game_id=game_id, run_type=run_type, return_dataframe=return_dataframe
    ) 