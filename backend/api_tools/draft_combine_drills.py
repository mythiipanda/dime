"""
NBA API tools for accessing draft combine drill results data.

This module provides functions to fetch and process data from the NBA's draft combine
drill results endpoint, which includes physical testing metrics such as:
- Standing vertical leap
- Max vertical leap
- Lane agility time
- Modified lane agility time
- Three-quarter sprint
- Bench press

The data is returned as pandas DataFrames and can be cached as CSV files for faster access.
"""

import os
import logging
import pandas as pd
from typing import Dict, Any, Optional, Union

from nba_api.stats.endpoints import draftcombinedrillresults
from utils.validation import _validate_season_format
from utils.path_utils import get_cache_dir

# Set up logging
logger = logging.getLogger(__name__)

# Cache directory setup
DRAFT_COMBINE_CSV_DIR = get_cache_dir("draft_combine")


def _save_dataframe_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """
    Saves a DataFrame to a CSV file.

    Args:
        df: DataFrame to save
        file_path: Path to save the CSV file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save DataFrame to CSV with data types preserved
        df.to_csv(file_path, index=False)
        logger.info(f"Saved DataFrame to CSV: {file_path}")
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}", exc_info=True)


def _get_csv_path_for_draft_combine_drills(season_year: str, league_id: str = "00") -> str:
    """
    Generates a file path for saving draft combine drill results DataFrame.

    Args:
        season_year: Season year in YYYY format
        league_id: League ID (default: "00" for NBA)

    Returns:
        Path to the CSV file
    """
    filename = f"draft_combine_drills_{season_year}_{league_id}.csv"
    return os.path.join(DRAFT_COMBINE_CSV_DIR, filename)


def fetch_draft_combine_drills_logic(
    season_year: str,
    league_id: str = "00",
    output_format: str = "json"
) -> Dict[str, Any]:
    """
    Fetches draft combine drill results data from the NBA API.

    Args:
        season_year: Season year in YYYY format (e.g., "2023")
        league_id: League ID (default: "00" for NBA)
        output_format: Output format, either "json" or "dataframe" (default: "json")

    Returns:
        Dictionary containing draft combine drill results data
    """
    # Validate season year format
    _validate_season_format(season_year)

    # Check if cached CSV file exists
    csv_path = _get_csv_path_for_draft_combine_drills(season_year, league_id)

    if os.path.exists(csv_path) and output_format == "dataframe":
        try:
            logger.info(f"Loading draft combine drill results from CSV: {csv_path}")
            # Read CSV with appropriate data types
            df = pd.read_csv(csv_path)

            # Convert numeric columns to appropriate types
            numeric_columns = [
                "STANDING_VERTICAL_LEAP", "MAX_VERTICAL_LEAP",
                "LANE_AGILITY_TIME", "MODIFIED_LANE_AGILITY_TIME",
                "THREE_QUARTER_SPRINT", "BENCH_PRESS"
            ]

            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return {
                "data": df,
                "csv_path": csv_path,
                "parameters": {
                    "season_year": season_year,
                    "league_id": league_id
                }
            }
        except Exception as e:
            logger.error(f"Error loading CSV: {e}", exc_info=True)
            # If there's an error loading the CSV, fetch from the API

    # Fetch data from the NBA API
    logger.info(f"Fetching draft combine drill results for season {season_year}")

    try:
        # Call the NBA API endpoint
        drill_results = draftcombinedrillresults.DraftCombineDrillResults(
            league_id=league_id,
            season_year=season_year
        )

        # Get the data
        drill_data = drill_results.get_normalized_dict()

        # Process the data based on the requested output format
        if output_format == "dataframe":
            # Convert to DataFrame
            if "Results" in drill_data and drill_data["Results"]:
                df = pd.DataFrame(drill_data["Results"])

                # Save to CSV for future use
                _save_dataframe_to_csv(df, csv_path)

                return {
                    "data": df,
                    "csv_path": csv_path,
                    "parameters": {
                        "season_year": season_year,
                        "league_id": league_id
                    }
                }
            else:
                # Return empty DataFrame if no data
                empty_df = pd.DataFrame(columns=[
                    "TEMP_PLAYER_ID", "PLAYER_ID", "FIRST_NAME", "LAST_NAME",
                    "PLAYER_NAME", "POSITION", "STANDING_VERTICAL_LEAP",
                    "MAX_VERTICAL_LEAP", "LANE_AGILITY_TIME",
                    "MODIFIED_LANE_AGILITY_TIME", "THREE_QUARTER_SPRINT", "BENCH_PRESS"
                ])

                return {
                    "data": empty_df,
                    "csv_path": csv_path,
                    "parameters": {
                        "season_year": season_year,
                        "league_id": league_id
                    }
                }
        else:
            # Return JSON data
            return {
                "data": drill_data,
                "parameters": {
                    "season_year": season_year,
                    "league_id": league_id
                }
            }

    except Exception as e:
        logger.error(f"Error fetching draft combine drill results: {e}", exc_info=True)

        if output_format == "dataframe":
            # Return empty DataFrame on error
            empty_df = pd.DataFrame(columns=[
                "TEMP_PLAYER_ID", "PLAYER_ID", "FIRST_NAME", "LAST_NAME",
                "PLAYER_NAME", "POSITION", "STANDING_VERTICAL_LEAP",
                "MAX_VERTICAL_LEAP", "LANE_AGILITY_TIME",
                "MODIFIED_LANE_AGILITY_TIME", "THREE_QUARTER_SPRINT", "BENCH_PRESS"
            ])

            return {
                "data": empty_df,
                "error": str(e),
                "parameters": {
                    "season_year": season_year,
                    "league_id": league_id
                }
            }
        else:
            # Return error message in JSON format
            return {
                "data": None,
                "error": str(e),
                "parameters": {
                    "season_year": season_year,
                    "league_id": league_id
                }
            }


def get_draft_combine_drills(
    season_year: str,
    league_id: str = "00",
    output_format: str = "json"
) -> Dict[str, Any]:
    """
    Gets draft combine drill results data.

    This function is the main entry point for fetching draft combine drill results data.
    It calls the fetch_draft_combine_drills_logic function and returns the results.

    Args:
        season_year: Season year in YYYY format (e.g., "2023")
        league_id: League ID (default: "00" for NBA)
        output_format: Output format, either "json" or "dataframe" (default: "json")

    Returns:
        Dictionary containing draft combine drill results data
    """
    return fetch_draft_combine_drills_logic(
        season_year=season_year,
        league_id=league_id,
        output_format=output_format
    )
