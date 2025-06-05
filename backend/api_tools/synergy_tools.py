"""
Handles fetching and processing Synergy Sports play type statistics.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import os
from typing import Optional, Dict, Any, Tuple, Type, List, Set, Union
from datetime import datetime
import pandas as pd

from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
from nba_api.stats.library.parameters import (
    LeagueID,
    PerModeSimple,
    PlayerOrTeamAbbreviation,
    SeasonTypeAllStar
)
from config import settings
from core.errors import Errors
from api_tools.utils import format_response, _process_dataframe
from utils.validation import _validate_season_format
from utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Module-Level Constants ---
SYNERGY_DATA_CACHE_SIZE = 128
CACHE_TTL_SECONDS_SYNERGY = 3600 * 4  # 4 hours

# --- Cache Directory Setup ---
SYNERGY_CSV_DIR = get_cache_dir("synergy")

def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file, creating the directory if it doesn't exist.

    Args:
        df: The DataFrame to save
        file_path: The path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV
        df.to_csv(file_path, index=False)
        logger.debug(f"Saved DataFrame to {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)

def _get_csv_path_for_synergy(
    play_type: str,
    type_grouping: Optional[str],
    player_or_team: str,
    season: str,
    season_type: str
) -> str:
    """
    Generates a file path for saving synergy data as CSV.

    Args:
        play_type: The play type (e.g., 'Isolation', 'PostUp')
        type_grouping: The type grouping ('offensive' or 'defensive')
        player_or_team: Whether the data is for players or teams ('P' or 'T')
        season: The season in YYYY-YY format
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')

    Returns:
        Path to the CSV file
    """
    # Clean values for filename
    clean_play_type = play_type.replace(" ", "_").lower()
    clean_type_grouping = type_grouping.replace(" ", "_").lower() if type_grouping else "all"
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"synergy_{clean_play_type}_{clean_type_grouping}_{player_or_team}_{season}_{clean_season_type}.csv"
    return get_cache_file_path(filename, "synergy")

VALID_PLAY_TYPES: Set[str] = {
    "Cut", "Handoff", "Isolation", "Misc", "OffScreen", "Postup",
    "PRBallHandler", "PRRollMan", "OffRebound", "Spotup", "Transition"
}
VALID_TYPE_GROUPINGS: Set[str] = {"offensive", "defensive"}

# Validation sets for API parameters, constructed once
_SYNERGY_VALID_PLAYER_TEAM_ABBR: Set[str] = {getattr(PlayerOrTeamAbbreviation, attr) for attr in dir(PlayerOrTeamAbbreviation) if not attr.startswith('_') and isinstance(getattr(PlayerOrTeamAbbreviation, attr), str)}
_SYNERGY_VALID_LEAGUE_IDS: Set[str] = {getattr(LeagueID, attr) for attr in dir(LeagueID) if not attr.startswith('_') and isinstance(getattr(LeagueID, attr), str)}
_SYNERGY_VALID_PER_MODES: Set[str] = {getattr(PerModeSimple, attr) for attr in dir(PerModeSimple) if not attr.startswith('_') and isinstance(getattr(PerModeSimple, attr), str)}
_SYNERGY_VALID_SEASON_TYPES: Set[str] = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}

# --- Helper Functions ---
def get_cached_synergy_data(
    timestamp_bucket: str,
    endpoint_class: Type[SynergyPlayTypes],
    api_kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """Wrapper for the SynergyPlayTypes NBA API endpoint."""
    logger.info(f"Fetching Synergy data (ts: {timestamp_bucket}). Params: {api_kwargs}")
    try:
        synergy_stats_endpoint = endpoint_class(**api_kwargs, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        return synergy_stats_endpoint.get_dict()
    except Exception as e:
        logger.error(f"{endpoint_class.__name__} API call failed: {e}", exc_info=True)
        raise

def _validate_synergy_params(
    season: str, play_type_nullable: Optional[str], type_grouping_nullable: Optional[str],
    player_or_team: str, league_id: str, per_mode: str, season_type: str
) -> Optional[str]:
    """Validates parameters for fetch_synergy_play_types_logic."""
    if not _validate_season_format(season):
        return Errors.INVALID_SEASON_FORMAT.format(season=season)
    if play_type_nullable is None: # This is a required field for the API to return meaningful data
        return Errors.SYNERGY_PLAY_TYPE_REQUIRED.format(options=", ".join(VALID_PLAY_TYPES))
    if play_type_nullable not in VALID_PLAY_TYPES:
        return Errors.INVALID_PLAY_TYPE.format(play_type=play_type_nullable, options=", ".join(VALID_PLAY_TYPES))
    if type_grouping_nullable is not None and type_grouping_nullable not in VALID_TYPE_GROUPINGS:
        return Errors.INVALID_TYPE_GROUPING.format(type_grouping=type_grouping_nullable, options=", ".join(VALID_TYPE_GROUPINGS))
    if player_or_team not in _SYNERGY_VALID_PLAYER_TEAM_ABBR:
        return Errors.INVALID_PLAYER_OR_TEAM_ABBREVIATION.format(value=player_or_team, valid_values=", ".join(_SYNERGY_VALID_PLAYER_TEAM_ABBR))
    if league_id not in _SYNERGY_VALID_LEAGUE_IDS:
        return Errors.INVALID_LEAGUE_ID.format(value=league_id, options=", ".join(list(_SYNERGY_VALID_LEAGUE_IDS)[:5])) # Show some options
    if per_mode not in _SYNERGY_VALID_PER_MODES:
        return Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(_SYNERGY_VALID_PER_MODES)[:5]))
    if season_type not in _SYNERGY_VALID_SEASON_TYPES:
        return Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(_SYNERGY_VALID_SEASON_TYPES)[:5]))
    return None

def _extract_synergy_dataframe(response_dict: Dict[str, Any], api_params_logging: Dict[str, Any]) -> pd.DataFrame:
    """Extracts the SynergyPlayType DataFrame from the raw API response."""
    result_set_data = None
    if 'resultSets' in response_dict and isinstance(response_dict['resultSets'], list):
        for rs_item in response_dict['resultSets']:
            if isinstance(rs_item, dict) and rs_item.get('name') == 'SynergyPlayType':
                result_set_data = rs_item
                break
        # Fallback: if not found by name and only one result set exists, assume it's the one.
        if not result_set_data and len(response_dict['resultSets']) == 1 and isinstance(response_dict['resultSets'][0], dict):
            logger.warning(f"SynergyPlayType dataset not found by name, using first available result set for params: {api_params_logging}")
            result_set_data = response_dict['resultSets'][0]

    if not result_set_data or 'headers' not in result_set_data or 'rowSet' not in result_set_data:
        logger.warning(f"Could not find expected 'SynergyPlayType' data structure in API response for params: {api_params_logging}. Response (first 500 chars): {str(response_dict)[:500]}")
        return pd.DataFrame() # Return empty DataFrame

    return pd.DataFrame(result_set_data['rowSet'], columns=result_set_data['headers'])

def _apply_synergy_id_filters(
    data_list: List[Dict[str, Any]],
    player_or_team: str,
    player_id: Optional[int],
    team_id: Optional[int]
) -> List[Dict[str, Any]]:
    """Applies post-fetch filtering by player_id or team_id if provided."""
    if not data_list:
        return []

    filtered_list = data_list
    if player_id is not None and player_or_team == PlayerOrTeamAbbreviation.player:
        filtered_list = [entry for entry in data_list if entry.get("PLAYER_ID") == player_id]
        if not filtered_list: logger.warning(f"No Synergy data after filtering for player_id: {player_id}")
    elif team_id is not None and player_or_team == PlayerOrTeamAbbreviation.team:
        filtered_list = [entry for entry in data_list if entry.get("TEAM_ID") == team_id]
        if not filtered_list: logger.warning(f"No Synergy data after filtering for team_id: {team_id}")
    return filtered_list

# --- Main Logic Function ---
def fetch_synergy_play_types_logic(
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    player_or_team: str = PlayerOrTeamAbbreviation.team,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = settings.CURRENT_NBA_SEASON,
    play_type_nullable: Optional[str] = None, # Made explicit that it can be None, but validation enforces it
    type_grouping_nullable: Optional[str] = None,
    player_id_nullable: Optional[int] = None, # For post-fetch filtering
    team_id_nullable: Optional[int] = None,   # For post-fetch filtering
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches Synergy Sports play type statistics.
    Provides DataFrame output capabilities.

    A specific `play_type_nullable` is REQUIRED for meaningful data.
    `type_grouping_nullable` ("offensive" or "defensive") is also highly recommended.
    Optional `player_id_nullable` or `team_id_nullable` can be used for post-fetch filtering.

    Args:
        league_id: The league ID. Valid values from `LeagueID` (e.g., "00" for NBA).
        per_mode: Statistical mode. Valid values from `PerModeSimple` (e.g., "PerGame").
        player_or_team: Whether to fetch player or team data. Valid values from `PlayerOrTeamAbbreviation`.
        season_type: The season type. Valid values from `SeasonTypeAllStar`.
        season: The season in YYYY-YY format.
        play_type_nullable: The play type to fetch. REQUIRED for meaningful data.
        type_grouping_nullable: The type grouping ("offensive" or "defensive").
        player_id_nullable: Player ID for post-fetch filtering.
        team_id_nullable: Team ID for post-fetch filtering.
        bypass_cache: If True, ignores cached data and fetches fresh data.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string containing synergy play type statistics.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_synergy_play_types_logic for S: {season}, P/T: {player_or_team}, PlayType: {play_type_nullable}, Grouping: {type_grouping_nullable}, PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}, DataFrame: {return_dataframe}")

    # Initialize dataframes dictionary if returning DataFrames
    dataframes = {}

    validation_error = _validate_synergy_params(
        season, play_type_nullable, type_grouping_nullable, player_or_team,
        league_id, per_mode, season_type
    )
    if validation_error:
        error_response = format_response(error=validation_error)
        if return_dataframe:
            return error_response, dataframes
        return error_response

    # API parameters do not include player_id_nullable or team_id_nullable directly for SynergyPlayTypes
    # These are used for post-filtering if player_or_team is general ('P' or 'T')
    api_params_for_call = {
        "league_id": league_id,
        "per_mode_simple": per_mode,
        "player_or_team_abbreviation": player_or_team,
        "season_type_all_star": season_type,
        "season": season,
        "play_type_nullable": play_type_nullable,
        "type_grouping_nullable": type_grouping_nullable
    }
    # Create a timestamp bucket for logging
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS_SYNERGY))

    try:
        response_dict: Dict[str, Any]
        if bypass_cache:
            logger.info(f"Bypassing cache, fetching fresh Synergy data with params: {api_params_for_call} and custom headers.")
            synergy_endpoint = SynergyPlayTypes(**api_params_for_call, timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            response_dict = synergy_endpoint.get_dict()
        else:
            # For cached data, we don't need to pass headers again as the request was already made
            response_dict = get_cached_synergy_data(
                timestamp_bucket=timestamp_bucket,
                endpoint_class=SynergyPlayTypes, api_kwargs=api_params_for_call
            )
    except KeyError as ke: # Handles cases where API response might be malformed
        logger.warning(f"KeyError ('{str(ke)}') fetching Synergy data, params: {api_params_for_call}. Returning empty with message.")
        response_data = {
            "parameters": {**api_params_for_call, "player_id_nullable": player_id_nullable, "team_id_nullable": team_id_nullable},
            "synergy_stats": [],
            "message": f"Could not retrieve Synergy data due to API response format issue (KeyError: {str(ke)})."
        }
        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)
    except Exception as e:
        logger.error(f"Error fetching Synergy play types (pre-df): {e}", exc_info=True)
        error_response = format_response(error=Errors.SYNERGY_UNEXPECTED.format(error=str(e)))
        if return_dataframe:
            return error_response, dataframes
        return error_response

    try:
        synergy_df = _extract_synergy_dataframe(response_dict, api_params_for_call)
        processed_data = _process_dataframe(synergy_df, single_row=False)

        if processed_data is None:
            # _process_dataframe returns None on its internal error, or if df was empty and it decided so.
            # If synergy_df was empty, _extract_synergy_dataframe already logged it.
            if not synergy_df.empty: # Log only if df was not empty but processing failed
                 logger.error(f"DataFrame processing failed for Synergy stats with params: {api_params_for_call}")

            if not synergy_df.empty:
                error_response = format_response(error=Errors.SYNERGY_PROCESSING)
                if return_dataframe:
                    return error_response, dataframes
                return error_response
            else:
                response_data = {
                    "parameters": {**api_params_for_call, "player_id_nullable": player_id_nullable, "team_id_nullable": team_id_nullable},
                    "synergy_stats": [],
                    "message": "No Synergy play type data rows returned by API or processing failed."
                }
                if return_dataframe:
                    return format_response(response_data), dataframes
                return format_response(response_data)

        # Apply post-fetch filtering
        final_data = _apply_synergy_id_filters(processed_data, player_or_team, player_id_nullable, team_id_nullable)

        if not final_data and (player_id_nullable or team_id_nullable):
            # Log if filtering resulted in empty but original data was present
            logger.warning(f"Synergy data became empty after ID filtering. PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}")
            # Return empty stats but include parameters for context
            response_data = {
                "parameters": {**api_params_for_call, "player_id_nullable": player_id_nullable, "team_id_nullable": team_id_nullable},
                "synergy_stats": []
            }
            if return_dataframe:
                return format_response(response_data), dataframes
            return format_response(response_data)

        logger.info(f"Successfully fetched Synergy stats. Found {len(final_data)} entries after all filters.")

        response_data = {
            "parameters": {**api_params_for_call, "player_id_nullable": player_id_nullable, "team_id_nullable": team_id_nullable},
            "synergy_stats": final_data
        }

        # If DataFrame output is requested, save DataFrames and return them
        if return_dataframe:
            # Add synergy stats DataFrame
            synergy_stats_df = pd.DataFrame(final_data) if final_data else pd.DataFrame()
            dataframes["synergy_stats"] = synergy_stats_df

            # Add raw synergy data
            dataframes["raw_synergy_data"] = synergy_df

            # Save DataFrame to CSV if not empty
            if not synergy_stats_df.empty and play_type_nullable:
                csv_path = _get_csv_path_for_synergy(
                    play_type_nullable,
                    type_grouping_nullable,
                    player_or_team,
                    season,
                    season_type
                )
                _save_dataframe_to_csv(synergy_stats_df, csv_path)

                # Add DataFrame metadata to the response
                csv_filename = os.path.basename(csv_path)
                relative_path = get_relative_cache_path(csv_filename, "synergy")

                response_data["dataframe_info"] = {
                    "message": "Synergy play type data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "synergy_stats": {
                            "shape": list(synergy_stats_df.shape),
                            "columns": synergy_stats_df.columns.tolist(),
                            "csv_path": relative_path
                        },
                        "raw_synergy_data": {
                            "shape": list(synergy_df.shape),
                            "columns": synergy_df.columns.tolist()
                        }
                    }
                }

            return format_response(response_data), dataframes

        # Return just the JSON response if DataFrames are not requested
        return format_response(response_data)

    except Exception as e:
        logger.error(f"Error processing Synergy result sets or applying filters: {e}", exc_info=True)
        error_response = format_response(error=Errors.SYNERGY_PROCESSING)
        if return_dataframe:
            return error_response, dataframes
        return error_response
