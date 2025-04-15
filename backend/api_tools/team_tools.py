import logging
import json
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import teaminfocommon, commonteamroster, teamdashboardbygeneralsplits, teamdashptpass, teamyearbyyearstats
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar

from backend.config import DEFAULT_TIMEOUT, CURRENT_SEASON, ErrorMessages as Errors
from backend.api_tools.utils import _process_dataframe, _validate_season_format, format_response

logger = logging.getLogger(__name__)

def _find_team_id(team_identifier: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Finds a team's ID and name from abbreviation or full name.
    
    Returns:
        Tuple of (team_id, team_name) or (None, None) if not found
    """
    logger.debug(f"Searching for team ID using identifier: '{team_identifier}'")

    # 1. Check if the identifier is potentially an ID (numeric string)
    # 1. Check if the identifier is potentially an ID (numeric string)
    if isinstance(team_identifier, str) and team_identifier.isdigit():
        try:
            team_id_int = int(team_identifier)
            # Correct way to find by ID: iterate through get_teams()
            all_teams_list = teams.get_teams()
            for team in all_teams_list:
                if team['id'] == team_id_int:
                    logger.info(f"Found team by ID: {team['full_name']} (ID: {team['id']})")
                    return team['id'], team['full_name']
        except ValueError:
             # Should not happen if isdigit() is true, but good practice
             pass

    # 2. Check by abbreviation
    team_info_by_abbr = teams.find_team_by_abbreviation(team_identifier.upper())
    if team_info_by_abbr:
        logger.info(f"Found team by abbreviation: {team_info_by_abbr['full_name']} (ID: {team_info_by_abbr['id']})")
        return team_info_by_abbr['id'], team_info_by_abbr['full_name']

    # 3. Check by full name
    team_list_by_name = teams.find_teams_by_full_name(team_identifier)
    if team_list_by_name:
        team_info = team_list_by_name[0]
        logger.info(f"Found team by full name: {team_info['full_name']} (ID: {team_info['id']})")
        return team_info['id'], team_info['full_name']

    # 4. Check by nickname (case-insensitive)
    all_teams = teams.get_teams()
    identifier_lower = team_identifier.lower()
    for team in all_teams:
        if team['nickname'].lower() == identifier_lower:
            logger.info(f"Found team by nickname: {team['full_name']} (ID: {team['id']})")
            return team['id'], team['full_name']


    logger.warning(f"Team not found for identifier: '{team_identifier}'")
    return None, None

# Removed unused find_team_by_name function

def fetch_team_info_and_roster_logic(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches team info, ranks, roster, and coaches.
    Returns JSON string with essential information.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}")
    if not team_identifier or not team_identifier.strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    try:
        team_id, team_name = _find_team_id(team_identifier)
        if team_id is None:
            return format_response(error=Errors.TEAM_NOT_FOUND.format(identifier=team_identifier))

        team_info_dict, team_ranks_dict, roster_list, coaches_list = {}, {}, [], []
        errors: List[str] = []

        logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}")
        try:
            team_info_endpoint = teaminfocommon.TeamInfoCommon(
                team_id=team_id,
                season_nullable=season,
                league_id=LeagueID.nba,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"teaminfocommon API call successful for ID: {team_id}")
            team_info_dict = _process_dataframe(team_info_endpoint.team_info_common.get_data_frame(), single_row=True)
            team_ranks_dict = _process_dataframe(team_info_endpoint.team_season_ranks.get_data_frame(), single_row=True)
            if team_info_dict is None or team_ranks_dict is None:
                errors.append("team info/ranks processing")
                logger.error(Errors.TEAM_PROCESSING.format(data_type="team info/ranks", identifier=team_id))
        except Exception as api_error:
            logger.error(Errors.TEAM_API.format(data_type="teaminfocommon", identifier=team_id, error=api_error), exc_info=True)
            errors.append("team info/ranks API")

        logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}")
        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"commonteamroster API call successful for ID: {team_id}")
            roster_list = _process_dataframe(roster_endpoint.common_team_roster.get_data_frame(), single_row=False)
            coaches_list = _process_dataframe(roster_endpoint.coaches.get_data_frame(), single_row=False)
            if roster_list is None or coaches_list is None:
                errors.append("roster/coaches processing")
                logger.error(Errors.TEAM_PROCESSING.format(data_type="roster/coaches", identifier=team_id))
        except Exception as api_error:
            logger.error(Errors.TEAM_API.format(data_type="commonteamroster", identifier=team_id, error=api_error), exc_info=True)
            errors.append("roster/coaches API")

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list:
            error_msg = Errors.TEAM_ALL_FAILED.format(identifier=team_identifier, season=season, errors=', '.join(errors))
            logger.error(error_msg)
            return format_response(error=error_msg)

        # Process team info into a more compact format
        compact_team_info = {}
        if team_info_dict:
            key_fields = ["TEAM_NAME", "TEAM_CITY", "TEAM_ABBREVIATION", "TEAM_CONFERENCE", "TEAM_DIVISION", 
                         "W", "L", "PCT", "CONF_RANK", "DIV_RANK", "PTS_PG", "OPP_PTS_PG", "ARENA_NAME", "HEAD_COACH"]
            compact_team_info = {k: team_info_dict.get(k) for k in key_fields if k in team_info_dict}
        
        # Process team ranks into a more compact format
        compact_team_ranks = {}
        if team_ranks_dict:
            rank_fields = ["MIN_RANK", "PTS_RANK", "REB_RANK", "AST_RANK", "STL_RANK", "BLK_RANK", 
                          "FG_PCT_RANK", "FT_PCT_RANK", "FG3_PCT_RANK", "NET_RATING_RANK"]
            compact_team_ranks = {k: team_ranks_dict.get(k) for k in rank_fields if k in team_ranks_dict}
            
        # Process roster into a more compact format
        compact_roster = []
        if roster_list:
            for player in roster_list:
                compact_player = {
                    "PLAYER_ID": player.get("PLAYER_ID"),
                    "PLAYER": player.get("PLAYER"),
                    "JERSEY": player.get("NUM"),
                    "POSITION": player.get("POSITION"),
                    "HEIGHT": player.get("HEIGHT"),
                    "WEIGHT": player.get("WEIGHT"),
                    "AGE": player.get("AGE"),
                    "EXPERIENCE": player.get("EXP"),
                    "DRAFT_YEAR": player.get("DRAFT_YEAR")
                }
                compact_roster.append(compact_player)
                
        # Process coaches into a more compact format
        compact_coaches = []
        if coaches_list:
            for coach in coaches_list:
                compact_coach = {
                    "COACH_NAME": coach.get("COACH_NAME"),
                    "COACH_TYPE": coach.get("COACH_TYPE"),
                    "COACH_TITLE": coach.get("COACH_TITLE")
                }
                compact_coaches.append(compact_coach)

        # Create the final compact result
        result = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "info": compact_team_info,
            "ranks": compact_team_ranks,
            "roster": compact_roster,
            "coaches": compact_coaches
        }
        
        if errors:
            result["errors"] = errors
            
        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")
        return format_response(result)
    except Exception as e:
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)

def fetch_team_stats_logic(team_identifier: str, season: str = CURRENT_SEASON) -> str:
    """
    Fetches comprehensive team statistics.
    
    Args:
        team_identifier (str): Team name, abbreviation, or ID
        season (str): NBA season in format 'YYYY-YY'
        
    Returns:
        str: JSON string containing team statistics or error message
    """
    logger.info(f"Executing fetch_team_stats_logic for: '{team_identifier}', Season: {season}")
    
    if not team_identifier or not team_identifier.strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    try:
        team_id, team_name = _find_team_id(team_identifier)
        if team_id is None:
            return format_response(error=Errors.TEAM_NOT_FOUND.format(identifier=team_identifier))

        logger.debug(f"Fetching team dashboard stats for Team ID: {team_id}, Season: {season}")
        try:
            dashboard = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
                team_id=team_id,
                season=season,
                timeout=DEFAULT_TIMEOUT
            )
            
            # Get overall team stats
            overall_stats = _process_dataframe(dashboard.overall_team_dashboard.get_data_frame(), single_row=True)
            if not overall_stats:
                error_msg = Errors.TEAM_PROCESSING.format(data_type="dashboard stats", identifier=team_id)
                logger.error(error_msg)
                return format_response(error=error_msg)

            # Get historical stats
            historical_stats = []
            try:
                yearly_stats = teamyearbyyearstats.TeamYearByYearStats(
                    team_id=team_id,
                    per_mode_simple="PerGame",
                    timeout=DEFAULT_TIMEOUT
                )
                historical_df = yearly_stats.get_data_frames()[0]
                historical_stats = _process_dataframe(historical_df, single_row=False)
            except Exception as hist_error:
                logger.warning(f"Could not fetch historical stats: {str(hist_error)}")

            # Create compact result with key statistics
            key_stats = [
                "GP", "W", "L", "W_PCT", "MIN", "FGM", "FGA", "FG_PCT", 
                "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
                "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK",
                "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS"
            ]
            
            compact_stats = {k: overall_stats.get(k) for k in key_stats if k in overall_stats}
            
            result = {
                "team_id": team_id,
                "team_name": team_name,
                "season": season,
                "current_stats": compact_stats,
                "historical_stats": historical_stats
            }
            
            logger.info(f"fetch_team_stats_logic completed for Team ID: {team_id}, Season: {season}")
            return format_response(result)
            
        except Exception as api_error:
            error_msg = Errors.TEAM_API.format(data_type="team dashboard", identifier=team_id, error=str(api_error))
            logger.error(error_msg, exc_info=True)
            return format_response(error=error_msg)
            
    except Exception as e:
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_identifier, season=season, error=str(e))
        logger.critical(error_msg, exc_info=True)
        return format_response(error=error_msg)

def fetch_team_passing_stats_logic(team_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches team passing statistics.
    
    Args:
        team_name (str): The name of the team to fetch stats for
        season (str): The season to fetch stats for (e.g., '2023-24')
        season_type (str): The type of season (regular, playoffs, etc.)
        
    Returns:
        str: JSON string containing team passing statistics or error message
    """
    logger.info(f"Executing fetch_team_passing_stats_logic for: '{team_name}', Season: {season}")
    
    if not team_name or not team_name.strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    
    try:
        # Find team ID
        team_id, team_full_name = _find_team_id(team_name)
        if team_id is None:
            return format_response(error=Errors.TEAM_NOT_FOUND.format(identifier=team_name))
        
        # Get team passing stats
        try:
            passing_stats = teamdashptpass.TeamDashPtPass(
                team_id=team_id,
                season=season,
                season_type_all_star=season_type,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"teamdashptpass API call successful for ID: {team_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api teamdashptpass failed for ID {team_id}, Season {season}: {api_error}", exc_info=True)
            return format_response(error=Errors.TEAM_API.format(data_type="teamdashptpass", identifier=team_id, error=str(api_error)))
            
        passes_made = _process_dataframe(passing_stats.passes_made.get_data_frame(), single_row=False)
        passes_received = _process_dataframe(passing_stats.passes_received.get_data_frame(), single_row=False)
        
        if passes_made is None or passes_received is None:
            logger.error(f"DataFrame processing failed for team passing stats of {team_full_name} ({season}).")
            return format_response(error=Errors.TEAM_PROCESSING.format(data_type="team passing stats", identifier=team_id))
        
        # Process passes made into more compact format
        compact_passes_made = []
        if passes_made:
            for pass_data in passes_made:
                compact_pass = {
                    "PASS_FROM": pass_data.get("PASS_FROM"),
                    "PASS_TO": pass_data.get("PASS_TO"),
                    "PASS": pass_data.get("PASS"),
                    "AST": pass_data.get("AST"),
                    "FGM": pass_data.get("FGM"),
                    "FGA": pass_data.get("FGA"),
                    "FG_PCT": pass_data.get("FG_PCT")
                }
                compact_passes_made.append(compact_pass)
                
        # Process passes received into more compact format
        compact_passes_received = []
        if passes_received:
            for pass_data in passes_received:
                compact_pass = {
                    "PASS_FROM": pass_data.get("PASS_FROM"),
                    "PASS_TO": pass_data.get("PASS_TO"),
                    "PASS": pass_data.get("PASS"),
                    "AST": pass_data.get("AST"),
                    "FGM": pass_data.get("FGM"),
                    "FGA": pass_data.get("FGA"),
                    "FG_PCT": pass_data.get("FG_PCT")
                }
                compact_passes_received.append(compact_pass)
        
        # Combine results
        result = {
            "team_name": team_full_name,
            "team_id": team_id,
            "season": season,
            "season_type": season_type,
            "passes_made": compact_passes_made,
            "passes_received": compact_passes_received
        }
        
        logger.info(f"fetch_team_passing_stats_logic completed for '{team_full_name}'")
        return format_response(result)
        
    except Exception as e:
        error_msg = Errors.TEAM_UNEXPECTED.format(identifier=team_name, season=season, error=str(e))
        logger.critical(f"Unexpected error in fetch_team_passing_stats_logic for '{team_name}': {e}", exc_info=True)
        return format_response(error=error_msg)