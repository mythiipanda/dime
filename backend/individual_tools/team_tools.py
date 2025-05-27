from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# Team specific stats logic functions
from ..api_tools.team_dash_lineups import fetch_team_lineups_logic
from ..api_tools.team_dash_pt_shots import fetch_team_dash_pt_shots_logic
from ..api_tools.league_dash_pt_team_defend import fetch_league_dash_pt_team_defend_logic
from ..api_tools.team_dashboard_shooting import fetch_team_dashboard_shooting_splits_logic
from ..api_tools.team_details import fetch_team_details_logic
from ..api_tools.team_estimated_metrics import fetch_team_estimated_metrics_logic
from ..api_tools.team_game_logs import fetch_team_game_logs_logic
from ..api_tools.team_general_stats import fetch_team_stats_logic
from ..api_tools.team_historical_leaders import fetch_team_historical_leaders_logic
from ..api_tools.team_history import fetch_common_team_years_logic
from ..api_tools.team_info_roster import fetch_team_info_and_roster_logic
from ..api_tools.team_passing_analytics import fetch_team_passing_stats_logic
from ..api_tools.team_player_dashboard import fetch_team_player_dashboard_logic
from ..api_tools.team_player_on_off_details import fetch_team_player_on_off_details_logic
from ..api_tools.teamplayeronoffsummary import fetch_teamplayeronoffsummary_logic
from ..api_tools.team_rebounding_tracking import fetch_team_rebounding_stats_logic
from ..api_tools.team_shooting_tracking import fetch_team_shooting_stats_logic
from ..api_tools.teamvsplayer import fetch_teamvsplayer_logic
from ..api_tools.franchise_history import fetch_franchise_history_logic
from ..api_tools.franchise_leaders import fetch_franchise_leaders_logic
from ..api_tools.franchise_players import fetch_franchise_players_logic

# Placeholder for utility functions that were likely part of the toolkit or a shared utils module
# You WILL need to define these or ensure they are correctly imported for the tools to work.
def find_team_id_or_error(identifier: str) -> Tuple[int, str]:
    # This is a placeholder. Implement actual team ID resolution logic.
    # Should return (team_id: int, team_abbreviation: str) or raise an error.
    logger.warning(f"[Placeholder] find_team_id_or_error called for {identifier}. Needs implementation.")
    if identifier.isdigit():
        return int(identifier), "UNK"
    # Simplified example, replace with actual lookup
    if identifier == "Los Angeles Lakers" or identifier == "LAL":
        return 1610612747, "LAL"
    raise ValueError(f"Could not resolve team identifier: {identifier}")

def format_response(error: Optional[str] = None, data: Optional[Dict] = None, **kwargs) -> str:
    # This is a placeholder. Implement actual response formatting.
    import json
    if error:
        return json.dumps({"status": "error", "message": error, **kwargs})
    return json.dumps({"status": "success", "data": data, **kwargs})


from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense,
    PerModeSimple, PerModeTime, DefenseCategory
)

@tool
def get_team_lineup_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.totals,
    group_quantity: int = 5,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team lineup statistics.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        measure_type (str, optional): Statistical category. Defaults to "Base".
        per_mode (str, optional): Per mode for stats. Defaults to "Totals".
        group_quantity (int, optional): Number of players in lineup (2-5). Defaults to 5.
        return_dataframe (bool, optional): If True, returns (JSON, {'Lineups': df, 'Overall': df}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_lineup_stats called for {team_identifier}, season {season}")
    return fetch_team_lineups_logic(
        team_identifier=team_identifier, # Assuming logic function can handle identifier or uses a resolver
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        group_quantity=group_quantity,
        return_dataframe=return_dataframe
    )

@tool
def get_team_player_tracking_shot_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    per_mode_simple: str = PerModeSimple.totals,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team-level player tracking shot statistics.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): Season. Defaults to current NBA season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        per_mode_simple (str, optional): Per mode. Defaults to "Totals".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'TeamPtShot': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_player_tracking_shot_stats called for {team_identifier}, season {season}")
    try:
        team_id_val, _ = find_team_id_or_error(team_identifier)
    except Exception as e:
        logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    return fetch_team_dash_pt_shots_logic(
        team_id=str(team_id_val),
        season=season,
        season_type_all_star=season_type_all_star,
        per_mode_simple=per_mode_simple,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_player_tracking_defense_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    defense_category: str = DefenseCategory.overall,
    league_id: str = LeagueID.nba,
    team_identifier_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches defensive team tracking statistics. Can be league-wide or filtered for a specific team.
    Args:
        season (str, optional): Season YYYY-YY. Defaults to current.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        defense_category (str, optional): Defense category. Defaults to "Overall".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        team_identifier_nullable (Optional[str], optional): Team identifier to filter for. If None, league-wide.
        return_dataframe (bool, optional): If True, returns (JSON, {'pt_team_defend': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_player_tracking_defense_stats for season {season}, team: {team_identifier_nullable or 'League-wide'}")
    team_id_val_nullable = None
    if team_identifier_nullable:
        try:
            team_id_val_nullable, _ = find_team_id_or_error(team_identifier_nullable)
        except Exception as e:
            logger.warning(f"Could not resolve team_identifier '{team_identifier_nullable}' for defense stats: {e}")
            # Optionally, can return error here if team_identifier must be valid
            # error_response = format_response(error=str(e))
            # if return_dataframe: return error_response, {}
            # return error_response
    return fetch_league_dash_pt_team_defend_logic(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        defense_category=defense_category,
        league_id=league_id,
        team_id_nullable=str(team_id_val_nullable) if team_id_val_nullable else None,
        return_dataframe=return_dataframe
    )

@tool
def get_team_dashboard_shooting_splits(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "Totals", # Toolkit had "Totals", nba_api default PerModeDetailed.per_game
    measure_type: str = "Base", # Toolkit had "Base", nba_api default MeasureTypeDetailedDefense.base
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team dashboard statistics for shooting splits.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_dashboard_shooting_splits for {team_identifier}, season {season}")
    # Assuming fetch_team_dashboard_shooting_splits_logic can take team_identifier
    return fetch_team_dashboard_shooting_splits_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_team_details(
    team_id: str, # Explicitly team_id as per original toolkit note
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed information for a specific team, including background, history, and social presence.
    Args:
        team_id (str): The ID of the team.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_details for team_id {team_id}")
    return fetch_team_details_logic(
        team_id=team_id,
        return_dataframe=return_dataframe
    )

@tool
def get_league_team_estimated_metrics(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches estimated metrics (OffRtg, DefRtg, NetRtg, etc.) for all teams in the league.
    Args:
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'team_metrics': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_estimated_metrics for season {season}")
    return fetch_team_estimated_metrics_logic(
        season=season,
        season_type=season_type,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_game_logs(
    team_identifier: str, # Changed from team_id to team_identifier for consistency
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_nullable: Optional[str] = "Regular Season", # parameter in logic is season_type_nullable
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    # Add other parameters from TeamGameLogs endpoint as needed, e.g., league_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches game logs for a specific team.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): Season. Defaults to current season.
        season_type_nullable (Optional[str], optional): Season type. Defaults to "Regular Season".
        date_from_nullable (Optional[str], optional): Start date filter.
        date_to_nullable (Optional[str], optional): End date filter.
        return_dataframe (bool, optional): If True, returns (JSON, {'game_logs': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_game_logs for {team_identifier}, season {season}")
    # Logic might require team_id, team_identifier passed for now.
    # Ensure fetch_team_game_logs_logic can handle team_identifier or resolve it.
    return fetch_team_game_logs_logic(
        team_identifier=team_identifier,
        season=season,
        season_type_nullable=season_type_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_team_general_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base,
    # ... other params from original logic like plus_minus, rank etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches general statistics for a team (e.g., W-L, PTS, REB, AST).
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_general_stats for {team_identifier}, season {season}")
    return fetch_team_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        return_dataframe=return_dataframe
    )

@tool
def get_team_historical_leaders(
    team_identifier: str, # team_id is used in logic but identifier is more user friendly
    season_id: str, # e.g., "22022" for 2022-23 season (NBA API format)
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches historical leaders for a specific team in a given season for various statistical categories.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season_id (str): Season ID in NNNNN format (e.g., 22023 for 2023-24).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'leaders': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_historical_leaders for {team_identifier}, season_id {season_id}")
    # Logic will likely require team_id from team_identifier
    return fetch_team_historical_leaders_logic(
        team_identifier=team_identifier,
        season_id=season_id,
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_common_team_years(
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches common team year information, such as seasons teams participated in.
    This is typically league-wide information about team history.
    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'team_years': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_common_team_years for league {league_id}")
    return fetch_common_team_years_logic(
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_info_and_roster(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular, # Parameter name in logic is season_type_all_star
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches general team information and current roster for a specific season.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'team_info': df, 'roster': df}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_info_and_roster for {team_identifier}, season {season}")
    return fetch_team_info_and_roster_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type, # Correct parameter name
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_team_passing_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    # ... other params like date_from, date_to, opponent_team_id etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team passing statistics.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        return_dataframe (bool, optional): If True, returns (JSON, {'passing_stats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_passing_stats for {team_identifier}, season {season}")
    return fetch_team_passing_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_team_player_dashboard_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    # ... other params from TeamPlayerDashboard endpoint
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches player statistics for players on a specific team (team's player dashboard).
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_player_dashboard_stats for {team_identifier}, season {season}")
    return fetch_team_player_dashboard_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        return_dataframe=return_dataframe
    )

@tool
def get_team_player_on_off_details(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    # ... other params from TeamPlayerOnOffDetails endpoint
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed on/off court statistics for players on a specific team.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_player_on_off_details for {team_identifier}, season {season}")
    return fetch_team_player_on_off_details_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        return_dataframe=return_dataframe
    )

@tool
def get_team_player_on_off_summary(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular, # Logic param is season_type_all_star
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    # ... other params
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches summary on/off court statistics for players on a specific team.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        per_mode_detailed (str, optional): Statistical mode. Defaults to "Totals".
        measure_type_detailed_defense (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_player_on_off_summary for {team_identifier}, season {season}")
    return fetch_teamplayeronoffsummary_logic(
        team_identifier=team_identifier,
        season=season,
        season_type_all_star=season_type_all_star,
        per_mode_detailed=per_mode_detailed,
        measure_type_detailed_defense=measure_type_detailed_defense,
        return_dataframe=return_dataframe
    )

@tool
def get_team_rebounding_tracking_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    # ... other params
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team rebounding tracking statistics.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        return_dataframe (bool, optional): If True, returns (JSON, {'rebounding_stats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_team_rebounding_tracking_stats for {team_identifier}, season {season}")
    return fetch_team_rebounding_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_team_shooting_tracking_stats(
    team_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    # ... other params
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches team shooting tracking statistics.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_shooting_tracking_stats for {team_identifier}, season {season}")
    return fetch_team_shooting_stats_logic(
        team_identifier=team_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        return_dataframe=return_dataframe
    )

@tool
def get_team_vs_player_stats(
    team_identifier: str,
    vs_player_identifier: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.totals,
    measure_type: str = MeasureTypeDetailedDefense.base,
    # ... other params like player_identifier for on-off impact within the team
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches detailed statistics for a team when a specific opposing player is on/off the court.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team.
        vs_player_identifier (str): Name or ID of the opposing player.
        season (str, optional): NBA season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
        measure_type (str, optional): Type of stats. Defaults to "Base".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_team_vs_player_stats for team {team_identifier} vs player {vs_player_identifier}")
    return fetch_teamvsplayer_logic(
        team_identifier=team_identifier,
        vs_player_identifier=vs_player_identifier,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        return_dataframe=return_dataframe
    )

@tool
def get_league_franchise_history(
    league_id: str = "00",
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches historical data for all franchises in a league.
    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'franchise_history': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_franchise_history for league_id {league_id}")
    return fetch_franchise_history_logic(
        league_id=league_id,
        return_dataframe=return_dataframe
    )

@tool
def get_franchise_leaders(
    team_identifier: str, # Toolkit note: Team ID is required.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches all-time leaders for a specific franchise.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team. Will be resolved to Team ID.
        return_dataframe (bool, optional): If True, returns (JSON, {'franchise_leaders': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_franchise_leaders for {team_identifier}")
    try:
        team_id_val, _ = find_team_id_or_error(team_identifier)
    except Exception as e:
        logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    return fetch_franchise_leaders_logic(
        team_id=str(team_id_val), # Logic requires team_id
        return_dataframe=return_dataframe
    )

@tool
def get_franchise_players(
    team_identifier: str, # Toolkit note: Team ID is required.
    league_id: str = "00", # Parameters from FranchisePlayers endpoint
    per_mode_detailed: str = PerModeDetailed.totals,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches all players who have played for a specific franchise, with their career stats for that franchise.
    Args:
        team_identifier (str): Name, abbreviation, or ID of the team. Will be resolved to Team ID.
        league_id (str, optional): League ID. Defaults to "00".
        per_mode_detailed (str, optional): Statistical mode. Defaults to "Totals".
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        return_dataframe (bool, optional): If True, returns (JSON, {'franchise_players': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_franchise_players for {team_identifier}")
    try:
        team_id_val, _ = find_team_id_or_error(team_identifier)
    except Exception as e:
        logger.error(f"Error finding team ID for '{team_identifier}': {e}", exc_info=True)
        error_response = format_response(error=str(e))
        if return_dataframe:
            return error_response, {}
        return error_response
    return fetch_franchise_players_logic(
        team_id=str(team_id_val), # Logic requires team_id
        league_id=league_id,
        per_mode_detailed=per_mode_detailed,
        season_type_all_star=season_type_all_star,
        return_dataframe=return_dataframe
    )