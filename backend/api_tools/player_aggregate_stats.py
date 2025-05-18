"""
Handles aggregating various player statistics from different sources,
including common info, career stats, game logs for a specific season, and awards.
Provides both JSON and DataFrame outputs with CSV caching.
"""
import logging
import json
import os
from functools import lru_cache
from typing import Optional, Dict, Any, Union, Tuple
import pandas as pd
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings
from backend.core.errors import Errors
from backend.api_tools.utils import (
    format_response,
    find_player_id_or_error,
    PlayerNotFoundError
)
from backend.utils.validation import _validate_season_format
from backend.api_tools.player_common_info import fetch_player_info_logic
from backend.api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from backend.api_tools.player_gamelogs import fetch_player_gamelog_logic

logger = logging.getLogger(__name__)

PLAYER_AGGREGATE_STATS_CACHE_SIZE = 128

# --- Cache Directory Setup ---
CSV_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
PLAYER_STATS_CSV_DIR = os.path.join(CSV_CACHE_DIR, "player_stats")

# Ensure cache directories exist
os.makedirs(CSV_CACHE_DIR, exist_ok=True)
os.makedirs(PLAYER_STATS_CSV_DIR, exist_ok=True)

# --- Helper Functions ---
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

def _get_csv_path_for_player_stats(player_name: str, season: str, season_type: str, data_type: str) -> str:
    """
    Generates a file path for saving a player stats DataFrame as CSV.

    Args:
        player_name: The player's name
        season: The season (YYYY-YY format)
        season_type: The season type (e.g., 'Regular Season', 'Playoffs')
        data_type: The type of data (e.g., 'info', 'career', 'gamelog', 'awards')

    Returns:
        Path to the CSV file
    """
    # Clean player name for filename
    clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

    # Clean season type for filename
    clean_season_type = season_type.replace(" ", "_").lower()

    filename = f"{clean_player_name}_{season}_{clean_season_type}_{data_type}.csv"
    return os.path.join(PLAYER_STATS_CSV_DIR, filename)

def fetch_player_stats_logic(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Aggregates various player statistics including common info, career stats,
    game logs for a specified season, and awards history.

    Provides DataFrame output capabilities.

    Args:
        player_name: The name or ID of the player.
        season: The season for which to fetch game logs (YYYY-YY format).
               Defaults to the current NBA season if None.
        season_type: The type of season for game logs (e.g., "Regular Season").
                    Defaults to "Regular Season".
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: A JSON string containing the aggregated player statistics, or an error message.
                 Successful response structure includes keys like:
                 "player_name", "player_id", "season_requested_for_gamelog",
                 "season_type_requested_for_gamelog", "info", "headline_stats",
                 "available_seasons", "career_stats", "season_gamelog", "awards".
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Executing fetch_player_stats_logic for: '{player_name}', Season for Gamelog: {effective_season}, Type: {season_type}, return_dataframe={return_dataframe}")

    if not _validate_season_format(effective_season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=effective_season)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)

        results_json = {}
        dataframes = {}

        # Define the logic functions to call
        logic_functions_config = {
            "info_and_headlines": (fetch_player_info_logic, [player_actual_name]),
            "career": (fetch_player_career_stats_logic, [player_actual_name]),
            "gamelog_for_season": (fetch_player_gamelog_logic, [player_actual_name, effective_season, season_type]),
            "awards_history": (fetch_player_awards_logic, [player_actual_name])
        }

        # Call each logic function and process the results
        for key, (func, args) in logic_functions_config.items():
            result_str = func(*args)
            try:
                data = json.loads(result_str)
                if "error" in data:
                    logger.error(f"Error from {key} logic for {player_actual_name}: {data['error']}")
                    error_response = result_str
                    if return_dataframe:
                        return error_response, {}
                    return error_response

                results_json[key] = data

                # Convert JSON data to DataFrames
                if return_dataframe:
                    if key == "info_and_headlines":
                        # Convert player info to DataFrame
                        if "player_info" in data:
                            info_df = pd.DataFrame([data["player_info"]])
                            dataframes["player_info"] = info_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "info")
                            _save_dataframe_to_csv(info_df, csv_path)

                        # Convert headline stats to DataFrame
                        if "headline_stats" in data:
                            headline_df = pd.DataFrame([data["headline_stats"]])
                            dataframes["headline_stats"] = headline_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "headline_stats")
                            _save_dataframe_to_csv(headline_df, csv_path)

                        # Convert available seasons to DataFrame
                        if "available_seasons" in data:
                            seasons_df = pd.DataFrame(data["available_seasons"])
                            dataframes["available_seasons"] = seasons_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "available_seasons")
                            _save_dataframe_to_csv(seasons_df, csv_path)

                    elif key == "career":
                        # Convert season totals regular season to DataFrame
                        if "season_totals_regular_season" in data:
                            reg_season_df = pd.DataFrame(data["season_totals_regular_season"])
                            dataframes["season_totals_regular_season"] = reg_season_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "season_totals_regular")
                            _save_dataframe_to_csv(reg_season_df, csv_path)

                        # Convert career totals regular season to DataFrame
                        if "career_totals_regular_season" in data:
                            career_reg_df = pd.DataFrame([data["career_totals_regular_season"]])
                            dataframes["career_totals_regular_season"] = career_reg_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "career_totals_regular")
                            _save_dataframe_to_csv(career_reg_df, csv_path)

                        # Convert season totals post season to DataFrame
                        if "season_totals_post_season" in data:
                            post_season_df = pd.DataFrame(data["season_totals_post_season"])
                            dataframes["season_totals_post_season"] = post_season_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "season_totals_post")
                            _save_dataframe_to_csv(post_season_df, csv_path)

                        # Convert career totals post season to DataFrame
                        if "career_totals_post_season" in data:
                            career_post_df = pd.DataFrame([data["career_totals_post_season"]])
                            dataframes["career_totals_post_season"] = career_post_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "career_totals_post")
                            _save_dataframe_to_csv(career_post_df, csv_path)

                    elif key == "gamelog_for_season":
                        # Convert gamelog to DataFrame
                        if "gamelog" in data:
                            gamelog_df = pd.DataFrame(data["gamelog"])
                            dataframes["gamelog"] = gamelog_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "gamelog")
                            _save_dataframe_to_csv(gamelog_df, csv_path)

                    elif key == "awards_history":
                        # Convert awards to DataFrame
                        if "awards" in data:
                            awards_df = pd.DataFrame(data["awards"])
                            dataframes["awards"] = awards_df

                            # Save to CSV
                            csv_path = _get_csv_path_for_player_stats(player_actual_name, effective_season, season_type, "awards")
                            _save_dataframe_to_csv(awards_df, csv_path)

            except json.JSONDecodeError as parse_error:
                logger.error(f"Failed to parse JSON from {key} logic for {player_actual_name}: {parse_error}. Response: {result_str}")
                error_response = format_response(error=f"Failed to process internal {key} results for {player_actual_name}.")
                if return_dataframe:
                    return error_response, {}
                return error_response

        # Extract data from the results
        info_data = results_json.get("info_and_headlines", {})
        career_data = results_json.get("career", {})
        gamelog_data = results_json.get("gamelog_for_season", {})
        awards_data = results_json.get("awards_history", {})

        # Create the result dictionary
        result_dict = {
            "player_name": player_actual_name,
            "player_id": player_id,
            "season_requested_for_gamelog": effective_season,
            "season_type_requested_for_gamelog": season_type,
            "info": info_data.get("player_info", {}),
            "headline_stats": info_data.get("headline_stats", {}),
            "available_seasons": info_data.get("available_seasons", []),  # Include available seasons
            "career_stats": {
                "season_totals_regular_season": career_data.get("season_totals_regular_season", []),
                "career_totals_regular_season": career_data.get("career_totals_regular_season", {}),
                "season_totals_post_season": career_data.get("season_totals_post_season", []),
                "career_totals_post_season": career_data.get("career_totals_post_season", {})
            },
            "season_gamelog": gamelog_data.get("gamelog", []),
            "awards": awards_data.get("awards", [])
        }

        logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")

        # Return the appropriate result based on return_dataframe
        if return_dataframe:
            return format_response(result_dict), dataframes

        return format_response(result_dict)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_stats_logic: {e}")
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e))
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, {}
        return error_response