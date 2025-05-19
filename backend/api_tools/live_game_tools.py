"""
Handles fetching and formatting live NBA scoreboard data.
Uses nba_api.live.nba.endpoints.scoreboard.
Provides both JSON and DataFrame outputs with CSV caching.
"""
from typing import Dict, List, Optional, TypedDict, Any, Union, Tuple
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
import logging
import os
import pandas as pd
from functools import lru_cache

from ..config import settings
from ..core.errors import Errors
from .utils import format_response
from ..utils.path_utils import get_cache_dir, get_cache_file_path, get_relative_cache_path

logger = logging.getLogger(__name__)

# --- Cache Directory Setup ---
LIVE_SCOREBOARD_CSV_DIR = get_cache_dir("live_scoreboard")

# --- Helper Functions for CSV Caching ---
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

def _get_csv_path_for_live_scoreboard(date_str: str) -> str:
    """
    Generates a file path for saving live scoreboard DataFrame as CSV.

    Args:
        date_str: The date string in YYYY-MM-DD format

    Returns:
        Path to the CSV file
    """
    filename = f"live_scoreboard_{date_str}.csv"
    return get_cache_file_path(filename, "live_scoreboard")

# --- Module-Level Constants ---
CACHE_TTL_SECONDS = 10  # Time-to-live for cached raw scoreboard data
SCOREBOARD_RAW_CACHE_SIZE = 2 # Max number of raw scoreboard responses to cache

GAME_STATUS_SCHEDULED = 1
GAME_STATUS_IN_PROGRESS = 2
GAME_STATUS_FINAL = 3
DEFAULT_TRICODE = "N/A"

# --- TypedDicts for Data Structure Documentation ---
class GameLeader(TypedDict): # Kept for potential future use, though not currently populated
    name: str
    stats: str

class TeamInfo(TypedDict):
    id: Optional[int]
    code: str
    name: Optional[str] # Name might not always be present in raw data
    score: int
    record: Optional[str]
    wins: Optional[int]
    losses: Optional[int]

class GameStatusInfo(TypedDict): # Renamed from GameStatus to avoid conflict
    clock: Optional[str]
    period: int
    state_code: int # e.g., 1, 2, 3
    state_text: str # e.g., "Halftime", "Q1 0:00", "Final"

class FormattedGameInfo(TypedDict): # Renamed from GameInfo
    game_id: Optional[str]
    start_time_utc: str
    status: GameStatusInfo
    home_team: TeamInfo
    away_team: TeamInfo

class FormattedScoreboardResponse(TypedDict): # Renamed from ScoreboardResponse
    # meta: Dict[str, Any] # Meta not currently included in formatted response
    date: str
    games: List[FormattedGameInfo]

# --- Caching Function for Raw Data ---
@lru_cache(maxsize=SCOREBOARD_RAW_CACHE_SIZE)
def get_cached_scoreboard_data(
    cache_key: str,
    timestamp_bucket: str # Timestamp bucket for more frequent invalidation
) -> Dict[str, Any]:
    """
    Cached wrapper for fetching raw live scoreboard data.
    Uses a timestamp bucket for time-based cache invalidation.

    Args:
        cache_key: A simple string key for the cache (e.g., "live_scoreboard").
        timestamp_bucket: A string derived from the current time, bucketed by CACHE_TTL_SECONDS.

    Returns:
        Dict[str, Any]: The raw dictionary result from the API call.

    Raises:
        Exception: If the ScoreBoard API call fails.
    """
    logger.info(f"Cache miss or expiry for live scoreboard (key: {cache_key}, ts_bucket: {timestamp_bucket}) - fetching new data.")
    try:
        board = scoreboard.ScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS)
        return board.get_dict()
    except Exception as e:
        logger.error(f"ScoreBoard API call failed: {e}", exc_info=True)
        raise # Re-raise to be handled by the main logic function

# --- Helper for Formatting a Single Game ---
def _format_live_game_details(raw_game_data: Dict[str, Any]) -> FormattedGameInfo:
    """Formats a single raw game dictionary into the desired structure."""
    home_team_raw = raw_game_data.get("homeTeam", {})
    away_team_raw = raw_game_data.get("awayTeam", {})

    game_status_text_raw = raw_game_data.get("gameStatusText", "Status Unknown")
    game_status_code = raw_game_data.get("gameStatus", 0) # 0: Unknown, 1: Scheduled, 2: In Progress, 3: Final

    game_clock_val: Optional[str] = None
    current_period_val = 0
    status_text_final = game_status_text_raw

    if game_status_code == GAME_STATUS_IN_PROGRESS:
        game_clock_val = raw_game_data.get("gameClock")
        current_period_val = raw_game_data.get("period", 0)
        if game_clock_val: # If clock is present, format it with period
            status_text_final = f"Q{current_period_val} {game_clock_val}"
        elif status_text_final == "Halftime":
            pass # Keep "Halftime" as is
        else: # Default live status if clock is missing but game is in progress
            status_text_final = f"Q{current_period_val} In Progress"
    elif game_status_code == GAME_STATUS_SCHEDULED:
         # For scheduled games, gameStatusText might be the start time (e.g., "7:00 PM ET")
         # We already have gameTimeUTC, so can simplify or use that.
         status_text_final = "Scheduled" # Or use game_status_text_raw if more descriptive
    elif game_status_code == GAME_STATUS_FINAL:
        status_text_final = "Final"

    return {
        "game_id": raw_game_data.get("gameId"),
        "start_time_utc": raw_game_data.get("gameTimeUTC", ""),
        "status": {
            "clock": game_clock_val,
            "period": current_period_val,
            "state_code": game_status_code,
            "state_text": status_text_final
        },
        "home_team": {
            "id": home_team_raw.get("teamId"),
            "code": home_team_raw.get("teamTricode", DEFAULT_TRICODE),
            "name": home_team_raw.get("teamName"),
            "score": home_team_raw.get("score", 0),
            "record": f"{home_team_raw.get('wins', 0)}-{home_team_raw.get('losses', 0)}" if home_team_raw.get('wins') is not None else None,
            "wins": home_team_raw.get("wins"),
            "losses": home_team_raw.get("losses")
        },
        "away_team": {
            "id": away_team_raw.get("teamId"),
            "code": away_team_raw.get("teamTricode", DEFAULT_TRICODE),
            "name": away_team_raw.get("teamName"),
            "score": away_team_raw.get("score", 0),
            "record": f"{away_team_raw.get('wins', 0)}-{away_team_raw.get('losses', 0)}" if away_team_raw.get('wins') is not None else None,
            "wins": away_team_raw.get("wins"),
            "losses": away_team_raw.get("losses")
        }
    }

# --- Main Logic Function ---
def fetch_league_scoreboard_logic(
    bypass_cache: bool = False,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches and formats live scoreboard data for current NBA games.
    Provides DataFrame output capabilities.

    Args:
        bypass_cache: If True, ignores cached data. Defaults to False.
        return_dataframe: Whether to return DataFrames along with the JSON response.

    Returns:
        If return_dataframe=False:
            str: JSON string of current game information or an error message.
                 See FormattedScoreboardResponse TypedDict for structure.
        If return_dataframe=True:
            Tuple[str, Dict[str, pd.DataFrame]]: A tuple containing the JSON response string
                                               and a dictionary of DataFrames.
    """
    logger.info(f"Executing fetch_league_scoreboard_logic (bypass_cache: {bypass_cache}, return_dataframe: {return_dataframe})")

    # Store DataFrames if requested
    dataframes = {}

    cache_key = "live_scoreboard_data" # More descriptive key
    # Timestamp bucket for cache invalidation, based on CACHE_TTL_SECONDS
    timestamp_bucket = str(int(datetime.now().timestamp() // CACHE_TTL_SECONDS))

    try:
        if bypass_cache:
            logger.info("Bypassing cache for live scoreboard.")
            board = scoreboard.ScoreBoard(timeout=settings.DEFAULT_TIMEOUT_SECONDS)
            raw_data = board.get_dict()
        else:
            raw_data = get_cached_scoreboard_data(cache_key=cache_key, timestamp_bucket=timestamp_bucket)

        scoreboard_outer = raw_data.get('scoreboard', {})
        raw_games_list = scoreboard_outer.get('games', [])
        game_date_str = scoreboard_outer.get('gameDate', datetime.now().strftime("%Y-%m-%d"))

        formatted_games_list: List[FormattedGameInfo] = [_format_live_game_details(game) for game in raw_games_list]

        response_data: FormattedScoreboardResponse = {
            "date": game_date_str,
            "games": formatted_games_list
        }

        # Create DataFrames if requested
        if return_dataframe:
            # Create a DataFrame for the games list
            games_data = []
            for game in formatted_games_list:
                # Flatten the nested structure for DataFrame
                game_row = {
                    "game_id": game.get("game_id"),
                    "start_time_utc": game.get("start_time_utc"),
                    "status_clock": game.get("status", {}).get("clock"),
                    "status_period": game.get("status", {}).get("period"),
                    "status_state_code": game.get("status", {}).get("state_code"),
                    "status_state_text": game.get("status", {}).get("state_text"),
                    "home_team_id": game.get("home_team", {}).get("id"),
                    "home_team_code": game.get("home_team", {}).get("code"),
                    "home_team_name": game.get("home_team", {}).get("name"),
                    "home_team_score": game.get("home_team", {}).get("score"),
                    "home_team_record": game.get("home_team", {}).get("record"),
                    "home_team_wins": game.get("home_team", {}).get("wins"),
                    "home_team_losses": game.get("home_team", {}).get("losses"),
                    "away_team_id": game.get("away_team", {}).get("id"),
                    "away_team_code": game.get("away_team", {}).get("code"),
                    "away_team_name": game.get("away_team", {}).get("name"),
                    "away_team_score": game.get("away_team", {}).get("score"),
                    "away_team_record": game.get("away_team", {}).get("record"),
                    "away_team_wins": game.get("away_team", {}).get("wins"),
                    "away_team_losses": game.get("away_team", {}).get("losses")
                }
                games_data.append(game_row)

            # Create DataFrame from the flattened data
            games_df = pd.DataFrame(games_data)
            dataframes["games"] = games_df

            # Save to CSV
            if not games_df.empty:
                csv_path = _get_csv_path_for_live_scoreboard(game_date_str)
                _save_dataframe_to_csv(games_df, csv_path)

                # Add relative path to response
                relative_path = get_relative_cache_path(
                    os.path.basename(csv_path),
                    "live_scoreboard"
                )

                response_data["dataframe_info"] = {
                    "message": "Live scoreboard data has been converted to DataFrame and saved as CSV file",
                    "dataframes": {
                        "games": {
                            "shape": list(games_df.shape),
                            "columns": games_df.columns.tolist(),
                            "csv_path": relative_path
                        }
                    }
                }

        logger.info(f"fetch_league_scoreboard_logic formatted {len(formatted_games_list)} games for date {game_date_str}")

        if return_dataframe:
            return format_response(response_data), dataframes
        return format_response(response_data)

    except Exception as e:
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        logger.error(f"Error fetching/formatting scoreboard data for {current_date_str}: {str(e)}", exc_info=True)
        error_msg = Errors.LEAGUE_SCOREBOARD_UNEXPECTED.format(game_date=current_date_str, error=str(e)) if hasattr(Errors, 'LEAGUE_SCOREBOARD_UNEXPECTED') else f"Unexpected error fetching scoreboard: {e}"
        error_response = format_response(error=error_msg)
        if return_dataframe:
            return error_response, dataframes
        return error_response