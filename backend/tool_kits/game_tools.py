"""
This module provides a toolkit of game-related functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch
various NBA game statistics and information.
Supports both JSON and DataFrame outputs with CSV caching.
"""
import logging
import json
import os
from typing import Optional, Dict, Any
from agno.tools import tool
from nba_api.stats.library.parameters import LeagueID, RunType, SeasonTypeAllStar # Added SeasonTypeAllStar

# Import specific logic functions for game tools
from ..api_tools.game_finder import fetch_league_games_logic
from ..api_tools.game_boxscores import (
    fetch_boxscore_traditional_logic,
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_boxscore_summary_logic
)
from ..api_tools.game_playbyplay import fetch_playbyplay_logic
from ..api_tools.game_visuals_analytics import (
    fetch_win_probability_logic
)
from ..api_tools.search import search_games_logic
from ..utils.path_utils import get_relative_cache_path

logger = logging.getLogger(__name__)

@tool
def get_league_games(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None,
    season_nullable: Optional[str] = None,
    season_type_nullable: Optional[str] = None, # e.g., SeasonTypeAllStar.regular
    league_id_nullable: Optional[str] = LeagueID.nba,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Finds games based on various criteria using the LeagueGameFinder endpoint.
    Previously named find_games.

    Args:
        player_or_team_abbreviation (str, optional): Specify 'P' for player or 'T' for team. Defaults to 'T'.
        player_id_nullable (Optional[int], optional): Player's ID (required if player_or_team_abbreviation='P').
        team_id_nullable (Optional[int], optional): Team's ID (required if player_or_team_abbreviation='T').
        season_nullable (Optional[str], optional): Season in YYYY-YY format (e.g., "2023-24").
        season_type_nullable (Optional[str], optional): Type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        league_id_nullable (Optional[str], optional): League ID. Defaults to "00" (NBA).
        date_from_nullable (Optional[str], optional): Start date in YYYY-MM-DD format.
        date_to_nullable (Optional[str], optional): End date in YYYY-MM-DD format.

    Returns:
        str: JSON string containing a list of found games or an error message.
    """
    logger.debug(f"Tool 'get_league_games' called with params: player_or_team={player_or_team_abbreviation}, player_id={player_id_nullable}, team_id={team_id_nullable}, season={season_nullable}, date_from={date_from_nullable}, date_to={date_to_nullable}")
    return fetch_league_games_logic(
        player_or_team_abbreviation=player_or_team_abbreviation,
        player_id_nullable=player_id_nullable,
        team_id_nullable=team_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable
    )

@tool
def get_boxscore_traditional(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0,
    range_type: int = 0,
    as_dataframe: bool = False
) -> str:
    """
    Fetches the traditional box score (BoxScoreTraditionalV3) for a specific game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        start_range (int, optional): Start of the range for range-based queries. Defaults to 0.
        end_range (int, optional): End of the range for range-based queries. Defaults to 0.
        range_type (int, optional): Type of range. Defaults to 0.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with traditional box score data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_traditional' called for game_id '{game_id}', periods {start_period}-{end_period}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_traditional_logic(
            game_id,
            start_period=start_period,
            end_period=end_period,
            start_range=start_range,
            end_range=end_range,
            range_type=range_type,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_traditional_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_traditional_logic(
            game_id,
            start_period=start_period,
            end_period=end_period,
            start_range=start_range,
            end_range=end_range,
            range_type=range_type
        )

@tool
def get_playbyplay(
    game_id: str,
    start_period: int = 0, # 0 for all
    end_period: int = 0,   # 0 for all
    event_types: str = None,  # Comma-separated list of event types (e.g., "SHOT,REBOUND,TURNOVER")
    player_name: str = None,  # Filter plays by player name
    person_id: int = None,    # Filter plays by player ID
    team_id: int = None,      # Filter plays by team ID
    team_tricode: str = None, # Filter plays by team tricode (e.g., 'LAL', 'BOS')
    as_dataframe: bool = False
) -> str:
    """
    Fetches the play-by-play data for a specific game (PlayByPlayV3).
    Previously named get_play_by_play.
    Provides granular filtering options and DataFrame output capabilities.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        event_types (str, optional): Comma-separated list of event types to filter by.
        player_name (str, optional): Filter plays by player name.
        person_id (int, optional): Filter plays by player ID.
        team_id (int, optional): Filter plays by team ID.
        team_tricode (str, optional): Filter plays by team tricode.
        as_dataframe (bool, optional): If True, returns pandas DataFrame and saves to CSV. Defaults to False.

    Returns:
        str: JSON string with play-by-play data.
    """
    logger.debug(f"Tool 'get_playbyplay' called for game_id '{game_id}', periods '{start_period}'-'{end_period}', as_dataframe={as_dataframe}")
    event_types_list = [event_type.strip().upper() for event_type in event_types.split(',')] if event_types else None
    if as_dataframe:
        json_response, dataframes = fetch_playbyplay_logic(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period,
            event_types_list=event_types_list,
            player_name=player_name,
            person_id=person_id,
            team_id=team_id,
            team_tricode=team_tricode,
            return_dataframe=True
        )
        data = json.loads(json_response)
        df_info = { "message": "Play-by-play data converted to DataFrames and saved as CSV files", "dataframes": {} }
        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_playbyplay_{key}.csv", "playbyplay"),
                    "sample_data": df.head(3).to_dict(orient="records")
                }
        data["dataframe_info"] = df_info
        return json.dumps(data)
    else:
        return fetch_playbyplay_logic(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period,
            event_types_list=event_types_list,
            player_name=player_name,
            person_id=person_id,
            team_id=team_id,
            team_tricode=team_tricode
        )

@tool
def get_boxscore_advanced(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    start_range: int = 0,
    end_range: int = 0,
    as_dataframe: bool = False
) -> str:
    """
    Fetches advanced box score data (BoxScoreAdvancedV3) for a game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        start_range (int, optional): Start of the range for range-based queries. Defaults to 0.
        end_range (int, optional): End of the range for range-based queries. Defaults to 0.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with advanced box score data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_advanced' called for game_id '{game_id}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_advanced_logic(
            game_id,
            start_period=start_period,
            end_period=end_period,
            start_range=start_range,
            end_range=end_range,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Advanced box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_advanced_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_advanced_logic(
            game_id,
            start_period=start_period,
            end_period=end_period,
            start_range=start_range,
            end_range=end_range
        )

@tool
def get_boxscore_four_factors(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    as_dataframe: bool = False
) -> str:
    """
    Fetches box score Four Factors (BoxScoreFourFactorsV3) for a game.

    Args:
        game_id (str): The ID of the game.
        start_period (int, optional): Starting period number (0 for full game). Defaults to 0.
        end_period (int, optional): Ending period number (0 for full game). Defaults to 0.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with Four Factors box score data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_four_factors' called for game_id '{game_id}', periods {start_period}-{end_period}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_four_factors_logic(
            game_id,
            start_period=start_period,
            end_period=end_period,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Four Factors box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_four_factors_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_four_factors_logic(
            game_id,
            start_period=start_period,
            end_period=end_period
        )

@tool
def get_boxscore_usage(
    game_id: str,
    as_dataframe: bool = False
) -> str:
    """
    Fetches box score usage statistics (BoxScoreUsageV3) for a game.

    Args:
        game_id (str): The ID of the game.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with usage statistics for players and teams. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_usage' called for game_id '{game_id}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_usage_logic(
            game_id,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Usage box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_usage_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_usage_logic(game_id)

@tool
def get_boxscore_defensive(
    game_id: str,
    as_dataframe: bool = False
) -> str:
    """
    Fetches box score defensive statistics (BoxScoreDefensiveV2) for a game.

    Args:
        game_id (str): The ID of the game.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with defensive statistics for players and teams. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_defensive' called for game_id '{game_id}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_defensive_logic(
            game_id,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Defensive box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_defensive_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_defensive_logic(game_id)

@tool
def get_boxscore_summary(
    game_id: str,
    as_dataframe: bool = False
) -> str:
    """
    Fetches a comprehensive summary of a game (BoxScoreSummaryV2), including line scores,
    officials, inactive players, etc.

    Args:
        game_id (str): The ID of the game.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with game summary datasets. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_boxscore_summary' called for game_id '{game_id}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_boxscore_summary_logic(
            game_id,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Summary box score data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": get_relative_cache_path(f"{game_id}_summary_{key}.csv", "boxscores"),
                    "sample_data": df.head(3).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_boxscore_summary_logic(game_id)

@tool
def get_win_probability(
    game_id: str,
    run_type: str = RunType.default,
    as_dataframe: bool = False
) -> str:
    """
    Fetches win probability data throughout a specific game (WinProbabilityPBP).
    Provides DataFrame output capabilities.

    Args:
        game_id (str): The ID of the game.
        run_type (str, optional): Type of run for win probability.
            Valid values from `nba_api.stats.library.parameters.RunType`. Defaults to "Default".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with win probability data including game info and PBP events.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_win_probability' called for game_id '{game_id}', run_type '{run_type}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_win_probability_logic(
            game_id,
            run_type=run_type,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Win probability data has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Create a descriptive filename
                csv_path = get_relative_cache_path(f"{game_id}_run_{run_type.replace(' ', '_')}_{key}.csv", "win_probability")

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
                    "sample_data": df.head(5).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_win_probability_logic(game_id, run_type=run_type)

@tool
def get_search_games(
    query: str,
    season: str,
    season_type: str = SeasonTypeAllStar.regular,
    limit: int = 10,
    as_dataframe: bool = False
) -> str:
    """
    Searches for games based on a query string (e.g., "Lakers vs Celtics", "Lakers").

    Args:
        query (str): The search query string.
        season (str): The NBA season in YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        limit (int, optional): Maximum number of results to return. Defaults to 10.
        as_dataframe (bool, optional): If True, returns pandas DataFrames. Defaults to False.

    Returns:
        str: JSON string with a list of matching games.
    """
    logger.debug(f"Tool 'get_search_games' called with query: '{query}', season: {season}, season_type: {season_type}, limit: {limit}, as_dataframe={as_dataframe}")
    return search_games_logic(
        query=query,
        season=season,
        season_type=season_type,
        limit=limit,
        return_dataframe=as_dataframe
    )