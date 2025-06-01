"""
Handles fetching and processing game play-by-play (PBP) data.
It attempts to fetch live PBP data first and falls back to historical PBP data (PlayByPlayV3)
if live data is unavailable or if specific period filters are applied.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
import re
import pandas as pd
from functools import lru_cache

from nba_api.stats.endpoints import playbyplayv3
from nba_api.live.nba.endpoints import PlayByPlay as LivePlayByPlay
from config import settings
from core.errors import Errors
from api_tools.utils import (
    _process_dataframe,
    format_response
)
from utils.validation import validate_game_id_format

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
GAME_PBP_CACHE_SIZE = 64
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PBP_CSV_DIR = os.path.join(CSV_CACHE_DIR, "playbyplay")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PBP_CSV_DIR, exist_ok=True)

# --- Helper Functions ---
# Note: Previous helper functions like _get_event_type and _determine_team_from_tricode
# were removed as PlayByPlayV3 provides richer data directly (actionType, subType, teamTricode).

def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)

def _get_csv_path_for_playbyplay(game_id: str, source: str, start_period: int = 0, end_period: int = 0) -> str:
    """
    Generates a file path for saving a play-by-play DataFrame as CSV.

    Args:
        game_id: The game ID
        source: The source of the data ('live' or 'historical_v3')
        start_period: Starting period filter
        end_period: Ending period filter

    Returns:
        Path to the CSV file
    """
    # Create a string with the period filters
    period_str = ""
    if start_period > 0 or end_period > 0:
        period_str = f"_periods_{start_period}_{end_period}"

    filename = f"{game_id}_{source}{period_str}.csv"
    return os.path.join(PBP_CSV_DIR, filename)

def _filter_plays_by_event_type(plays_df: pd.DataFrame, event_types: List[str] = None) -> pd.DataFrame:
    """
    Filters plays by event type.

    Args:
        plays_df: DataFrame containing play-by-play data
        event_types: List of event types to include (e.g., ['SHOT', 'REBOUND', 'TURNOVER'])
                    If None, all plays are returned

    Returns:
        Filtered DataFrame
    """
    if event_types is None or len(event_types) == 0 or plays_df.empty:
        return plays_df

    # Convert event types to uppercase for case-insensitive matching
    event_types = [et.upper() for et in event_types]

    # Check if actionType column exists (for V3 data)
    if 'actionType' in plays_df.columns:
        return plays_df[plays_df['actionType'].str.upper().isin(event_types)]

    # For live data, check the description for event types
    filtered_df = pd.DataFrame()
    for event_type in event_types:
        event_matches = plays_df[plays_df['description'].str.contains(event_type, case=False, na=False)]
        filtered_df = pd.concat([filtered_df, event_matches])

    return filtered_df.drop_duplicates().reset_index(drop=True)

def _filter_plays_by_player(plays_df: pd.DataFrame, player_name: str = None, person_id: int = None) -> pd.DataFrame:
    """
    Filters plays by player name or ID.

    Args:
        plays_df: DataFrame containing play-by-play data
        player_name: Player name to filter by
        person_id: Player ID to filter by

    Returns:
        Filtered DataFrame
    """
    if (player_name is None and person_id is None) or plays_df.empty:
        return plays_df

    filtered_df = plays_df.copy()

    # Filter by player ID if provided
    if person_id is not None:
        if 'personId' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['personId'] == person_id]
        else:
            # If personId column doesn't exist, return empty DataFrame
            return pd.DataFrame(columns=filtered_df.columns)

    # Filter by player name if provided
    if player_name is not None:
        player_name = player_name.lower()

        # Check for playerName or playerNameI columns
        if 'playerName' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['playerName'].str.lower().str.contains(player_name, na=False)]
        elif 'playerNameI' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['playerNameI'].str.lower().str.contains(player_name, na=False)]
        else:
            # If neither column exists, check description
            filtered_df = filtered_df[filtered_df['description'].str.lower().str.contains(player_name, na=False)]

    return filtered_df.reset_index(drop=True)

def _filter_plays_by_team(plays_df: pd.DataFrame, team_id: int = None, team_tricode: str = None) -> pd.DataFrame:
    """
    Filters plays by team ID or tricode.

    Args:
        plays_df: DataFrame containing play-by-play data
        team_id: Team ID to filter by
        team_tricode: Team tricode to filter by (e.g., 'LAL', 'BOS')

    Returns:
        Filtered DataFrame
    """
    if (team_id is None and team_tricode is None) or plays_df.empty:
        return plays_df

    filtered_df = plays_df.copy()

    # Filter by team ID if provided
    if team_id is not None:
        if 'teamId' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['teamId'] == team_id]
        else:
            # If teamId column doesn't exist, return empty DataFrame
            return pd.DataFrame(columns=filtered_df.columns)

    # Filter by team tricode if provided
    if team_tricode is not None:
        team_tricode = team_tricode.upper()

        if 'teamTricode' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['teamTricode'] == team_tricode]
        else:
            # If teamTricode column doesn't exist, check description
            filtered_df = filtered_df[filtered_df['description'].str.upper().str.contains(team_tricode, na=False)]

    return filtered_df.reset_index(drop=True)

def _format_historical_pbp_dataframe(pbp_df: pd.DataFrame) -> pd.DataFrame:
    """
    Formats the historical play-by-play DataFrame for better usability.

    Args:
        pbp_df: Raw DataFrame from PlayByPlayV3

    Returns:
        Formatted DataFrame with standardized column names and values
    """
    if pbp_df.empty:
        return pbp_df

    # Create a copy to avoid modifying the original
    formatted_df = pbp_df.copy()

    # Format the clock column (e.g., PT11M58.00S to 11:58)
    if 'clock' in formatted_df.columns:
        formatted_df['clock'] = formatted_df['clock'].apply(
            lambda x: str(x).replace("PT", "").replace("M", ":").replace("S", "").split(".")[0] if pd.notna(x) else ""
        )

    # Create a score column combining home and away scores
    if 'scoreHome' in formatted_df.columns and 'scoreAway' in formatted_df.columns:
        formatted_df['score'] = formatted_df.apply(
            lambda row: f"{row['scoreHome']}-{row['scoreAway']}"
            if pd.notna(row['scoreHome']) and pd.notna(row['scoreAway']) else None,
            axis=1
        )

    # Create a standardized event_type column
    if 'actionType' in formatted_df.columns and 'subType' in formatted_df.columns:
        formatted_df['event_type'] = formatted_df.apply(
            lambda row: f"{str(row['actionType']).upper()}_{str(row['subType']).upper()}"
            if pd.notna(row['actionType']) else "",
            axis=1
        )

    return formatted_df

def _format_live_pbp_dataframe(live_data_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Converts live play-by-play data dictionary to a DataFrame and formats it.

    Args:
        live_data_dict: Dictionary from LivePlayByPlay endpoint

    Returns:
        Formatted DataFrame with standardized columns
    """
    raw_actions_list = live_data_dict.get('game', {}).get('actions', [])

    if not raw_actions_list:
        return pd.DataFrame()

    # Convert list of dictionaries to DataFrame
    df = pd.DataFrame(raw_actions_list)

    if df.empty:
        return df

    # Get team information for mapping team IDs to home/away
    game_details_dict = live_data_dict.get('game', {})
    home_team_id_live = game_details_dict.get('homeTeam', {}).get('teamId')
    away_team_id_live = game_details_dict.get('awayTeam', {}).get('teamId')

    # Add team information
    if 'teamId' in df.columns:
        df['team'] = df['teamId'].apply(
            lambda x: "home" if x == home_team_id_live else
                     "away" if x == away_team_id_live else "neutral"
        )

    # Format the clock column
    if 'clock' in df.columns:
        df['clock'] = df['clock'].apply(
            lambda x: re.match(r"PT(\d+)M(\d+\.?\d*)S", str(x)).group(1) + ":" +
                     re.match(r"PT(\d+)M(\d+\.?\d*)S", str(x)).group(2).split('.')[0].zfill(2)
                     if re.match(r"PT(\d+)M(\d+\.?\d*)S", str(x)) else x
        )

    # Create a score column
    if 'scoreHome' in df.columns and 'scoreAway' in df.columns:
        df['score'] = df.apply(
            lambda row: f"{row['scoreHome']}-{row['scoreAway']}"
            if pd.notna(row['scoreHome']) and pd.notna(row['scoreAway']) else None,
            axis=1
        )

    # Create a standardized event_type column
    if 'actionType' in df.columns and 'subType' in df.columns:
        df['event_type'] = df.apply(
            lambda row: f"{str(row['actionType']).upper()}_{str(row['subType']).upper()}"
            if pd.notna(row['actionType']) else "",
            axis=1
        )

    return df

# --- Play-by-Play Logic Functions ---

def _fetch_historical_playbyplay_logic(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    event_types: List[str] = None,
    player_name: str = None,
    person_id: int = None,
    team_id: int = None,
    team_tricode: str = None,
    return_dataframe: bool = False
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Fetches historical play-by-play data using PlayByPlayV3.

    Args:
        game_id: The ID of the game.
        start_period: The starting period to fetch. Defaults to 0 (all).
        end_period: The ending period to fetch. Defaults to 0 (all).
        event_types: List of event types to filter by (e.g., ['SHOT', 'REBOUND', 'TURNOVER']).
        player_name: Filter plays by player name.
        person_id: Filter plays by player ID.
        team_id: Filter plays by team ID.
        team_tricode: Filter plays by team tricode (e.g., 'LAL', 'BOS').
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            Dict[str, Any]: A dictionary containing formatted PBP data.
                            Includes 'periods' list, 'has_video' flag, and 'source'.
        If return_dataframe=True:
            Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]: A tuple containing the formatted PBP data
                                                           and a dictionary of DataFrames.

    Raises:
        ValueError: If DataFrame processing fails for non-empty data.
        Exception: For NBA API call failures.
    """
    logger.info(f"Executing _fetch_historical_playbyplay_logic (V3) for game ID: {game_id}, periods {start_period}-{end_period}, return_dataframe={return_dataframe}")

    # Fetch data from the API
    pbp_endpoint = playbyplayv3.PlayByPlayV3(
        game_id=game_id, start_period=start_period, end_period=end_period, timeout=settings.DEFAULT_TIMEOUT_SECONDS
    )

    # Get DataFrames
    pbp_df = pbp_endpoint.play_by_play.get_data_frame()  # V3 uses camelCase
    video_df = pbp_endpoint.available_video.get_data_frame()  # V3 uses camelCase 'videoAvailable'

    # Format the DataFrame for better usability
    formatted_pbp_df = _format_historical_pbp_dataframe(pbp_df)

    # Apply filters if provided
    if event_types:
        formatted_pbp_df = _filter_plays_by_event_type(formatted_pbp_df, event_types)

    if player_name or person_id:
        formatted_pbp_df = _filter_plays_by_player(formatted_pbp_df, player_name, person_id)

    if team_id or team_tricode:
        formatted_pbp_df = _filter_plays_by_team(formatted_pbp_df, team_id, team_tricode)

    # Save to CSV if returning DataFrame
    if return_dataframe:
        csv_path = _get_csv_path_for_playbyplay(game_id, "historical_v3", start_period, end_period)
        _save_dataframe_to_csv(formatted_pbp_df, csv_path)

    # Process the DataFrame for JSON response
    processed_plays = _process_dataframe(pbp_df, single_row=False)
    if processed_plays is None:
        if pbp_df.empty:
            logger.warning(f"No historical PBP data found for game {game_id} via API (V3).")
            processed_plays = []
        else:
            raise ValueError(f"Failed to process non-empty historical PBP (V3) DataFrame for game {game_id}")

    # Organize plays by period
    periods_data = {}
    for play_item in processed_plays:  # play_item keys are now camelCase
        period_num = play_item.get("period", 0)
        if period_num not in periods_data:
            periods_data[period_num] = []

        # V3 provides scoreHome and scoreAway
        score_home_v3 = play_item.get('scoreHome')
        score_away_v3 = play_item.get('scoreAway')
        score_str_v3 = f"{score_home_v3}-{score_away_v3}" if score_home_v3 is not None and score_away_v3 is not None else None

        # Format the play data
        formatted_play = {
            "event_num": play_item.get("actionNumber"),
            "clock": play_item.get("clock", "").replace("PT", "").replace("M", ":").replace("S", "").split(".")[0],  # Format PT11M58.00S to 11:58
            "score": score_str_v3,
            "team_tricode": play_item.get("teamTricode"),  # Team performing action
            "person_id": play_item.get("personId"),
            "player_name": play_item.get("playerNameI"),  # Or playerName
            "description": play_item.get("description"),  # Main description
            "action_type": play_item.get("actionType"),
            "sub_type": play_item.get("subType"),
            "event_type": f"{play_item.get('actionType', '').upper()}_{play_item.get('subType', '').upper()}",
            "video_available": play_item.get("videoAvailable", False)  # V3 has this per play
        }

        # Add to the appropriate period
        periods_data[period_num].append(formatted_play)

    # Create the final periods list
    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]

    # Check if video is available
    has_overall_video = bool(video_df.iloc[0]['videoAvailable'] == 1) if not video_df.empty and 'videoAvailable' in video_df.columns else False

    # Create the result dictionary
    result_dict = {
        "game_id": game_id,
        "has_video": has_overall_video,
        "source": "historical_v3",
        "filtered_periods": {"start": start_period, "end": end_period} if start_period > 0 or end_period > 0 else None,
        "periods": periods_list_final
    }

    # Add filter information if any filters were applied
    filters_applied = {}
    if event_types:
        filters_applied["event_types"] = event_types
    if player_name:
        filters_applied["player_name"] = player_name
    if person_id:
        filters_applied["person_id"] = person_id
    if team_id:
        filters_applied["team_id"] = team_id
    if team_tricode:
        filters_applied["team_tricode"] = team_tricode

    if filters_applied:
        result_dict["filters_applied"] = filters_applied

    # Return the appropriate result based on return_dataframe
    if return_dataframe:
        dataframes = {
            "play_by_play": formatted_pbp_df,
            "available_video": video_df
        }
        return result_dict, dataframes

    return result_dict

def _fetch_live_playbyplay_logic(
    game_id: str,
    event_types: List[str] = None,
    player_name: str = None,
    person_id: int = None,
    team_id: int = None,
    team_tricode: str = None,
    return_dataframe: bool = False
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]]:
    """
    Fetches live play-by-play data.

    Args:
        game_id: The ID of the game.
        event_types: List of event types to filter by (e.g., ['SHOT', 'REBOUND', 'TURNOVER']).
        player_name: Filter plays by player name.
        person_id: Filter plays by player ID.
        team_id: Filter plays by team ID.
        team_tricode: Filter plays by team tricode (e.g., 'LAL', 'BOS').
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            Dict[str, Any]: A dictionary containing formatted live PBP data.
                            Includes 'periods' list and 'source'. 'has_video' is False for live.
        If return_dataframe=True:
            Tuple[Dict[str, Any], Dict[str, pd.DataFrame]]: A tuple containing the formatted live PBP data
                                                           and a dictionary of DataFrames.

    Raises:
        ValueError: If no live actions are found (game not live or recently concluded).
        Exception: For NBA API call failures or unexpected data structure.
    """
    logger.info(f"Executing _fetch_live_playbyplay_logic for game ID: {game_id}, return_dataframe={return_dataframe}")

    # Fetch data from the API
    live_pbp_endpoint = LivePlayByPlay(game_id=game_id)
    live_data_dict = live_pbp_endpoint.get_dict()
    raw_actions_list = live_data_dict.get('game', {}).get('actions', [])

    if not raw_actions_list:
        logger.warning(f"No live actions found for game {game_id}. Game might not be live or recently concluded.")
        raise ValueError("No live actions found, game may not be live.")

    # Convert to DataFrame and format
    formatted_pbp_df = _format_live_pbp_dataframe(live_data_dict)

    # Apply filters if provided
    if event_types:
        formatted_pbp_df = _filter_plays_by_event_type(formatted_pbp_df, event_types)

    if player_name or person_id:
        formatted_pbp_df = _filter_plays_by_player(formatted_pbp_df, player_name, person_id)

    if team_id or team_tricode:
        formatted_pbp_df = _filter_plays_by_team(formatted_pbp_df, team_id, team_tricode)

    # Save to CSV if returning DataFrame
    if return_dataframe:
        csv_path = _get_csv_path_for_playbyplay(game_id, "live")
        _save_dataframe_to_csv(formatted_pbp_df, csv_path)

    # Process for JSON response
    periods_data = {}
    game_details_dict = live_data_dict.get('game', {})
    home_team_id_live = game_details_dict.get('homeTeam', {}).get('teamId')
    away_team_id_live = game_details_dict.get('awayTeam', {}).get('teamId')

    # Use the filtered DataFrame if filters were applied
    actions_to_process = formatted_pbp_df.to_dict('records') if not formatted_pbp_df.empty else raw_actions_list

    for action_item in actions_to_process:
        period_num = action_item.get("period", 0)
        if period_num not in periods_data:
            periods_data[period_num] = []

        # Format clock string
        clock_raw_str = action_item.get("clock", "")
        match_obj = re.match(r"PT(\d+)M(\d+\.?\d*)S", str(clock_raw_str))
        clock_formatted_str = f"{match_obj.group(1)}:{match_obj.group(2).split('.')[0].zfill(2)}" if match_obj else clock_raw_str

        # Format score string
        score_home = action_item.get('scoreHome')
        score_away = action_item.get('scoreAway')
        score_str_live = f"{score_home}-{score_away}" if score_home is not None and score_away is not None else None

        # Determine team (home/away/neutral)
        action_team_id_live = action_item.get('teamId')
        team_str_live = "home" if action_team_id_live == home_team_id_live else "away" if action_team_id_live == away_team_id_live else "neutral"

        # Create formatted play dictionary
        formatted_play = {
            "event_num": action_item.get("actionNumber"),
            "clock": clock_formatted_str,
            "score": score_str_live,
            "team": team_str_live,  # home, away, or neutral
            "team_tricode": action_item.get("teamTricode"),
            "description": action_item.get("description"),
            "person_id": action_item.get("personId"),
            "player_name": action_item.get("playerNameI") or action_item.get("playerName"),  # Prefer playerNameI if available
            "action_type": action_item.get("actionType"),
            "sub_type": action_item.get("subType"),
            "event_type": f"{str(action_item.get('actionType', '')).upper()}_{str(action_item.get('subType', '')).upper()}"
        }

        # Add to the appropriate period
        periods_data[period_num].append(formatted_play)

    # Create the final periods list
    periods_list_final = [{"period": p_num, "plays": plays_list} for p_num, plays_list in sorted(periods_data.items())]

    # Create the result dictionary
    result_dict = {
        "game_id": game_id,
        "has_video": False,
        "source": "live",
        "filtered_periods": None,
        "periods": periods_list_final
    }

    # Add filter information if any filters were applied
    filters_applied = {}
    if event_types:
        filters_applied["event_types"] = event_types
    if player_name:
        filters_applied["player_name"] = player_name
    if person_id:
        filters_applied["person_id"] = person_id
    if team_id:
        filters_applied["team_id"] = team_id
    if team_tricode:
        filters_applied["team_tricode"] = team_tricode

    if filters_applied:
        result_dict["filters_applied"] = filters_applied

    # Return the appropriate result based on return_dataframe
    if return_dataframe:
        dataframes = {
            "play_by_play": formatted_pbp_df
        }
        return result_dict, dataframes

    return result_dict

# --- Main Public Function ---
def fetch_playbyplay_logic(
    game_id: str,
    start_period: int = 0,
    end_period: int = 0,
    event_types: List[str] = None,
    player_name: str = None,
    person_id: int = None,
    team_id: int = None,
    team_tricode: str = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches play-by-play data for a game. Attempts live data first if no period filters
    are applied, otherwise falls back to or directly uses historical data (PlayByPlayV3).

    Provides granular filtering options and DataFrame output capabilities.

    Args:
        game_id: The ID of the game.
        start_period: The starting period filter. Defaults to 0 (no filter).
        end_period: The ending period filter. Defaults to 0 (no filter).
        event_types: List of event types to filter by (e.g., ['SHOT', 'REBOUND', 'TURNOVER']).
                    Common event types include: 'SHOT', 'REBOUND', 'TURNOVER', 'FOUL', 'FREE_THROW',
                    'SUBSTITUTION', 'TIMEOUT', 'JUMP_BALL', 'BLOCK', 'STEAL', 'VIOLATION'.
        player_name: Filter plays by player name.
        person_id: Filter plays by player ID.
        team_id: Filter plays by team ID.
        team_tricode: Filter plays by team tricode (e.g., 'LAL', 'BOS').
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the play-by-play data or an error message.
                 The response includes a 'source' field ("live" or "historical_v3")
                 and a 'periods' list, each containing plays for that period.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_playbyplay_logic for game ID: {game_id}, StartPeriod: {start_period}, EndPeriod: {end_period}, return_dataframe: {return_dataframe}")

    # Validate input parameters
    if not game_id:
        error_response = format_response(error=Errors.GAME_ID_EMPTY)
        if return_dataframe:
            return error_response, {}
        return error_response

    if not validate_game_id_format(game_id):
        error_response = format_response(error=Errors.INVALID_GAME_ID_FORMAT.format(game_id=game_id))
        if return_dataframe:
            return error_response, {}
        return error_response

    # If specific periods are requested, directly fetch historical data as live PBP typically doesn't support period filtering.
    if start_period != 0 or end_period != 0:
        logger.info(f"Period filters active ({start_period}-{end_period}), fetching historical PBP directly for game {game_id}.")
        try:
            # Call the historical PBP logic with all parameters
            result = _fetch_historical_playbyplay_logic(
                game_id,
                start_period,
                end_period,
                event_types,
                player_name,
                person_id,
                team_id,
                team_tricode,
                return_dataframe
            )

            # Handle the result based on return_dataframe
            if return_dataframe:
                result_dict, dataframes = result
                result_dict["parameters"] = {
                    "start_period": start_period,
                    "end_period": end_period,
                    "note": "Filtered historical data with DataFrame output."
                }
                json_response = format_response(data=result_dict)
                return json_response, dataframes
            else:
                result_dict = result
                result_dict["parameters"] = {
                    "start_period": start_period,
                    "end_period": end_period,
                    "note": "Filtered historical data."
                }
                return format_response(data=result_dict)

        except Exception as hist_fetch_error:
            logger.error(f"Historical PBP fetch failed for game {game_id} (with period filters): {hist_fetch_error}", exc_info=True)
            error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(hist_fetch_error))
            error_response = format_response(error=error_msg)

            if return_dataframe:
                return error_response, {}
            return error_response
    else:
        # No period filters, attempt live PBP first, then fallback to historical.
        try:
            logger.debug(f"Attempting live PBP fetch for game {game_id} (no period filters).")

            # Call the live PBP logic with all parameters
            result = _fetch_live_playbyplay_logic(
                game_id,
                event_types,
                player_name,
                person_id,
                team_id,
                team_tricode,
                return_dataframe
            )

            # Handle the result based on return_dataframe
            if return_dataframe:
                result_dict, dataframes = result
                result_dict["parameters"] = {
                    "start_period": 0,
                    "end_period": 0,
                    "note": "Live data with DataFrame output; period filters not applied."
                }
                json_response = format_response(data=result_dict)
                return json_response, dataframes
            else:
                result_dict = result
                result_dict["parameters"] = {
                    "start_period": 0,
                    "end_period": 0,
                    "note": "Live data; period filters not applied."
                }
                return format_response(data=result_dict)

        except ValueError as live_fetch_error:  # Raised by _fetch_live_playbyplay_logic if no live actions
            logger.warning(f"Live PBP fetch failed for game {game_id} ({live_fetch_error}), attempting historical (no period filters).")
            try:
                # Call the historical PBP logic with all parameters
                result = _fetch_historical_playbyplay_logic(
                    game_id,
                    0,
                    0,
                    event_types,
                    player_name,
                    person_id,
                    team_id,
                    team_tricode,
                    return_dataframe
                )

                # Handle the result based on return_dataframe
                if return_dataframe:
                    result_dict, dataframes = result
                    result_dict["parameters"] = {
                        "start_period": 0,
                        "end_period": 0,
                        "note": "Full historical data with DataFrame output after live fallback."
                    }
                    json_response = format_response(data=result_dict)
                    return json_response, dataframes
                else:
                    result_dict = result
                    result_dict["parameters"] = {
                        "start_period": 0,
                        "end_period": 0,
                        "note": "Full historical data after live fallback."
                    }
                    return format_response(data=result_dict)

            except Exception as hist_fetch_error:
                logger.error(f"Historical PBP fetch (fallback) also failed for game {game_id}: {hist_fetch_error}", exc_info=True)
                error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(hist_fetch_error))
                error_response = format_response(error=error_msg)

                if return_dataframe:
                    return error_response, {}
                return error_response

        except Exception as e:  # Catch other unexpected errors during the live attempt phase
            logger.error(f"Unexpected error during initial live PBP fetch attempt for game {game_id}: {e}", exc_info=True)
            error_msg = Errors.PLAYBYPLAY_API.format(game_id=game_id, error=str(e))
            error_response = format_response(error=error_msg)

            if return_dataframe:
                return error_response, {}
            return error_response