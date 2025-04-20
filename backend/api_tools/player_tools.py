import logging
import json
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import requests
import os
from nba_api.stats.static import players
from nba_api.stats.endpoints import (
    commonplayerinfo, 
    playergamelog, 
    playerawards, 
    playercareerstats,
    shotchartdetail,
    playerdashptshotdefend,
    playerprofilev2,
    leaguehustlestatsplayer
)
from nba_api.stats.library.parameters import SeasonAll, SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID
from backend.config import DEFAULT_TIMEOUT, HEADSHOT_BASE_URL, Errors, CURRENT_SEASON
from backend.api_tools.utils import _process_dataframe, _validate_season_format, retry_on_timeout, format_response
from backend.api_tools.visualization import create_shotchart

logger = logging.getLogger(__name__)

def _find_player_id(player_name: str) -> tuple[str, str]:
    """Find a player's ID by their name."""
    if not player_name:
        return None, None
    
    try:
        player_list = players.find_players_by_full_name(player_name)
        if player_list:
            # Return the first match's ID and full name
            return player_list[0]['id'], player_list[0]['full_name']
        return None, None
    except Exception as e:
        logger.error(f"Error finding player ID for {player_name}: {e}")
        return None, None

def fetch_player_info_logic(player_name: str) -> str:
    """Core logic to fetch player info."""
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id}")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_INFO_API.format(name=player_actual_name, error=str(api_error)))

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
            logger.error(f"DataFrame processing failed for {player_actual_name}.")
            return format_response(error=Errors.PLAYER_INFO_PROCESSING.format(name=player_actual_name))

        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return format_response({
            "player_info": player_info_dict or {},
            "headline_stats": headline_stats_dict or {}
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_INFO_UNEXPECTED.format(name=player_name, error=str(e)))

def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    """Core logic to fetch player game logs."""
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_GAMELOG_API.format(name=player_actual_name, season=season, error=str(api_error)))

        gamelog_df = gamelog_endpoint.get_data_frames()[0]

        if gamelog_df.empty:
             logger.warning(f"No gamelog data found for {player_actual_name} ({season}).")
             return format_response({
                 "player_name": player_actual_name,
                 "player_id": player_id,
                 "season": season,
                 "season_type": season_type,
                 "gamelog": []
             })

        # Select essential columns for gamelog
        gamelog_cols = [
            'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT',
            'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB',
            'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'PLUS_MINUS'
        ]
        # Ensure all essential columns exist in the DataFrame before selecting
        available_gamelog_cols = [col for col in gamelog_cols if col in gamelog_df.columns]
        gamelog_list = _process_dataframe(gamelog_df.loc[:, available_gamelog_cols], single_row=False)

        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            return format_response(error=Errors.PLAYER_GAMELOG_PROCESSING.format(name=player_actual_name, season=season))

        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "season": season,
            "season_type": season_type,
            "gamelog": gamelog_list
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_GAMELOG_UNEXPECTED.format(name=player_name, season=season, error=str(e)))

def fetch_player_career_stats_logic(player_name: str, per_mode36: str = PerMode36.per_game) -> str:
    """Core logic to fetch player career stats."""
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', PerMode36: {per_mode36}")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)

    valid_per_modes = [getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)]
    original_request_mode = per_mode36
    if per_mode36 not in valid_per_modes:
        logger.warning(f"Invalid per_mode36 '{per_mode36}'. Using default '{PerMode36.per_game}'. Valid options: {valid_per_modes}")
        per_mode36 = PerMode36.per_game

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playercareerstats for ID: {player_id} (Ignoring PerMode in API call)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_CAREER_STATS_API.format(name=player_actual_name, error=str(api_error)))

        season_totals_df = career_endpoint.season_totals_regular_season.get_data_frame()
        career_totals_df = career_endpoint.career_totals_regular_season.get_data_frame()

        # Select essential columns for season totals
        season_totals_cols = [
            'SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'PLAYER_AGE', 'GP', 'GS',
            'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM',
            'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV',
            'PF', 'PTS'
        ]
        # Ensure all essential columns exist in the DataFrame before selecting
        available_season_totals_cols = [col for col in season_totals_cols if col in season_totals_df.columns]
        season_totals = _process_dataframe(season_totals_df.loc[:, available_season_totals_cols] if not season_totals_df.empty else season_totals_df, single_row=False)

        career_totals = _process_dataframe(career_totals_df, single_row=True)


        if season_totals is None or career_totals is None:
            logger.error(f"DataFrame processing failed for career stats of {player_actual_name}.")
            return format_response(error=Errors.PLAYER_CAREER_STATS_PROCESSING.format(name=player_actual_name))

        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "per_mode_requested": original_request_mode,
            "data_retrieved_mode": "Default (PerMode parameter ignored)",
            "season_totals_regular_season": season_totals or [],
            "career_totals_regular_season": career_totals or {}
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(name=player_name, error=str(e)))

def get_player_headshot_url(player_id: int) -> str:
    """
    Get the URL for a player's headshot image.
    Args:
        player_id (int): The player's ID
    Returns:
        str: The URL for the player's headshot image
    """
    if not player_id or player_id <= 0:
        # Use the defined error constant if available, otherwise raise ValueError
        # raise ValueError(Errors.INVALID_PLAYER_ID_FORMAT.format(player_id=player_id))
        raise ValueError(f"Invalid player ID provided: {player_id}")
    
    return f"{HEADSHOT_BASE_URL}/{player_id}.png"

def fetch_player_awards_logic(player_name: str) -> str:
    """Core logic to fetch player awards."""
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}'")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playerawards for ID: {player_id}")
        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_AWARDS_API.format(name=player_actual_name, error=str(api_error)))

        awards_list = _process_dataframe(awards_endpoint.player_awards.get_data_frame(), single_row=False)

        if awards_list is None:
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            awards_list = []

        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_AWARDS_UNEXPECTED.format(name=player_name, error=str(e)))

def fetch_player_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches comprehensive player statistics including career stats, game logs, and info.
    """
    logger.info(f"Executing fetch_player_stats_logic for: '{player_name}', Season: {season}")
    
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))
        
        info_result = fetch_player_info_logic(player_name)
        career_result = fetch_player_career_stats_logic(player_name)
        gamelog_result = fetch_player_gamelog_logic(player_name, season, season_type)
        awards_result = fetch_player_awards_logic(player_name)

        for result in [info_result, career_result, gamelog_result, awards_result]:
            if '"error":' in result:
                return result

        try:
            info_data = json.loads(info_result)
            career_data = json.loads(career_result)
            gamelog_data = json.loads(gamelog_result)
            awards_data = json.loads(awards_result)

            logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")
            return format_response({
                "player_name": player_actual_name,
                "player_id": player_id,
                "season": season,
                "season_type": season_type,
                "info": info_data.get("player_info", {}),
                "headline_stats": info_data.get("headline_stats", {}),
                "career_stats": {
                    "season_totals": career_data.get("season_totals_regular_season", []),
                    "career_totals": career_data.get("career_totals_regular_season", {})
                },
                "current_season": {
                    "gamelog": gamelog_data.get("gamelog", [])
                },
                "awards": awards_data.get("awards", [])
            })
        except json.JSONDecodeError as parse_error:
            logger.error(f"Failed to parse sub-results in fetch_player_stats_logic: {parse_error}")
            return format_response(error="Failed to process intermediate results.")
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=f"Unexpected error retrieving player stats: {str(e)}")

def fetch_player_shotchart_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """Fetches a player's shot chart data for detailed shooting analysis."""
    logger.info(f"Executing fetch_player_shotchart_logic for: '{player_name}', Season: {season}")
    
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching shotchartdetail for ID: {player_id}, Season: {season}")
        try:
            shotchart_endpoint = shotchartdetail.ShotChartDetail(
                player_id=player_id,
                team_id=0,  # 0 for all teams
                season_nullable=season,
                season_type_all_star=season_type,
                timeout=DEFAULT_TIMEOUT,
                context_measure_simple='FGA'
            )
            logger.debug(f"shotchartdetail API call successful for ID: {player_id}")
            
            shots_df = shotchart_endpoint.get_data_frames()[0]
            league_avg_df = shotchart_endpoint.get_data_frames()[1]
            
            shots_data = _process_dataframe(shots_df, single_row=False)
            league_averages = _process_dataframe(league_avg_df, single_row=False)
            
            if shots_data is None or league_averages is None:
                logger.error(f"DataFrame processing failed for shot chart of {player_actual_name}")
                return format_response(error=f"Failed to process shot chart data for {player_actual_name}")
            
            # Create zone-based shooting summary
            zone_summary = {}
            total_shots = len(shots_data)
            made_shots = sum(1 for shot in shots_data if shot.get("SHOT_MADE_FLAG", 0) == 1)
            
            for shot in shots_data:
                zone = shot.get("SHOT_ZONE_BASIC", "Unknown")
                if zone not in zone_summary:
                    zone_summary[zone] = {
                        "attempts": 0,
                        "made": 0,
                        "percentage": 0.0
                    }
                zone_summary[zone]["attempts"] += 1
                if shot.get("SHOT_MADE_FLAG", 0) == 1:
                    zone_summary[zone]["made"] += 1
            
            # Calculate percentages for each zone
            for zone in zone_summary:
                attempts = zone_summary[zone]["attempts"]
                made = zone_summary[zone]["made"]
                zone_summary[zone]["percentage"] = round(made / attempts * 100, 1) if attempts > 0 else 0
            
            shot_summary = {
                "player_name": player_actual_name,
                "player_id": player_id,
                "season": season,
                "season_type": season_type,
                "overall_stats": {
                    "total_shots": total_shots,
                    "made_shots": made_shots,
                    "field_goal_percentage": round(made_shots / total_shots * 100, 1) if total_shots > 0 else 0
                },
                "zone_breakdown": zone_summary,
                "shot_locations": [
                    {
                        "x": shot.get("LOC_X"),
                        "y": shot.get("LOC_Y"),
                        "made": shot.get("SHOT_MADE_FLAG") == 1,
                        "distance": shot.get("SHOT_DISTANCE"),
                        "zone": shot.get("SHOT_ZONE_BASIC")
                    }
                    for shot in shots_data  # Include all shots for visualization
                ]
            }
            
            # Generate visualization
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
            try:
                visualization_path = create_shotchart(shot_summary, output_dir)
                shot_summary["visualization_path"] = visualization_path
            except Exception as viz_error:
                logger.error(f"Failed to create shot chart visualization: {viz_error}")
                shot_summary["visualization_error"] = str(viz_error)
            
            # Prepare the response, excluding the full shot_locations list
            response_summary = {
                "player_name": shot_summary.get("player_name"),
                "player_id": shot_summary.get("player_id"),
                "season": shot_summary.get("season"),
                "season_type": shot_summary.get("season_type"),
                "overall_stats": shot_summary.get("overall_stats", {}),
                "zone_breakdown": shot_summary.get("zone_breakdown", {}),
                "visualization_path": shot_summary.get("visualization_path"),
                "visualization_error": shot_summary.get("visualization_error") # Include error if visualization failed
            }
            return format_response(response_summary)
            
        except Exception as api_error:
            logger.error(f"nba_api shotchartdetail failed for ID {player_id}: {api_error}")
            return format_response(error=f"API error fetching shot chart: {str(api_error)}")
            
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_shotchart_logic: {e}")
        return format_response(error=f"Unexpected error fetching shot chart: {str(e)}")

def fetch_player_defense_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """Fetches detailed defensive statistics for a player."""
    logger.info(
        f"Executing fetch_player_defense_logic for: '{player_name}', Season: {season}, Type: {season_type}, "
        f"Opponent: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )
    
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))
    
    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching defense stats for ID: {player_id}, Season: {season}")
        try:
            defense_endpoint = playerdashptshotdefend.PlayerDashPtShotDefend(
                player_id=player_id,
                team_id=0,  # 0 for player-centric view
                season=season,
                season_type_all_star=season_type,
                opponent_team_id=opponent_team_id,
                date_from_nullable=date_from,
                date_to_nullable=date_to,
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerdashptshotdefend API call successful for ID: {player_id}")
            
            defense_df = defense_endpoint.get_data_frames()[0]
            defense_stats_list = _process_dataframe(defense_df, single_row=False)

            if defense_stats_list is None or not defense_stats_list:
                logger.error(f"No defense stats found for {player_actual_name}")
                return format_response(error=f"No defense stats available for {player_actual_name} in {season}")

            # Process into a dictionary keyed by DEFENSE_CATEGORY for robust access
            defense_by_category = {item.get("DEFENSE_CATEGORY", "Unknown"): item for item in defense_stats_list}

            # Helper to safely get stats from the category dictionary
            def get_category_stats(category_name, default_val=0):
                category_data = defense_by_category.get(category_name, {})
                return {
                    "frequency": category_data.get("FREQ", default_val),
                    "field_goal_percentage_allowed": category_data.get("D_FG_PCT", default_val),
                    "impact": category_data.get("PCT_PLUSMINUS", default_val)
                }

            overall_stats = defense_by_category.get("Overall", {})
            three_pt_stats = get_category_stats("3 Pointers")
            two_pt_stats = get_category_stats("2 Pointers")
            rim_stats = get_category_stats("Less Than 6Ft") # Assuming 'Less Than 6Ft' corresponds to rim protection

            # Create a more structured and summarized response
            defensive_summary = {
                "player_name": player_actual_name,
                "player_id": player_id,
                "parameters": {
                    "season": season,
                    "season_type": season_type,
                    "per_mode_requested": per_mode,
                    "opponent_team_id": opponent_team_id,
                    "date_from": date_from,
                    "date_to": date_to
                },
                "summary": {
                    "games_played": overall_stats.get("GP", 0),
                    "overall_defense": {
                        "field_goal_percentage_allowed": overall_stats.get("D_FG_PCT", 0),
                        "league_average": overall_stats.get("NORMAL_FG_PCT", 0),
                        "impact": overall_stats.get("PCT_PLUSMINUS", 0)
                    },
                    "three_point_defense": three_pt_stats,
                    "two_point_defense": two_pt_stats,
                    "rim_protection": rim_stats # Stats for shots less than 6ft
                }
            }
            
            return format_response(defensive_summary)
            
        except Exception as api_error:
            logger.error(f"nba_api playerdashptshotdefend failed for ID {player_id}: {api_error}")
            return format_response(error=f"API error fetching defense stats: {str(api_error)}")
            
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_defense_logic: {e}")
        return format_response(error=f"Unexpected error fetching defense stats: {str(e)}")

def fetch_player_hustle_stats_logic(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = LeagueID.nba,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    """Fetches hustle stats (deflections, loose balls, etc.) filtered by season, type, mode, and optionally player or team."""
    logger.info(
        f"Executing fetch_player_hustle_stats_logic for season {season}, type {season_type}, per_mode {per_mode}, "
        f"player '{player_name}', team '{team_id}', league '{league_id}', from '{date_from}', to '{date_to}'"
    )
    
    if not season or not _validate_season_format(season):
        return format_response(error=Errors.INVALID_SEASON_FORMAT.format(season=season))

    # Input Validation (existing + new)
    valid_season_types = [getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)]
    if season_type not in valid_season_types:
        logger.error(f"Invalid season_type '{season_type}'.")
        return format_response(error=f"Invalid season_type: '{season_type}'. Valid: {valid_season_types}")

    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
        logger.error(f"Invalid per_mode '{per_mode}'.")
        return format_response(error=f"Invalid per_mode: '{per_mode}'. Valid: {valid_per_modes}")

    player_id_to_pass = None
    player_or_team_abbr = 'T' # Default to Team if no player name
    if player_name:
        player_id_result, _ = _find_player_id(player_name)
        if player_id_result is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))
        player_id_to_pass = player_id_result
        player_or_team_abbr = 'P'
    elif team_id:
         player_or_team_abbr = 'T'
    # If neither player_name nor team_id is given, we fetch league-wide (player_or_team_abbr stays 'T'? API default seems league-wide)
    # Let's explicitly set player_id/team_id to 0 for league-wide fetch if needed, check API defaults
    if not player_name and not team_id:
         player_or_team_abbr = None # Let API default handle league-wide
         # Explicitly set IDs to 0 or None? Let's try None first.
         team_id_to_pass = None
    else:
         team_id_to_pass = team_id

    try:
        logger.debug(f"Fetching hustle stats for season {season} with filters.")
        hustle = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season,
            season_type_all_star=season_type,
            per_mode_time=per_mode,
            league_id_nullable=league_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            team_id_nullable=team_id_to_pass,
            timeout=DEFAULT_TIMEOUT
        )
        
        hustle_df = hustle.get_data_frames()[0]
        if hustle_df.empty:
            logger.warning(f"No hustle stats found for the specified filters (season {season}, player '{player_name}', team '{team_id}')")
            # Return empty list instead of error if simply no data matches filters
            return format_response({
                "parameters": { # Include parameters in the response
                     "season": season, "season_type": season_type, "per_mode": per_mode,
                     "player_name": player_name, "team_id": team_id, "league_id": league_id,
                     "date_from": date_from, "date_to": date_to
                 },
                "hustle_stats": []
            })

        # If a player name is provided, filter the dataframe for that player's ID
        if player_id_to_pass:
            hustle_df = hustle_df[hustle_df['PLAYER_ID'] == int(player_id_to_pass)]
            if hustle_df.empty:
                 logger.warning(f"No hustle stats found for player ID {player_id_to_pass} with the specified filters.")
                 return format_response({
                     "parameters": { # Include parameters in the response
                          "season": season, "season_type": season_type, "per_mode": per_mode,
                          "player_name": player_name, "team_id": team_id, "league_id": league_id,
                          "date_from": date_from, "date_to": date_to
                      },
                     "hustle_stats": []
                 })

        # Limit the number of players returned if no specific player or team is requested
        if player_name is None and team_id is None:
             logger.info(f"Limiting league-wide hustle stats to the top 200 players.")
             hustle_df = hustle_df.head(200) # Limit to the first 200 rows

        # Process hustle stats using list comprehension
        hustle_stats = [
            {
                "player": {
                    "id": row.get("PLAYER_ID"), "name": row.get("PLAYER_NAME"), "team": row.get("TEAM_ABBREVIATION")
                },
                "games_played": row.get("G", 0), "minutes": row.get("MIN", 0),
                "defensive_stats": {
                    "charges_drawn": row.get("CHARGES_DRAWN", 0), "contested_shots": row.get("CONTESTED_SHOTS", 0),
                    "contested_shots_3pt": row.get("CONTESTED_SHOTS_3PT", 0), "contested_shots_2pt": row.get("CONTESTED_SHOTS_2PT", 0),
                    "deflections": row.get("DEFLECTIONS", 0)
                },
                "loose_ball_stats": {
                    "loose_balls_recovered": row.get("LOOSE_BALLS_RECOVERED", 0),
                    "loose_balls_recovered_offensive": row.get("LOOSE_BALLS_RECOVERED_OFF", 0),
                    "loose_balls_recovered_defensive": row.get("LOOSE_BALLS_RECOVERED_DEF", 0)
                },
                "screen_stats": {
                    "screen_assists": row.get("SCREEN_ASSISTS", 0), "screen_assist_points": row.get("SCREEN_AST_PTS", 0)
                },
                "box_out_stats": {
                    "box_outs": row.get("BOX_OUTS", 0), "box_outs_offensive": row.get("BOX_OUTS_OFF", 0),
                    "box_outs_defensive": row.get("BOX_OUTS_DEF", 0)
                }
            } for _, row in hustle_df.iterrows()
        ] if not hustle_df.empty else []

        result = {
            "parameters": {
                 "season": season, "season_type": season_type, "per_mode": per_mode,
                 "player_name": player_name, "team_id": team_id, "league_id": league_id,
                 "date_from": date_from, "date_to": date_to
             },
            "hustle_stats": hustle_stats
        }

        logger.info(f"Successfully fetched hustle stats for {len(hustle_stats)} players")
        return format_response(result)
        
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_hustle_stats_logic: {e}")
        return format_response(error=f"Unexpected error fetching hustle stats: {str(e)}")

def fetch_player_profile_logic(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    """Fetches comprehensive player profile information including career highs, next game, etc."""
    logger.info(f"Executing fetch_player_profile_logic for: '{player_name}', PerMode: {per_mode}")
    if not player_name or not player_name.strip():
        return format_response(error=Errors.PLAYER_NAME_EMPTY)

    valid_per_modes = [getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)]
    if per_mode not in valid_per_modes:
        logger.warning(f"Invalid per_mode '{per_mode}'. Using default '{PerModeDetailed.per_game}'. Valid options: {valid_per_modes}")
        per_mode = PerModeDetailed.per_game

    try:
        player_id, player_actual_name = _find_player_id(player_name)
        if player_id is None:
            return format_response(error=Errors.PLAYER_NOT_FOUND.format(name=player_name))

        logger.debug(f"Fetching playerprofilev2 for ID: {player_id}, PerMode: {per_mode}")
        try:
            # Fetch basic player info first
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
            if player_info_dict is None:
                 logger.error(f"Failed to process commonplayerinfo for {player_actual_name}.")
                 # Decide if this should be a fatal error or just log a warning
                 return format_response(error=Errors.PLAYER_INFO_PROCESSING.format(name=player_actual_name))

            # Fetch profile details
            profile_endpoint = playerprofilev2.PlayerProfileV2(
                player_id=player_id,
                per_mode36=per_mode,  # Note: API uses per_mode36 param name
                timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playerprofilev2 API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerprofilev2 failed for ID {player_id}: {api_error}", exc_info=True)
            return format_response(error=Errors.PLAYER_PROFILE_API.format(name=player_actual_name, error=str(api_error))) # Assumes PLAYER_PROFILE_API error exists

        # Process the different dataframes available in the endpoint
        career_totals_allstar_season = _process_dataframe(profile_endpoint.career_totals_all_star_season.get_data_frame(), single_row=True)
        career_totals_college_season = _process_dataframe(profile_endpoint.career_totals_college_season.get_data_frame(), single_row=True)
        career_totals_post_season = _process_dataframe(profile_endpoint.career_totals_post_season.get_data_frame(), single_row=True)
        career_totals_preseason = _process_dataframe(profile_endpoint.career_totals_preseason.get_data_frame(), single_row=True)
        career_totals_regular_season = _process_dataframe(profile_endpoint.career_totals_regular_season.get_data_frame(), single_row=True)
        season_highs = _process_dataframe(profile_endpoint.season_highs.get_data_frame(), single_row=True)
        career_highs = _process_dataframe(profile_endpoint.career_highs.get_data_frame(), single_row=True)
        next_game = _process_dataframe(profile_endpoint.next_game.get_data_frame(), single_row=True)
        # Season totals are split by season type
        season_totals_allstar_season = _process_dataframe(profile_endpoint.season_totals_all_star_season.get_data_frame(), single_row=False)
        season_totals_college_season = _process_dataframe(profile_endpoint.season_totals_college_season.get_data_frame(), single_row=False)
        season_totals_post_season = _process_dataframe(profile_endpoint.season_totals_post_season.get_data_frame(), single_row=False)
        season_totals_preseason = _process_dataframe(profile_endpoint.season_totals_preseason.get_data_frame(), single_row=False)
        season_totals_regular_season = _process_dataframe(profile_endpoint.season_totals_regular_season.get_data_frame(), single_row=False)

        # Check if primary data (regular season totals) failed
        if career_totals_regular_season is None and season_totals_regular_season is None:
             logger.error(f"Essential profile data processing failed for {player_actual_name}.")
             return format_response(error=Errors.PLAYER_PROFILE_PROCESSING.format(name=player_actual_name)) # Assumes PLAYER_PROFILE_PROCESSING error exists

        logger.info(f"fetch_player_profile_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "player_info": player_info_dict or {},
            "per_mode_requested": per_mode,
            "career_highs": career_highs or {},
            "season_highs": season_highs or {},
            "next_game": next_game or {},
            "career_totals": {
                "regular_season": career_totals_regular_season or {},
            },
            "season_totals": {
                "regular_season": season_totals_regular_season or [],
            }
        })
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_profile_logic for '{player_name}': {e}", exc_info=True)
        return format_response(error=Errors.PLAYER_PROFILE_UNEXPECTED.format(name=player_name, error=str(e))) # Assumes PLAYER_PROFILE_UNEXPECTED error exists
