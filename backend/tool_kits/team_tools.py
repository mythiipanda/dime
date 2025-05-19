"""
This module provides a toolkit of team-related functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch
various NBA team statistics and information.
"""
import logging
import json
from typing import Optional
from agno.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense, PerModeSimple
from backend.config import settings
# Import specific logic functions for team tools
from backend.api_tools.team_info_roster import fetch_team_info_and_roster_logic
from backend.api_tools.team_general_stats import fetch_team_stats_logic
from backend.api_tools.team_passing_tracking import fetch_team_passing_stats_logic
from backend.api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic
from backend.api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic

logger = logging.getLogger(__name__)

@tool
def get_team_info_and_roster(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular, # Added season_type for consistency with underlying logic
    league_id: str = LeagueID.nba # Added league_id for consistency
) -> str:
    """
    Fetches comprehensive team information for a specific season, including basic details,
    conference/division ranks, current season roster, and coaching staff.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", "1610612738").
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        league_id (str, optional): The league ID (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".


    Returns:
        str: JSON string containing detailed team data including info, ranks, roster, and coaches for the specified season.
    """
    logger.debug(f"Tool 'get_team_info_and_roster' called for '{team_identifier}', season '{season}', type '{season_type}', league '{league_id}'")
    # Pass all relevant parameters to the logic function
    result = fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        league_id=league_id
    )
    return result

@tool
def get_team_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base, # Corrected default to match nba_api
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba,
    as_dataframe: bool = False
) -> str:
    """
    Fetches comprehensive team statistics for a given season, including current season dashboard stats
    and historical year-by-year performance, with various filtering options.
    Provides DataFrame output capabilities.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID.
        season (str, optional): The NBA season for dashboard stats (e.g., "2023-24"). Defaults to current season.
        season_type (str, optional): The type of season for dashboard and historical stats.
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        per_mode (str, optional): The statistical mode for dashboard stats (e.g., "PerGame", "Totals").
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`. Defaults to "PerGame".
        measure_type (str, optional): The category of stats for dashboard (e.g., "Base", "Advanced").
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`. Defaults to "Base".
        opponent_team_id (int, optional): Filter dashboard stats against a specific opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date for filtering dashboard games (YYYY-MM-DD).
        date_to (Optional[str], optional): End date for filtering dashboard games (YYYY-MM-DD).
        league_id (str, optional): The league ID for historical stats (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing team statistics, including 'current_season_dashboard_stats' and 'historical_year_by_year_stats'.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_team_stats' called for '{team_identifier}', season '{season}', measure '{measure_type}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_team_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            measure_type=measure_type,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to,
            league_id=league_id,
            return_dataframe=True
        )

        # Parse the original JSON response
        try:
            data = json.loads(json_response)
        except json.JSONDecodeError as jde:
            logger.error("Failed to parse team-stats JSON: %s", jde, exc_info=True)
            return json_response  # propagate raw response up-stream

        # Add DataFrame info
        df_info = {
            "message": "Team statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean team name for filename
                team_name = data.get("team_name", team_identifier)
                clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                # Clean measure type for filename
                clean_measure_type = measure_type.replace(" ", "_").lower()

                if key == "dashboard":
                    csv_path = f"backend/cache/team_general/{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{clean_measure_type}_dashboard.csv"
                else:  # historical
                    csv_path = f"backend/cache/team_general/{clean_team_name}_all_seasons_{clean_season_type}_pergame_base_historical.csv"

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
        return fetch_team_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            measure_type=measure_type,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to,
            league_id=league_id
        )

@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    as_dataframe: bool = False
) -> str:
    """
    Fetches team passing statistics, detailing passes made and received among players
    for a specific team and season using the TeamDashPtPass endpoint.
    Provides DataFrame output capabilities.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", "1610612738").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeSimple`.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with team passing stats, including 'passes_made' and 'passes_received' lists.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_team_passing_stats' called for '{team_identifier}', season '{season}', type '{season_type}', per_mode '{per_mode}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_team_passing_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Team passing statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean team name for filename
                team_name = data.get("team_name", team_identifier)
                clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                csv_path = f"backend/cache/team_passing/{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{key}.csv"

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
        return fetch_team_passing_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode
        )

@tool
def get_team_rebounding_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    as_dataframe: bool = False
) -> str:
    """
    Fetches team rebounding statistics, categorized by various factors like shot type,
    contest level, shot distance, and rebound distance, using the TeamDashPtReb endpoint.
    Provides DataFrame output capabilities.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", "1610612738").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeSimple`.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with team rebounding stats, including 'overall', 'by_shot_type', 'by_contest',
             'by_shot_distance', and 'by_rebound_distance' categories.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_team_rebounding_stats' called for '{team_identifier}', season '{season}', type '{season_type}', per_mode '{per_mode}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_team_rebounding_stats_logic(
            team_identifier=team_identifier,
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
            "message": "Team rebounding statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean team name for filename
                team_name = data.get("team_name", team_identifier)
                clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                csv_path = f"backend/cache/team_rebounding/{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{key}.csv"

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
        return fetch_team_rebounding_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to
        )

@tool
def get_team_shooting_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    as_dataframe: bool = False
) -> str:
    """
    Fetches team shooting statistics, categorized by various factors like shot clock,
    number of dribbles, defender distance, and touch time, using the TeamDashPtShots endpoint.
    Provides DataFrame output capabilities.

    Args:
        team_identifier (str): The team's name, abbreviation, or ID (e.g., "Boston Celtics", "BOS", "1610612738").
        season (str, optional): NBA season in 'YYYY-YY' format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeSimple`.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0 (all).
        date_from (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to (Optional[str], optional): End date filter (YYYY-MM-DD).
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with team shooting stats, including 'overall_shooting', 'general_shooting_splits',
             'by_shot_clock', 'by_dribble', 'by_defender_distance', and 'by_touch_time'.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_team_shooting_stats' called for '{team_identifier}', season '{season}', type '{season_type}', per_mode '{per_mode}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_team_shooting_stats_logic(
            team_identifier=team_identifier,
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
            "message": "Team shooting statistics have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean team name for filename
                team_name = data.get("team_name", team_identifier)
                clean_team_name = team_name.replace(" ", "_").replace(".", "").lower()

                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                # Clean per mode for filename
                clean_per_mode = per_mode.replace(" ", "_").lower()

                csv_path = f"backend/cache/team_shooting/{clean_team_name}_{season}_{clean_season_type}_{clean_per_mode}_{key}.csv"

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
        return fetch_team_shooting_stats_logic(
            team_identifier=team_identifier,
            season=season,
            season_type=season_type,
            per_mode=per_mode,
            opponent_team_id=opponent_team_id,
            date_from=date_from,
            date_to=date_to
        )