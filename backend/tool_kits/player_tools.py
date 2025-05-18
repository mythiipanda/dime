"""
This module provides a toolkit of player-related functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch and
process various NBA player statistics and information, making them easily usable by an AI agent.
"""
import logging
import json
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID
from backend.config import settings
# Import specific logic functions for player tools
from backend.api_tools.player_common_info import fetch_player_info_logic
from backend.api_tools.player_gamelogs import fetch_player_gamelog_logic
from backend.api_tools.player_career_data import fetch_player_career_stats_logic, fetch_player_awards_logic
from backend.api_tools.player_dashboard_stats import fetch_player_profile_logic
from backend.api_tools.player_aggregate_stats import fetch_player_stats_logic
from backend.api_tools.analyze import analyze_player_stats_logic
from backend.api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic
from backend.api_tools.player_dashboard_team_performance import fetch_player_dashboard_by_team_performance_logic
from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic

logger = logging.getLogger(__name__)

@tool
def get_player_info(
    player_name: str,
    as_dataframe: bool = False
) -> str:
    """
    Fetches basic player information, including biographical details, headshot URL,
    available seasons, and headline career statistics.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The full name of the player (e.g., "LeBron James").
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing player information, headline stats, and available seasons.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_info' called for '{player_name}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_info_logic(
            player_name=player_name,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player information has been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                csv_path = f"backend/cache/player_info/{clean_player_name}_{key}.csv"

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
        return fetch_player_info_logic(player_name=player_name)

@tool
def get_player_gamelog(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches the game-by-game statistics for a specific player in a given season and season type.
    Includes video availability flags for plays if available.

    Args:
        player_name (str): The full name of the player (e.g., "Jayson Tatum").
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".

    Returns:
        str: JSON string containing a list of game log entries.
    """
    logger.debug(f"Tool 'get_player_gamelog' called for '{player_name}', season '{season}', type '{season_type}'")
    result = fetch_player_gamelog_logic(player_name, season, season_type)
    return result

@tool
def get_player_career_stats(
    player_name: str,
    per_mode: str = PerMode36.per_game,
    as_dataframe: bool = False
) -> str:
    """
    Fetches player career statistics, including Regular Season and Playoffs if available, aggregated by season.
    Do NOT try to pass a 'season_type' argument to this tool; it processes all available types.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The full name of the player (e.g., "Kevin Durant").
        per_mode (str, optional): The statistical mode (e.g., "PerGame", "Totals", "Per36").
            Valid values from `nba_api.stats.library.parameters.PerMode36`. Defaults to "PerGame".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing career statistics data. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_career_stats' called for '{player_name}', per_mode '{per_mode}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_career_stats_logic(
            player_name=player_name,
            per_mode=per_mode,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player career statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.lower()

                # Determine data type for filename
                if key == "season_totals_regular_season":
                    data_type = "season_regular"
                elif key == "career_totals_regular_season":
                    data_type = "career_regular"
                elif key == "season_totals_post_season":
                    data_type = "season_post"
                elif key == "career_totals_post_season":
                    data_type = "career_post"
                else:
                    data_type = key

                csv_path = f"backend/cache/player_career/{clean_player_name}_{clean_per_mode}_{data_type}.csv"

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
        return fetch_player_career_stats_logic(player_name=player_name, per_mode=per_mode)

@tool
def get_player_awards(
    player_name: str,
    as_dataframe: bool = False
) -> str:
    """
    Fetches a list of awards won by a specific player throughout their career.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The full name of the player (e.g., "Michael Jordan").
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing a list of awards. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_awards' called for '{player_name}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_awards_logic(
            player_name=player_name,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player awards have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                csv_path = f"backend/cache/player_awards/{clean_player_name}_awards.csv"

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
        return fetch_player_awards_logic(player_name=player_name)

@tool
def get_player_profile(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """
    Fetches a comprehensive player profile, including biographical information, career stats,
    next game details, and season highlights using the PlayerProfileV2 endpoint.

    Args:
        player_name (str): The full name of the player (e.g., "Giannis Antetokounmpo").
        per_mode (str, optional): The statistical mode for career stats (e.g., "PerGame", "Totals").
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`. Defaults to "PerGame".

    Returns:
        str: JSON string containing the player's profile.
    """
    logger.debug(f"Tool 'get_player_profile' called for {player_name}, per_mode {per_mode}")
    result = fetch_player_profile_logic(player_name, per_mode=per_mode)
    return result

@tool
def get_player_aggregate_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    as_dataframe: bool = False
) -> str:
    """
    Fetches an aggregated set of player statistics for a specific season.
    This tool combines player info, game logs, career stats, and awards for a holistic view.
    Provides DataFrame output capabilities.

    Args:
        player_name (str): The full name of the player (e.g., "Trae Young").
        season (str, optional): The NBA season identifier (e.g., "2023-24"). Defaults to the current season.
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing aggregated player statistics. If as_dataframe=True, the JSON response
             will include additional information about the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_player_aggregate_stats' called for {player_name}, season {season}, type {season_type}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_player_stats_logic(
            player_name=player_name,
            season=season,
            season_type=season_type,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean player name for filename
                clean_player_name = player_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                csv_path = f"backend/cache/player_stats/{clean_player_name}_{season}_{clean_season_type}_{key}.csv"

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
        return fetch_player_stats_logic(player_name=player_name, season=season, season_type=season_type)

@tool
def get_player_analysis(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    league_id: str = LeagueID.nba
) -> str:
    """
    Provides an analysis of a player's statistics, primarily fetching overall dashboard statistics
    for a specified player and season using the `PlayerDashboardByYearOverYear` NBA API endpoint.

    Args:
        player_name (str): The full name of the player.
        season (str, optional): The primary NBA season for analysis (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): Type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode for dashboard stats (e.g., "PerGame", "Totals").
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`. Defaults to "PerGame".
        league_id (str, optional): League ID (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".

    Returns:
        str: JSON string containing player analysis and dashboard statistics.
    """
    logger.debug(f"Tool 'get_player_analysis' called for Player: {player_name}, Season: {season}")
    return analyze_player_stats_logic(player_name, season, season_type, per_mode, league_id)

@tool
def get_player_insights(player_name: str, season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerModeDetailed.per_game, league_id: str = LeagueID.nba) -> str:
    """
    Fetches overall player dashboard statistics for a given season, type, and mode, providing insights into performance.
    This is a wrapper around `analyze_player_stats_logic` which uses `PlayerDashboardByYearOverYear`.
    Consider using `get_player_analysis` which is identical.

    Args:
        player_name (str): The full name of the player (e.g., "Stephen Curry").
        season (str, optional): The primary NBA season for analysis (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`.
        league_id (str, optional): League ID. Defaults to "00" (NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`.

    Returns:
        str: JSON string containing player dashboard statistics.
    """
    logger.debug(
        f"Tool 'get_player_insights' called for Player: {player_name}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}"
    )
    result = analyze_player_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id
    )
    return result

@tool
def get_player_estimated_metrics(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches player estimated metrics (e.g., E_OFF_RATING, E_DEF_RATING, E_NET_RATING)
    for all players in a given season and season type.

    Args:
        season (str, optional): NBA season in 'YYYY-YY' format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): Season type (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        league_id (str, optional): League ID (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".

    Returns:
        str: JSON string containing player estimated metrics for all players in the specified scope.
    """
    logger.debug(f"Tool 'get_player_estimated_metrics' called for Season: {season}, Type: {season_type}, League: {league_id}")
    return fetch_player_estimated_metrics_logic(
        season=season,
        season_type=season_type,
        league_id=league_id
    )

@tool
def get_player_dashboard_by_team_performance(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals, # Default as per nba_api
    measure_type: str = "Base", # Default as per nba_api
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    vs_division: Optional[str] = None,
    vs_conference: Optional[str] = None,
    shot_clock_range: Optional[str] = None,
    season_segment: Optional[str] = None,
    po_round: Optional[int] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    league_id: Optional[str] = None,
    game_segment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """
    Fetches a player's impact on their team's performance using the PlayerDashboardByTeamPerformance NBA API endpoint.
    This provides various splits of team performance when the player is on or off the court.

    Args:
        player_name (str): Full name of the player (e.g., "LeBron James").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): "Regular Season", "Playoffs", or "Pre Season". Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode (e.g., "Totals", "PerGame"). Defaults to "Totals".
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`.
        measure_type (str, optional): "Base", "Advanced", etc. Defaults to "Base".
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`.
        last_n_games (int, optional): Number of most recent games to include. Defaults to 0 (all).
        month (int, optional): Month filter (1-12, 0 for all). Defaults to 0.
        opponent_team_id (int, optional): Opponent team ID. Defaults to 0 (all opponents).
        pace_adjust (str, optional): Pace adjustment ("Y" or "N"). Defaults to "N".
        period (int, optional): Period filter (0 for all, 1-4 for quarters, 5+ for overtimes). Defaults to 0.
        plus_minus (str, optional): Plus/Minus ("Y" or "N"). Defaults to "N".
        rank (str, optional): Rank ("Y" or "N"). Defaults to "N".
        vs_division (Optional[str], optional): Division abbreviation (e.g., "Atlantic", "Central").
        vs_conference (Optional[str], optional): Conference abbreviation (e.g., "East", "West").
        shot_clock_range (Optional[str], optional): Shot clock range (e.g., "24-22", "4-0 Fast").
        season_segment (Optional[str], optional): "Pre All-Star" or "Post All-Star".
        po_round (Optional[int], optional): Playoff round number (e.g., 1 for First Round).
        outcome (Optional[str], optional): Game outcome ("W" or "L").
        location (Optional[str], optional): Game location ("Home" or "Road").
        league_id (Optional[str], optional): League ID (e.g., "00" for NBA).
        game_segment (Optional[str], optional): "First Half", "Second Half", "Overtime".
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with team performance dashboard data related to the player.
    """
    logger.debug(f"Tool 'get_player_dashboard_by_team_performance' called for {player_name}, season {season}")
    return fetch_player_dashboard_by_team_performance_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        period=period,
        plus_minus=plus_minus,
        rank=rank,
        vs_division_nullable=vs_division,
        vs_conference_nullable=vs_conference,
        shot_clock_range_nullable=shot_clock_range,
        season_segment_nullable=season_segment,
        po_round_nullable=po_round,
        outcome_nullable=outcome,
        location_nullable=location,
        league_id_nullable=league_id,
        game_segment_nullable=game_segment,
        date_from_nullable=date_from,
        date_to_nullable=date_to
    )

@tool
def get_player_clutch_stats(
    player_name: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base", # Default from nba_api
    per_mode: str = "Totals", # Default from nba_api
    plus_minus: str = "N", # Default from nba_api
    pace_adjust: str = "N", # Default from nba_api
    rank: str = "N", # Default from nba_api
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    period: int = 0, # Default from nba_api
    last_n_games: int = 0, # Default from nba_api
    month: int = 0, # Default from nba_api
    opponent_team_id: int = 0, # Default from nba_api
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """
    Fetches all clutch split dashboards for a player in a given season using the PlayerDashboardByClutch NBA API endpoint.

    Args:
        player_name (str): Full name of the player (e.g., "LeBron James").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): "Regular Season", "Playoffs", or "Pre Season". Defaults to "Regular Season".
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
        last_n_games (int, optional): Number of most recent games to include. Defaults to 0.
        month (int, optional): Month filter (0 for all). Defaults to 0.
        opponent_team_id (int, optional): Opponent team ID (0 for all). Defaults to 0.
        location_nullable (Optional[str], optional): "Home" or "Road".
        outcome_nullable (Optional[str], optional): "W" or "L".
        vs_conference_nullable (Optional[str], optional): Conference filter.
        vs_division_nullable (Optional[str], optional): Division filter.
        season_segment_nullable (Optional[str], optional): "Pre All-Star" or "Post All-Star".
        date_from_nullable (Optional[str], optional): Start date (YYYY-MM-DD).
        date_to_nullable (Optional[str], optional): End date (YYYY-MM-DD).

    Returns:
        str: JSON string with all clutch split dashboards for the player.
    """
    logger.debug(f"Tool 'get_player_clutch_stats' called for {player_name}, season {season}")
    return fetch_player_clutch_stats_logic(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        plus_minus=plus_minus,
        pace_adjust=pace_adjust,
        rank=rank,
        shot_clock_range_nullable=shot_clock_range_nullable,
        game_segment_nullable=game_segment_nullable,
        period=period,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        season_segment_nullable=season_segment_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable
    )