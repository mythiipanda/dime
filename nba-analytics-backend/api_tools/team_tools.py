import logging
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import teaminfocommon, commonteamroster
from nba_api.stats.library.parameters import LeagueID
import re
import json # Import json

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
CURRENT_SEASON = "2024-25"

# --- Helper Functions ---
def _validate_season_format(season: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}$", season))

def _find_team_id(team_identifier: str) -> int | None:
    logger.debug(f"Searching for team ID using identifier: '{team_identifier}'")
    team_info = teams.find_team_by_abbreviation(team_identifier.upper())
    if team_info:
        logger.info(f"Found team by abbreviation: {team_info['full_name']} (ID: {team_info['id']})")
        return team_info['id']
    team_list = teams.find_teams_by_full_name(team_identifier)
    if team_list:
        team_info = team_list[0]
        logger.info(f"Found team by full name: {team_info['full_name']} (ID: {team_info['id']})")
        return team_info['id']
    logger.warning(f"Team not found for identifier: '{team_identifier}'")
    return None

def _process_dataframe(df: pd.DataFrame | None, single_row: bool = True) -> list | dict | None:
    if df is None or df.empty:
        return {} if single_row else []
    try:
        records = df.to_dict(orient='records')
        processed_records = [
            {k: (v if pd.notna(v) else None) for k, v in row.items()}
            for row in records
        ]
        if single_row:
            return processed_records[0] if processed_records else {}
        else:
            return processed_records
    except Exception as e:
        logger.error(f"Error processing DataFrame: {e}", exc_info=True)
        return None

# --- Team Tool Logic Function (Returning JSON String) ---

def fetch_team_info_and_roster_logic(team_identifier: str, season: str = CURRENT_SEASON) -> str: # Return str (JSON)
    """Core logic to fetch team info and roster."""
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}")
    if not team_identifier or not team_identifier.strip(): return json.dumps({"error": "Team identifier cannot be empty."})
    if not season or not _validate_season_format(season): return json.dumps({"error": f"Invalid season format: {season}. Expected YYYY-YY."})

    try:
        team_id = _find_team_id(team_identifier)
        if team_id is None: return json.dumps({"error": f"Team '{team_identifier}' not found."})

        team_info_dict, team_ranks_dict, roster_list, coaches_list = {}, {}, [], []
        errors = []

        logger.debug(f"Fetching teaminfocommon for Team ID: {team_id}, Season: {season}")
        try:
            team_info_endpoint = teaminfocommon.TeamInfoCommon(team_id=team_id, season_nullable=season, league_id=LeagueID.nba, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"teaminfocommon API call successful for ID: {team_id}")
            team_info_dict = _process_dataframe(team_info_endpoint.team_info_common.get_data_frame(), single_row=True)
            team_ranks_dict = _process_dataframe(team_info_endpoint.team_season_ranks.get_data_frame(), single_row=True)
            if team_info_dict is None or team_ranks_dict is None:
                 errors.append("team info/ranks processing")
                 logger.error(f"DataFrame processing failed for team info/ranks, Team ID {team_id}")
        except Exception as api_error:
            logger.error(f"nba_api teaminfocommon failed for ID {team_id}: {api_error}", exc_info=True)
            errors.append("team info/ranks API")

        logger.debug(f"Fetching commonteamroster for Team ID: {team_id}, Season: {season}")
        try:
            roster_endpoint = commonteamroster.CommonTeamRoster(team_id=team_id, season=season, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonteamroster API call successful for ID: {team_id}")
            roster_list = _process_dataframe(roster_endpoint.common_team_roster.get_data_frame(), single_row=False)
            coaches_list = _process_dataframe(roster_endpoint.coaches.get_data_frame(), single_row=False)
            if roster_list is None or coaches_list is None:
                errors.append("roster/coaches processing")
                logger.error(f"DataFrame processing failed for roster/coaches, Team ID {team_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonteamroster failed for ID {team_id}, Season {season}: {api_error}", exc_info=True)
            errors.append("roster/coaches API")

        if not team_info_dict and not team_ranks_dict and not roster_list and not coaches_list:
             logger.error(f"All team data fetching failed for team ID {team_id}, Season {season}. Errors: {errors}")
             return json.dumps({"error": f"Failed to fetch any data for team '{team_identifier}' ({season}). Errors: {', '.join(errors)}."})

        result = {
            "team_info": team_info_dict or {},
            "team_ranks": team_ranks_dict or {},
            "roster": roster_list or [],
            "coaches": coaches_list or [],
            "fetch_errors": errors
        }
        logger.info(f"fetch_team_info_and_roster_logic completed for Team ID: {team_id}, Season: {season}")
        return json.dumps(result, default=str) # Return JSON string
    except Exception as e:
        logger.critical(f"Unexpected critical error in fetch_team_info_and_roster_logic for '{team_identifier}', Season {season}: {e}", exc_info=True)
        return json.dumps({"error": f"Unexpected error processing team info/roster request for {team_identifier} ({season}): {str(e)}"})