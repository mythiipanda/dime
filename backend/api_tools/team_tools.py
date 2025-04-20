import logging
import json
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import (
    teaminfocommon,
    commonteamroster,
    teamdashboardbygeneralsplits,
    teamdashptpass,
    teamyearbyyearstats,
    leaguedashlineups
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    MeasureTypeDetailedDefense,
    PerModeDetailed
)

from backend.config import DEFAULT_TIMEOUT, CURRENT_SEASON, Errors
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

def fetch_team_info_and_roster_logic(team_identifier: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular, league_id: str = LeagueID.nba) -> str:
    """
    Fetches team info, ranks, roster, and coaches.
    Returns JSON string with essential information.
    """
    logger.info(f"Executing fetch_team_info_and_roster_logic for: '{team_identifier}', Season: {season}, Type: {season_type}, League: {league_id}")
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
                league_id=league_id,
                season_type_nullable=season_type,
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
                league_id_nullable=league_id,
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

        # Process dataframes into compact dictionaries/lists using pandas
        compact_team_info = team_info_dict if team_info_dict else {}
        compact_team_ranks = team_ranks_dict if team_ranks_dict else {}
        
        # Define desired columns and rename mapping for roster
        roster_cols = {
            "PLAYER_ID": "PLAYER_ID", "PLAYER": "PLAYER", "NUM": "JERSEY",
            "POSITION": "POSITION", "HEIGHT": "HEIGHT", "WEIGHT": "WEIGHT",
            "AGE": "AGE", "EXP": "EXPERIENCE", "DRAFT_YEAR": "DRAFT_YEAR"
        }
        compact_roster = []
        if roster_list:
            roster_df = pd.DataFrame(roster_list)
            # Select and rename columns, then convert to list of dicts
            compact_roster = roster_df.filter(items=roster_cols.keys()).rename(columns=roster_cols).to_dict('records')

        # Define desired columns and rename mapping for coaches
        coach_cols = {"COACH_NAME": "COACH_NAME", "COACH_TYPE": "COACH_TYPE", "COACH_TITLE": "COACH_TITLE"}
        compact_coaches = []
        if coaches_list:
            coach_df = pd.DataFrame(coaches_list)
            compact_coaches = coach_df.filter(items=coach_cols.keys()).rename(columns=coach_cols).to_dict('records')

        # Create the final compact result
        result = {
            "team_id": team_id,
            "team_name": team_name,
            "season": season,
            "season_type": season_type,
            "league_id": league_id,
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

def fetch_team_stats_logic(
    team_identifier: str, 
    season: str = CURRENT_SEASON, 
    season_type: str = SeasonTypeAllStar.regular, 
    per_mode: str = PerModeDetailed.per_game, 
    measure_type: str = MeasureTypeDetailedDefense.base, 
    opponent_team_id: int = 0, 
    date_from: Optional[str] = None, 
    date_to: Optional[str] = None,
    league_id: str = LeagueID.nba
) -> str:
    """
    Fetches comprehensive team statistics (current season dashboard and year-by-year).
    
    Args:
        team_identifier (str): Team name, abbreviation, or ID.
        season (str): NBA season in format 'YYYY-YY' for current stats.
        season_type (str): Season type (Regular Season, Playoffs, etc.).
        per_mode (str): Per mode for stats (PerGame, Totals, etc.).
        measure_type (str): Measure type for dashboard stats (Base, Advanced, etc.).
        opponent_team_id (int, optional): Filter by opponent team ID for dashboard stats.
        date_from (str, optional): Start date filter for dashboard stats.
        date_to (str, optional): End date filter for dashboard stats.
        league_id (str): League ID for historical stats (NBA, WNBA, G-League).
        
    Returns:
        str: JSON string containing team statistics or error message.
    """
    logger.info(
        f"Executing fetch_team_stats_logic for: '{team_identifier}', Season: {season}, Type: {season_type}, "
        f"PerMode: {per_mode}, Measure: {measure_type}, Opp: {opponent_team_id}, League: {league_id}"
    )
    
    if not team_identifier or not team_identifier.strip():
        return format_response(error=Errors.TEAM_IDENTIFIER_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    try:
        team_id, team_name = _find_team_id(team_identifier)
        if team_id is None:
            return format_response(error=Errors.TEAM_NOT_FOUND.format(identifier=team_identifier))

        logger.debug(f"Fetching team dashboard stats for Team ID: {team_id}, Season: {season}, Filters applied.")
        try:
            dashboard = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
                team_id=team_id,
                season=season,
                season_type_all_star=season_type,
                per_mode_detailed=per_mode,
                measure_type_detailed_defense=measure_type,
                opponent_team_id=opponent_team_id,
                date_from_nullable=date_from,
                date_to_nullable=date_to,
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
                    league_id_nullable=league_id,
                    season_type_all_star=season_type,
                    per_mode_simple=per_mode,
                    timeout=DEFAULT_TIMEOUT
                )
                historical_df = yearly_stats.get_data_frames()[0]
                historical_stats = _process_dataframe(historical_df, single_row=False)
            except Exception as hist_error:
                logger.warning(f"Could not fetch historical stats: {str(hist_error)}")

            # Create compact result using the overall_stats dictionary directly
            # (assuming _process_dataframe already returns a suitable dict)
            compact_stats = overall_stats if overall_stats else {}
            
            result = {
                "team_id": team_id,
                "team_name": team_name,
                "parameters": {
                    "season": season,
                    "season_type": season_type,
                    "per_mode": per_mode,
                    "measure_type": measure_type,
                    "opponent_team_id": opponent_team_id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "league_id": league_id
                },
                "current_stats": compact_stats,
                "historical_stats": historical_stats or []
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

def fetch_team_lineups_logic(
    team_id: Optional[int] = None,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base,
    month: int = 0,
    date_from: str = None,
    date_to: str = None,
    opponent_team_id: int = 0,
    vs_conference: str = None,
    vs_division: str = None,
    game_segment: str = None,
    period: int = 0,
    last_n_games: int = 0
) -> str:
    """
    Fetches lineup statistics, optionally filtered by various parameters.
    
    Args:
        team_id: Optional NBA team ID. If None, returns all team lineups.
        season: Season identifier (e.g., "2023-24")
        season_type: Type of season (regular, playoffs, etc.)
        per_mode: Per game, per possession, etc.
        measure_type: Type of metrics to return
        month: Filter by month (0 for all)
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        opponent_team_id: Filter by opponent (0 for all)
        vs_conference: Filter by conference
        vs_division: Filter by division
        game_segment: Filter by game segment
        period: Filter by period (0 for all)
        last_n_games: Filter by last N games (0 for all)
        
    Returns:
        str: JSON string with lineup statistics
    """
    logger.info(f"Executing fetch_team_lineups_logic for season {season}")
    
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    # Validate season_type
    valid_season_types = [getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)]
    if season_type not in valid_season_types:
        logger.error(f"Invalid season_type '{season_type}' provided.")
        return format_response(error=f"Invalid season_type: '{season_type}'. Valid options: {valid_season_types}")

    # Validate per_mode
    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
        logger.error(f"Invalid per_mode '{per_mode}' provided.")
        return format_response(error=f"Invalid per_mode: '{per_mode}'. Valid options: {valid_per_modes}")

    # Validate measure_type
    valid_measure_types = [getattr(MeasureTypeDetailedDefense, attr) for attr in dir(MeasureTypeDetailedDefense) if not attr.startswith('_') and isinstance(getattr(MeasureTypeDetailedDefense, attr), str)]
    if measure_type not in valid_measure_types:
        logger.error(f"Invalid measure_type '{measure_type}' provided.")
        return format_response(error=f"Invalid measure_type: '{measure_type}'. Valid options: {valid_measure_types}")

    # Validate month (0 is valid for all months)
    if not isinstance(month, int) or month < 0 or month > 12:
        logger.error(f"Invalid month '{month}' provided.")
        return format_response(error=f"Invalid month: '{month}'. Must be an integer between 0 and 12.")

    try:
        logger.debug(f"Fetching lineup stats for season {season}")
        lineups = leaguedashlineups.LeagueDashLineups(
            team_id_nullable=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type,
            month=month,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            opponent_team_id=opponent_team_id,
            vs_conference_nullable=vs_conference,
            vs_division_nullable=vs_division,
            game_segment_nullable=game_segment,
            period=period,
            last_n_games=last_n_games,
            timeout=DEFAULT_TIMEOUT
        )
        
        lineups_df = lineups.get_data_frames()[0]
        if lineups_df.empty:
            logger.error(f"No lineup stats found for given parameters")
            return format_response(error="No lineup statistics available for the specified filters")

        # If no specific team is requested, limit the number of lineups returned
        if team_id is None:
             logger.info(f"Limiting league-wide lineup stats to the top 200 lineups.")
             lineups_df = lineups_df.head(200) # Limit to the first 200 rows
        
        # Process lineup statistics
        lineup_stats = []
        for _, row in lineups_df.iterrows():
            lineup = {
                "group_id": row.get("GROUP_ID"),
                "group_name": row.get("GROUP_NAME"),
                "players": [
                    player.strip() for player in str(row.get("GROUP_NAME")).split(" - ")
                ],
                "games_played": int(row.get("GP", 0)),
                "minutes": float(row.get("MIN", 0)),
                "offensive_stats": {
                    "points": float(row.get("PTS", 0)),
                    "field_goals": {
                        "made": float(row.get("FGM", 0)),
                        "attempts": float(row.get("FGA", 0)),
                        "pct": float(row.get("FG_PCT", 0))
                    },
                    "three_points": {
                        "made": float(row.get("FG3M", 0)),
                        "attempts": float(row.get("FG3A", 0)),
                        "pct": float(row.get("FG3_PCT", 0))
                    },
                    "free_throws": {
                        "made": float(row.get("FTM", 0)),
                        "attempts": float(row.get("FTA", 0)),
                        "pct": float(row.get("FT_PCT", 0))
                    },
                    "assists": float(row.get("AST", 0)),
                    "turnovers": float(row.get("TOV", 0))
                },
                "defensive_stats": {
                    "rebounds": {
                        "offensive": float(row.get("OREB", 0)),
                        "defensive": float(row.get("DREB", 0)),
                        "total": float(row.get("REB", 0))
                    },
                    "steals": float(row.get("STL", 0)),
                    "blocks": float(row.get("BLK", 0))
                },
                "plus_minus": float(row.get("PLUS_MINUS", 0)),
                "advanced_stats": {
                    "offensive_rating": float(row.get("OFF_RATING", 0)),
                    "defensive_rating": float(row.get("DEF_RATING", 0)),
                    "net_rating": float(row.get("NET_RATING", 0)),
                    "pace": float(row.get("PACE", 0)),
                    "true_shooting_pct": float(row.get("TS_PCT", 0))
                }
            }
            lineup_stats.append(lineup)
        
        result = {
            "season": season,
            "season_type": season_type,
            "per_mode": per_mode,
            "filters": {
                "team_id": team_id,
                "month": month if month != 0 else None,
                "date_range": {"from": date_from, "to": date_to} if date_from or date_to else None,
                "opponent_team_id": opponent_team_id if opponent_team_id != 0 else None,
                "vs_conference": vs_conference,
                "vs_division": vs_division,
                "game_segment": game_segment,
                "period": period if period != 0 else None,
                "last_n_games": last_n_games if last_n_games != 0 else None
            },
            "lineups": lineup_stats
        }
        
        logger.info(f"Successfully fetched stats for {len(lineup_stats)} lineups")
        return format_response(result)
        
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_team_lineups_logic: {e}")
        return format_response(error=f"Unexpected error fetching lineup stats: {str(e)}")