"""
This module provides a toolkit of player and team tracking-related functions
exposed as agent tools. These tools wrap specific logic functions from `backend.api_tools`
to fetch detailed statistics like clutch performance, passing, rebounding, shooting,
defense, hustle, and shot charts.
"""
import logging
import json
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, PerModeSimple, LeagueID,
    MeasureTypeDetailedDefense # For clutch and defense stats
)
from backend.config import settings

# Import specific logic functions for tracking tools
from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic
from backend.api_tools.player_passing import fetch_player_passing_stats_logic
from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic
from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic
from backend.api_tools.player_shot_charts import fetch_player_shotchart_logic
from backend.api_tools.player_dashboard_stats import fetch_player_defense_logic, fetch_player_hustle_stats_logic
from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from backend.api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic

logger = logging.getLogger(__name__)

# --- Player Tracking Tools ---
@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailedDefense.base, # Match underlying logic default
    per_mode: str = PerModeDetailed.totals, # Match underlying logic default
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    period: int = 0,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    as_dataframe: bool = False
) -> str:
    """
    Fetches player statistics in clutch situations using PlayerDashboardByClutch endpoint.
    Provides various splits like Last5Min5PointGame, Last3Min5PointGame, etc.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): Full name of the player (e.g., "LeBron James").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): "Regular Season", "Playoffs", etc. Defaults to "Regular Season".
        measure_type (str, optional): "Base", "Advanced", etc. Defaults to "Base".
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`.
        per_mode (str, optional): Statistical mode (e.g., "Totals", "PerGame"). Defaults to "Totals".
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`.
        plus_minus (str, optional): "Y" or "N". Defaults to "N".
        pace_adjust (str, optional): "Y" or "N". Defaults to "N".
        rank (str, optional): "Y" or "N". Defaults to "N".
        shot_clock_range_nullable (Optional[str], optional): Shot clock range filter.
        game_segment_nullable (Optional[str], optional): Game segment filter.
        period (int, optional): Period filter (0 for all). Defaults to 0.
        last_n_games (int, optional): Number of most recent games. Defaults to 0.
        month (int, optional): Month filter (0 for all). Defaults to 0.
        opponent_team_id (int, optional): Opponent team ID. Defaults to 0.
        location_nullable (Optional[str], optional): "Home" or "Road".
        outcome_nullable (Optional[str], optional): "W" or "L".
        vs_conference_nullable (Optional[str], optional): Conference filter.
        vs_division_nullable (Optional[str], optional): Division filter.
        season_segment_nullable (Optional[str], optional): "Pre All-Star" or "Post All-Star".
        date_from_nullable (Optional[str], optional): Start date (YYYY-MM-DD).
        date_to_nullable (Optional[str], optional): End date (YYYY-MM-DD).
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with clutch statistics, including multiple dashboard datasets.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_clutch_stats' called for '{player_name}', season '{season}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_clutch_stats_logic(
            player_name=player_name, season=season, season_type=season_type,
            measure_type=measure_type, per_mode=per_mode, plus_minus=plus_minus,
            pace_adjust=pace_adjust, rank=rank, shot_clock_range_nullable=shot_clock_range_nullable,
            game_segment_nullable=game_segment_nullable, period=period, last_n_games=last_n_games,
            month=month, opponent_team_id=opponent_team_id, location_nullable=location_nullable,
            outcome_nullable=outcome_nullable, vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable, season_segment_nullable=season_segment_nullable,
            date_from_nullable=date_from_nullable, date_to_nullable=date_to_nullable,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player clutch statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean dashboard name for filename
                clean_dashboard = key.replace(" ", "_").lower()

                csv_path = f"backend/cache/player_clutch/{clean_player_name}_{season}_{clean_season_type}_{clean_dashboard}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
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
        return fetch_player_clutch_stats_logic(
            player_name=player_name, season=season, season_type=season_type,
            measure_type=measure_type, per_mode=per_mode, plus_minus=plus_minus,
            pace_adjust=pace_adjust, rank=rank, shot_clock_range_nullable=shot_clock_range_nullable,
            game_segment_nullable=game_segment_nullable, period=period, last_n_games=last_n_games,
            month=month, opponent_team_id=opponent_team_id, location_nullable=location_nullable,
            outcome_nullable=outcome_nullable, vs_conference_nullable=vs_conference_nullable,
            vs_division_nullable=vs_division_nullable, season_segment_nullable=season_segment_nullable,
            date_from_nullable=date_from_nullable, date_to_nullable=date_to_nullable
        )

@tool
def get_player_passing_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # Matches underlying logic default
    as_dataframe: bool = False
) -> str:
    """
    Fetches player passing tracking statistics (PlayerDashPtPass).
    Provides DataFrame output capabilities.

    Args:
        player_name (str): Full name of the player (e.g., "Nikola Jokic").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode (e.g., "PerGame", "Totals"). Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeSimple`.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with player passing statistics (passes made, passes received).
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_passing_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_passing_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player passing statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                csv_path = f"backend/cache/player_passing/{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{key}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
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
        return fetch_player_passing_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )

@tool
def get_player_rebounding_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # Matches underlying logic default
    as_dataframe: bool = False
) -> str:
    """
    Fetches player rebounding tracking statistics (PlayerDashPtReb).
    Provides DataFrame output capabilities.

    Args:
        player_name (str): Full name of the player (e.g., "Domantas Sabonis").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with player rebounding statistics, categorized by various factors.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_rebounding_stats' called for {player_name}, season {season}, type {season_type}, mode {per_mode}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_rebounding_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player rebounding statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                csv_path = f"backend/cache/player_rebounding/{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{key}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
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
        return fetch_player_rebounding_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )

@tool
def get_player_shots_tracking(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # Added to match underlying logic
    opponent_team_id: int = 0, # Added to match underlying logic
    date_from: Optional[str] = None, # Added to match underlying logic
    date_to: Optional[str] = None, # Added to match underlying logic
    as_dataframe: bool = False
) -> str:
    """
    Fetches detailed player shooting statistics by various factors (PlayerDashPtShots).
    Provides DataFrame output capabilities.

    Args:
        player_name (str): Full name of the player (e.g., "Stephen Curry").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with detailed shot tracking statistics (e.g., by shot clock, dribbles, defender distance).
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_shots_tracking' called for player_name '{player_name}', season '{season}', type '{season_type}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_shots_tracking_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player shooting tracking statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                # Map the key to a more descriptive name for the file path
                data_type_map = {
                    "general_shooting": "general",
                    "by_shot_clock": "shot_clock",
                    "by_dribble_count": "dribble",
                    "by_touch_time": "touch_time",
                    "by_defender_distance": "defender_distance",
                    "by_defender_distance_10ft_plus": "defender_distance_10ft_plus"
                }

                data_type = data_type_map.get(key, key)

                csv_path = f"backend/cache/player_shooting_tracking/{clean_player_name}_{season}_{clean_season_type}_{clean_per_mode}_{data_type}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
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
        return fetch_player_shots_tracking_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to
        )

@tool
def get_player_shotchart(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular
    # Add other params from fetch_player_shotchart_logic if they become available/used
) -> str:
    """
    Fetches detailed shot chart data for a player, including shot locations, makes/misses,
    zone summaries, and potentially a path to a generated visualization image.

    Args:
        player_name (str): Full name of the player (e.g., "Luka Doncic").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".

    Returns:
        str: JSON string with shot chart data, zone summaries, and visualization path.
    """
    logger.debug(f"Tool 'get_player_shotchart' called for {player_name}, season {season}, type {season_type}")
    return fetch_player_shotchart_logic(
        player_name=player_name, season=season, season_type=season_type
    )

@tool
def get_player_defense_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game, # Matches underlying logic default
    opponent_team_id: int = 0, # Added to match underlying logic
    date_from: Optional[str] = None, # Added to match underlying logic
    date_to: Optional[str] = None # Added to match underlying logic
) -> str:
    """
    Fetches detailed defensive statistics for a player (PlayerDashPtShotDefend).

    Args:
        player_name (str): Full name of the player (e.g., "Rudy Gobert").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with defensive statistics, such as shots defended at different distances.
    """
    logger.debug(f"Tool 'get_player_defense_stats' called for {player_name}, season {season}, per_mode {per_mode}")
    return fetch_player_defense_logic(
        player_name=player_name, season=season, season_type=season_type, per_mode=per_mode,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to
    )

@tool
def get_player_hustle_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular, # Matches underlying logic default
    per_mode: str = PerModeDetailed.per_game, # Matches underlying logic default
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba, # Matches underlying logic default
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches player or league-wide hustle statistics (LeagueHustleStatsPlayer).
    If player_name is provided, filters for that player. If team_id is provided, filters for that team.
    If neither is provided, fetches league-wide hustle stats.

    Args:
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        player_name (Optional[str], optional): Full name of the player.
        team_id (Optional[int], optional): Team ID.
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with hustle statistics (e.g., screen assists, deflections, loose balls recovered).
    """
    logger.debug(
        f"Tool 'get_player_hustle_stats' called for Season: {season}, Type: {season_type}, Mode: {per_mode}, "
        f"Player: {player_name}, Team: {team_id}, League: {league_id}"
    )
    return fetch_player_hustle_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode,
        player_name=player_name, team_id=team_id, league_id=league_id,
        date_from=date_from, date_to=date_to
    )

# --- Team Tracking Tools ---
@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game # Matches underlying logic default
) -> str:
    """
    Fetches team passing tracking statistics (TeamDashPtPass).

    Args:
        team_identifier (str): Team's name, abbreviation, or ID.
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".

    Returns:
        str: JSON string with team passing statistics (passes made, passes received).
    """
    logger.debug(f"Tool 'get_team_passing_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    return fetch_team_passing_stats_logic(
        team_identifier=team_identifier, season=season, season_type=season_type, per_mode=per_mode
    )

@tool
def get_team_shooting_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # Matches underlying logic default
    opponent_team_id: int = 0, # Added to match underlying logic
    date_from: Optional[str] = None, # Added to match underlying logic
    date_to: Optional[str] = None # Added to match underlying logic
) -> str:
    """
    Fetches team shooting tracking statistics (TeamDashPtShots).

    Args:
        team_identifier (str): Team's name, abbreviation, or ID.
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with team shooting statistics, categorized by various factors.
    """
    logger.debug(f"Tool 'get_team_shooting_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    return fetch_team_shooting_stats_logic(
        team_identifier=team_identifier, season=season, season_type=season_type, per_mode=per_mode,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to
    )

@tool
def get_team_rebounding_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game, # Matches underlying logic default
    opponent_team_id: int = 0, # Added to match underlying logic
    date_from: Optional[str] = None, # Added to match underlying logic
    date_to: Optional[str] = None # Added to match underlying logic
) -> str:
    """
    Fetches team rebounding tracking statistics (TeamDashPtReb).

    Args:
        team_identifier (str): Team's name, abbreviation, or ID.
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with team rebounding statistics, categorized by various factors.
    """
    logger.debug(f"Tool 'get_team_rebounding_stats' called for {team_identifier}, season {season}, mode {per_mode}")
    return fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier, season=season, season_type=season_type, per_mode=per_mode,
        opponent_team_id=opponent_team_id, date_from=date_from, date_to=date_to
    )