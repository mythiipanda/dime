import logging
import json
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import os
from functools import lru_cache

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
from backend.api_tools.utils import _process_dataframe, _validate_season_format, format_response, find_player_id_or_error, PlayerNotFoundError, validate_date_format
from backend.api_tools.visualization import create_shotchart

logger = logging.getLogger(__name__)

@lru_cache(maxsize=256)
def fetch_player_info_logic(player_name: str) -> str:
    logger.info(f"Executing fetch_player_info_logic for: '{player_name}'")
    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching commonplayerinfo for player ID: {player_id} ({player_actual_name})")
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"commonplayerinfo API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api commonplayerinfo failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_INFO_API.format(identifier=player_actual_name, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
        headline_stats_dict = _process_dataframe(info_endpoint.player_headline_stats.get_data_frame(), single_row=True)

        if player_info_dict is None or headline_stats_dict is None:
            logger.error(f"DataFrame processing failed for {player_actual_name}.")
            error_msg = Errors.PLAYER_INFO_PROCESSING.format(identifier=player_actual_name) # Corrected
            return format_response(error=error_msg)

        logger.info(f"fetch_player_info_logic completed for '{player_actual_name}'")
        return format_response({
            "player_info": player_info_dict or {},
            "headline_stats": headline_stats_dict or {}
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_info_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_info_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_info_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_INFO_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=256)
def fetch_player_gamelog_logic(player_name: str, season: str, season_type: str = SeasonTypeAllStar.regular) -> str:
    logger.info(f"Executing fetch_player_gamelog_logic for: '{player_name}', Season: {season}, Type: {season_type}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)

    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5])) # Show some options
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playergamelog for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            gamelog_endpoint = playergamelog.PlayerGameLog(
                player_id=player_id, season=season, season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT
            )
            logger.debug(f"playergamelog API call successful for ID: {player_id}, Season: {season}")
        except Exception as api_error:
            logger.error(f"nba_api playergamelog failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_GAMELOG_API.format(identifier=player_actual_name, season=season, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        gamelog_df = gamelog_endpoint.get_data_frames()[0]
        if gamelog_df.empty:
            logger.warning(f"No gamelog data found for {player_actual_name} ({season}, {season_type}).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id, "season": season,
                "season_type": season_type, "gamelog": []
            })

        gamelog_cols = [
            'GAME_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT',
            'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB',
            'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'PLUS_MINUS'
        ]
        available_gamelog_cols = [col for col in gamelog_cols if col in gamelog_df.columns]
        gamelog_list = _process_dataframe(gamelog_df.loc[:, available_gamelog_cols] if available_gamelog_cols else pd.DataFrame(), single_row=False)


        if gamelog_list is None:
            logger.error(f"DataFrame processing failed for gamelog of {player_actual_name} ({season}).")
            error_msg = Errors.PLAYER_GAMELOG_PROCESSING.format(identifier=player_actual_name, season=season) # Corrected
            return format_response(error=error_msg)

        logger.info(f"fetch_player_gamelog_logic completed for '{player_actual_name}', Season: {season}")
        return format_response({
            "player_name": player_actual_name, "player_id": player_id, "season": season,
            "season_type": season_type, "gamelog": gamelog_list
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_gamelog_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_gamelog_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_gamelog_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_GAMELOG_UNEXPECTED.format(identifier=player_name, season=season, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=256)
def fetch_player_career_stats_logic(player_name: str, per_mode: str = PerModeDetailed.per_game) -> str:
    logger.info(f"Executing fetch_player_career_stats_logic for: '{player_name}', Requested PerMode: {per_mode}")

    VALID_PER_MODES_CAREER = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    VALID_PER_MODES_CAREER.update({getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)})

    api_call_per_mode = per_mode
    if per_mode not in VALID_PER_MODES_CAREER:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES_CAREER)[:5]))
        logger.warning(error_msg + " Defaulting to PerGame for API call.")
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playercareerstats for ID: {player_id} (PerMode '{api_call_per_mode}' requested)")
        try:
            career_endpoint = playercareerstats.PlayerCareerStats(player_id=player_id, per_mode36=api_call_per_mode, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playercareerstats API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playercareerstats failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_CAREER_STATS_API.format(identifier=player_actual_name, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        season_totals_rs_df = career_endpoint.season_totals_regular_season.get_data_frame()
        career_totals_rs_df = career_endpoint.career_totals_regular_season.get_data_frame()
        season_totals_ps_df = career_endpoint.season_totals_post_season.get_data_frame()
        career_totals_ps_df = career_endpoint.career_totals_post_season.get_data_frame()

        season_totals_cols = [
            'SEASON_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'PLAYER_AGE', 'GP', 'GS',
            'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM',
            'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS'
        ]
        
        available_season_cols_rs = [col for col in season_totals_cols if col in season_totals_rs_df.columns]
        season_totals_regular_season = _process_dataframe(season_totals_rs_df.loc[:, available_season_cols_rs] if not season_totals_rs_df.empty and available_season_cols_rs else pd.DataFrame(), single_row=False)
        career_totals_regular_season = _process_dataframe(career_totals_rs_df, single_row=True)

        available_season_cols_ps = [col for col in season_totals_cols if col in season_totals_ps_df.columns]
        season_totals_post_season = _process_dataframe(season_totals_ps_df.loc[:, available_season_cols_ps] if not season_totals_ps_df.empty and available_season_cols_ps else pd.DataFrame(), single_row=False)
        career_totals_post_season = _process_dataframe(career_totals_ps_df, single_row=True)

        if season_totals_regular_season is None or career_totals_regular_season is None:
            logger.error(f"DataFrame processing failed for regular season career stats of {player_actual_name}.")
            error_msg = Errors.PLAYER_CAREER_STATS_PROCESSING.format(identifier=player_actual_name)
            return format_response(error=error_msg)
        
        # Postseason data can be empty if player never made playoffs, so None check is not as strict for erroring out.
        # It will just result in empty list/dict if processing returns None.

        logger.info(f"fetch_player_career_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name, "player_id": player_id,
            "per_mode_requested": per_mode,
            "data_retrieved_mode": api_call_per_mode,
            "season_totals_regular_season": season_totals_regular_season or [],
            "career_totals_regular_season": career_totals_regular_season or {},
            "season_totals_post_season": season_totals_post_season or [],
            "career_totals_post_season": career_totals_post_season or {}
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_career_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_career_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_career_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_CAREER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)

def get_player_headshot_url(player_id: int) -> str:
    if not isinstance(player_id, int) or player_id <= 0: 
        logger.error(f"Invalid player_id for headshot URL: {player_id}")
        raise ValueError(f"Invalid player ID provided for headshot: {player_id}")
    return f"{HEADSHOT_BASE_URL}/{player_id}.png"

@lru_cache(maxsize=256)
def fetch_player_awards_logic(player_name: str) -> str:
    logger.info(f"Executing fetch_player_awards_logic for: '{player_name}'")
    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerawards for ID: {player_id}")
        try:
            awards_endpoint = playerawards.PlayerAwards(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playerawards API call successful for ID: {player_id}")
        except Exception as api_error:
            logger.error(f"nba_api playerawards failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_AWARDS_API.format(identifier=player_actual_name, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        awards_list = _process_dataframe(awards_endpoint.player_awards.get_data_frame(), single_row=False)

        if awards_list is None: 
            logger.error(f"DataFrame processing failed for awards of {player_actual_name}.")
            error_msg = Errors.PLAYER_AWARDS_PROCESSING.format(identifier=player_actual_name) # Corrected
            return format_response(error=error_msg)

        logger.info(f"fetch_player_awards_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "awards": awards_list 
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_awards_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_awards_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_awards_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_AWARDS_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_player_stats_logic(player_name: str, season: str = CURRENT_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    logger.info(f"Executing fetch_player_stats_logic for: '{player_name}', Season for Gamelog: {season}, Type: {season_type}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name) 

        results_json = {}
        logic_functions_config = {
            "info_and_headlines": (fetch_player_info_logic, [player_actual_name]),
            "career": (fetch_player_career_stats_logic, [player_actual_name]), 
            "gamelog_for_season": (fetch_player_gamelog_logic, [player_actual_name, season, season_type]),
            "awards_history": (fetch_player_awards_logic, [player_actual_name])
        }

        for key, (func, args) in logic_functions_config.items():
            result_str = func(*args)
            try:
                data = json.loads(result_str)
                if "error" in data:
                    logger.error(f"Error from {key} logic for {player_actual_name}: {data['error']}")
                    return result_str 
                results_json[key] = data
            except json.JSONDecodeError as parse_error:
                logger.error(f"Failed to parse JSON from {key} logic for {player_actual_name}: {parse_error}. Response: {result_str}")
                return format_response(error=f"Failed to process internal {key} results for {player_actual_name}.")

        info_data = results_json.get("info_and_headlines", {})
        career_data = results_json.get("career", {})
        gamelog_data = results_json.get("gamelog_for_season", {})
        awards_data = results_json.get("awards_history", {})

        logger.info(f"fetch_player_stats_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name,
            "player_id": player_id,
            "season_requested_for_gamelog": season,
            "season_type_requested_for_gamelog": season_type,
            "info": info_data.get("player_info", {}),
            "headline_stats": info_data.get("headline_stats", {}),
            "career_stats": {
                "season_totals_regular_season": career_data.get("season_totals_regular_season", []),
                "career_totals_regular_season": career_data.get("career_totals_regular_season", {}),
                "season_totals_post_season": career_data.get("season_totals_post_season", []),
                "career_totals_post_season": career_data.get("career_totals_post_season", {})
            },
            "season_gamelog": gamelog_data.get("gamelog", []),
            "awards": awards_data.get("awards", [])
        })

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_stats_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e: 
        logger.warning(f"ValueError in fetch_player_stats_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_stats_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_STATS_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_player_shotchart_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    logger.info(f"Executing fetch_player_shotchart_logic for: '{player_name}', Season: {season}, Type: {season_type}")

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching shotchartdetail for ID: {player_id}, Season: {season}, Type: {season_type}")
        try:
            shotchart_endpoint = shotchartdetail.ShotChartDetail(
                player_id=player_id, team_id=0, season_nullable=season,
                season_type_all_star=season_type, timeout=DEFAULT_TIMEOUT, context_measure_simple='FGA'
            )
            logger.debug(f"shotchartdetail API call successful for ID: {player_id}")
            shots_df = shotchart_endpoint.shot_chart_detail.get_data_frame()
            league_avg_df = shotchart_endpoint.league_averages.get_data_frame()
        except Exception as api_error:
            logger.error(f"nba_api shotchartdetail failed for ID {player_id}, Season {season}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_SHOTCHART_API.format(identifier=player_actual_name, season=season, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        shots_data_list = _process_dataframe(shots_df, single_row=False)
        league_averages_list = _process_dataframe(league_avg_df, single_row=False)

        if shots_data_list is None or league_averages_list is None: 
            logger.error(f"DataFrame processing failed for shot chart of {player_actual_name}")
            error_msg = Errors.PLAYER_SHOTCHART_PROCESSING.format(identifier=player_actual_name) # Corrected
            return format_response(error=error_msg)

        if not shots_data_list: 
            logger.warning(f"No shot data found for {player_actual_name} ({season}, {season_type}).")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
                "overall_stats": {"total_shots": 0, "made_shots": 0, "field_goal_percentage": 0.0},
                "zone_breakdown": {}, "shot_data_summary": [], "league_averages": league_averages_list or [],
                "visualization_path": None, "visualization_error": None,
                "message": "No shot data found for the specified criteria."
            })

        zone_summary = {}
        total_shots = len(shots_data_list)
        made_shots = sum(1 for shot in shots_data_list if shot.get("SHOT_MADE_FLAG") == 1)

        for shot in shots_data_list:
            zone = shot.get("SHOT_ZONE_BASIC", "Unknown")
            if zone not in zone_summary:
                zone_summary[zone] = {"attempts": 0, "made": 0, "percentage": 0.0}
            zone_summary[zone]["attempts"] += 1
            if shot.get("SHOT_MADE_FLAG") == 1:
                zone_summary[zone]["made"] += 1
        for zone_stats in zone_summary.values():
            zone_stats["percentage"] = round(zone_stats["made"] / zone_stats["attempts"] * 100, 1) if zone_stats["attempts"] > 0 else 0.0

        overall_stats_for_viz = {
            "total_shots": total_shots, "made_shots": made_shots,
            "field_goal_percentage": round(made_shots / total_shots * 100, 1) if total_shots > 0 else 0.0
        }
        shot_summary_for_viz = { 
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats_for_viz, "zone_breakdown": zone_summary,
            "shot_locations": [{"x": s.get("LOC_X"), "y": s.get("LOC_Y"), "made": s.get("SHOT_MADE_FLAG") == 1, "zone": s.get("SHOT_ZONE_BASIC")} for s in shots_data_list]
        }

        visualization_path, visualization_error = None, None
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        try:
            os.makedirs(output_dir, exist_ok=True)
            visualization_path = create_shotchart(shot_summary_for_viz, output_dir)
            logger.info(f"Shot chart visualization created at: {visualization_path}")
        except Exception as viz_error:
            logger.error(f"Failed to create shot chart visualization for {player_actual_name}: {viz_error}", exc_info=True)
            visualization_error = str(viz_error)

        response_summary = {
            "player_name": player_actual_name, "player_id": player_id, "season": season, "season_type": season_type,
            "overall_stats": overall_stats_for_viz, "zone_breakdown": zone_summary,
            "shot_data_summary": shots_data_list, 
            "league_averages": league_averages_list or [],
            "visualization_path": visualization_path, "visualization_error": visualization_error
        }
        logger.info(f"fetch_player_shotchart_logic completed for '{player_actual_name}'")
        return format_response(response_summary)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_shotchart_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_shotchart_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_shotchart_logic for '{player_name}', Season {season}: {e}", exc_info=True)
        error_msg = Errors.PLAYER_SHOTCHART_UNEXPECTED.format(identifier=player_name, season=season, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=128)
def fetch_player_defense_logic(
    player_name: str,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    opponent_team_id: int = 0, 
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> str:
    logger.info(
        f"Executing fetch_player_defense_logic for: '{player_name}', Season: {season}, Type: {season_type}, "
        f"PerMode: {per_mode}, Opponent: {opponent_team_id}, From: {date_from}, To: {date_to}"
    )

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    if date_from and not validate_date_format(date_from):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from)
        return format_response(error=error_msg)
    if date_to and not validate_date_format(date_to):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to)
        return format_response(error=error_msg)
    
    VALID_SEASON_TYPES = {getattr(SeasonTypeAllStar, attr) for attr in dir(SeasonTypeAllStar) if not attr.startswith('_') and isinstance(getattr(SeasonTypeAllStar, attr), str)}
    if season_type not in VALID_SEASON_TYPES: 
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        logger.debug(f"Fetching playerdashptshotdefend for ID: {player_id}, Season: {season}")
        try:
            defense_endpoint = playerdashptshotdefend.PlayerDashPtShotDefend(
                player_id=player_id, team_id=0, season=season, season_type_all_star=season_type,
                opponent_team_id=opponent_team_id, date_from_nullable=date_from, date_to_nullable=date_to,
                timeout=DEFAULT_TIMEOUT
            ) 
            logger.debug(f"playerdashptshotdefend API call successful for ID: {player_id}")
            defense_df = defense_endpoint.get_data_frames()[0] 
        except Exception as api_error:
            logger.error(f"nba_api playerdashptshotdefend failed for ID {player_id}: {api_error}", exc_info=True)
            error_msg = Errors.PLAYER_DEFENSE_API.format(identifier=player_actual_name, error=str(api_error)) # Corrected
            return format_response(error=error_msg)

        defense_stats_list = _process_dataframe(defense_df, single_row=False)

        if defense_stats_list is None:
            logger.error(f"DataFrame processing failed for defense stats of {player_actual_name}")
            error_msg = Errors.PLAYER_DEFENSE_PROCESSING.format(identifier=player_actual_name) # Corrected
            return format_response(error=error_msg)

        if not defense_stats_list:
            logger.warning(f"No defense stats found for {player_actual_name} matching criteria.")
            return format_response({
                "player_name": player_actual_name, "player_id": player_id,
                "parameters": { "season": season, "season_type": season_type, "per_mode_requested": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to },
                "summary": {}, "detailed_defense_stats_by_category": [],
                "message": "No defense stats found for the specified criteria."
            })

        defense_by_category = {item.get("DEFENSE_CATEGORY", "Unknown"): item for item in defense_stats_list}
        def get_cat_stats(cat_name: str, default_val: float = 0.0) -> Dict[str, Any]:
            data = defense_by_category.get(cat_name, {})
            return {
                "frequency": float(data.get("FREQ", default_val) or default_val), 
                "field_goal_percentage_allowed": float(data.get("D_FG_PCT", default_val) or default_val),
                "impact_on_fg_percentage": float(data.get("PCT_PLUSMINUS", default_val) or default_val),
                "games_played": int(data.get("GP",0)) 
            }

        overall_raw = defense_by_category.get("Overall", {})
        summary = {
            "games_played": int(overall_raw.get("GP", 0)),
            "overall_defense": {
                "field_goal_percentage_allowed": float(overall_raw.get("D_FG_PCT", 0.0) or 0.0),
                "league_average_fg_percentage": float(overall_raw.get("NORMAL_FG_PCT", 0.0) or 0.0),
                "impact_on_fg_percentage": float(overall_raw.get("PCT_PLUSMINUS", 0.0) or 0.0)
            },
            "three_point_defense": get_cat_stats("3 Pointers"),
            "two_point_defense": get_cat_stats("2 Pointers"),
            "rim_protection_lt_6ft": get_cat_stats("Less Than 6Ft"),
            "mid_range_defense_gt_15ft": get_cat_stats("Greater Than 15Ft") 
        }

        response_data = {
            "player_name": player_actual_name, "player_id": player_id,
            "parameters": { "season": season, "season_type": season_type, "per_mode_requested": per_mode, "opponent_team_id": opponent_team_id, "date_from": date_from, "date_to": date_to },
            "summary": summary,
            "detailed_defense_stats_by_category": defense_stats_list 
        }
        logger.info(f"fetch_player_defense_logic completed for '{player_actual_name}'")
        return format_response(response_data)

    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_defense_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_defense_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_defense_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_DEFENSE_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)

@lru_cache(maxsize=64)
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
    logger.info(
        f"Executing fetch_player_hustle_stats_logic for season {season}, type {season_type}, per_mode {per_mode}, "
        f"player '{player_name}', team '{team_id}', league '{league_id}', from '{date_from}', to '{date_to}'"
    )

    if not season or not _validate_season_format(season):
        error_msg = Errors.INVALID_SEASON_FORMAT.format(season=season)
        return format_response(error=error_msg)
    if date_from and not validate_date_format(date_from):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_from)
        return format_response(error=error_msg)
    if date_to and not validate_date_format(date_to):
        error_msg = Errors.INVALID_DATE_FORMAT.format(date=date_to)
        return format_response(error=error_msg)

    VALID_SEASON_TYPES = {st for st in [SeasonTypeAllStar.regular, SeasonTypeAllStar.playoffs, SeasonTypeAllStar.preseason] if st} 
    if season_type not in VALID_SEASON_TYPES:
        error_msg = Errors.INVALID_SEASON_TYPE.format(value=season_type, options=", ".join(list(VALID_SEASON_TYPES)[:3]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    VALID_PER_MODES = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    if per_mode not in VALID_PER_MODES:
        error_msg = Errors.INVALID_PER_MODE.format(value=per_mode, options=", ".join(list(VALID_PER_MODES)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    player_id_to_filter, player_actual_name_for_response = None, player_name
    if player_name:
        try:
            player_id_to_filter, player_actual_name_for_response = find_player_id_or_error(player_name)
        except PlayerNotFoundError as e:
            logger.warning(f"PlayerNotFoundError in fetch_player_hustle_stats_logic: {e}")
            return format_response(error=str(e))
        except ValueError as e:
            logger.warning(f"ValueError finding player in fetch_player_hustle_stats_logic: {e}")
            return format_response(error=str(e))

    team_id_for_api = team_id if team_id is not None else 0
    try:
        logger.debug(f"Fetching leaguehustlestatsplayer for season {season}, team_id {team_id_for_api}")
        hustle_endpoint = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=season, season_type_all_star=season_type, per_mode_time=per_mode,
            league_id_nullable=league_id, date_from_nullable=date_from, date_to_nullable=date_to,
            team_id_nullable=team_id_for_api, timeout=DEFAULT_TIMEOUT
        )
        hustle_df = hustle_endpoint.get_data_frames()[0]
        logger.debug(f"leaguehustlestatsplayer API call successful.")
    except Exception as api_error:
        logger.error(f"nba_api leaguehustlestatsplayer failed: {api_error}", exc_info=True)
        error_msg = Errors.PLAYER_HUSTLE_API.format(error=str(api_error)) # No identifier here
        return format_response(error=error_msg)

    if hustle_df.empty:
        logger.warning(f"No hustle stats found for initial query (season {season}, team '{team_id_for_api}')")
        return format_response({
            "parameters": { "season": season, "season_type": season_type, "per_mode": per_mode, "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id, "date_from": date_from, "date_to": date_to },
            "hustle_stats": [], "message": "No hustle data found for the specified criteria."
        })

    if player_id_to_filter and 'PLAYER_ID' in hustle_df.columns:
        hustle_df = hustle_df[hustle_df['PLAYER_ID'] == player_id_to_filter]
        if hustle_df.empty:
            logger.warning(f"No hustle stats for player {player_actual_name_for_response} (ID: {player_id_to_filter}) after filtering.")
            return format_response({
                "parameters": { "season": season, "season_type": season_type, "per_mode": per_mode, "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id, "date_from": date_from, "date_to": date_to },
                "hustle_stats": [], "message": f"No hustle data found for player {player_actual_name_for_response} matching criteria."
            })
    elif player_id_to_filter and 'PLAYER_ID' not in hustle_df.columns:
        logger.error("PLAYER_ID column missing for player filtering in hustle stats.")
        return format_response(error="Could not filter hustle stats by player ID due to missing column.")

    if player_name is None and team_id is None and len(hustle_df) > 200: 
         logger.info(f"Limiting league-wide hustle stats to the top 200 entries.")
         hustle_df = hustle_df.head(200)

    hustle_stats_list = _process_dataframe(hustle_df, single_row=False)
    if hustle_stats_list is None:
        logger.error(f"DataFrame processing failed for hustle stats.")
        error_msg = Errors.PLAYER_HUSTLE_PROCESSING.format() # No identifier here
        return format_response(error=error_msg)

    result = {
        "parameters": {
             "season": season, "season_type": season_type, "per_mode": per_mode,
             "player_name": player_actual_name_for_response, "team_id": team_id, "league_id": league_id,
             "date_from": date_from, "date_to": date_to
         },
        "hustle_stats": hustle_stats_list
    }
    logger.info(f"Successfully fetched hustle stats for {len(hustle_stats_list)} entries matching criteria.")
    return format_response(result)

@lru_cache(maxsize=256)
def fetch_player_profile_logic(player_name: str, per_mode: Optional[str] = PerModeDetailed.per_game) -> str: # Allow Optional[str]
    # Handle cases where per_mode might be passed as None from the route
    effective_per_mode = per_mode
    if effective_per_mode is None or effective_per_mode == "None": # Check for None or string "None"
        effective_per_mode = PerModeDetailed.per_game
        logger.info(f"per_mode was None or 'None', defaulting to {effective_per_mode} for {player_name}")
    
    logger.info(f"Executing fetch_player_profile_logic for: '{player_name}', Effective PerMode: {effective_per_mode}")

    VALID_PER_MODES_PROFILE = {getattr(PerModeDetailed, attr) for attr in dir(PerModeDetailed) if not attr.startswith('_') and isinstance(getattr(PerModeDetailed, attr), str)}
    VALID_PER_MODES_PROFILE.update({getattr(PerMode36, attr) for attr in dir(PerMode36) if not attr.startswith('_') and isinstance(getattr(PerMode36, attr), str)})

    if effective_per_mode not in VALID_PER_MODES_PROFILE:
        error_msg = Errors.INVALID_PER_MODE.format(value=effective_per_mode, options=", ".join(list(VALID_PER_MODES_PROFILE)[:5]))
        logger.warning(error_msg)
        return format_response(error=error_msg)

    try:
        player_id, player_actual_name = find_player_id_or_error(player_name)
        # Explicit logging for debugging Jokic issue
        logger.info(f"DEBUG: Inside fetch_player_profile_logic - Resolved Player ID: {player_id}, Actual Name: '{player_actual_name}' for input '{player_name}'")
        
        logger.debug(f"Fetching commonplayerinfo and playerprofilev2 for ID: {player_id}, PerMode: {effective_per_mode}") # Use effective_per_mode here
        try:
            info_endpoint = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=DEFAULT_TIMEOUT)
            player_info_dict = _process_dataframe(info_endpoint.common_player_info.get_data_frame(), single_row=True)
            if player_info_dict is None:
                logger.error(f"Failed to process commonplayerinfo for {player_actual_name} within profile fetch.")
                error_msg = Errors.PLAYER_INFO_PROCESSING.format(identifier=player_actual_name) # Corrected
                return format_response(error=error_msg)

            profile_endpoint = playerprofilev2.PlayerProfileV2(player_id=player_id, per_mode36=effective_per_mode, timeout=DEFAULT_TIMEOUT)
            logger.debug(f"playerprofilev2 API call object created for ID: {player_id}")

            # Check the actual resource returned by the API, if possible
            # This part is tricky as nba_api might parse or error out before we can check raw resource name easily
            # For now, we rely on the endpoint's own dataset attributes.
            # If a JSONDecodeError happens, it's before this point. If not, we check datasets.

        except Exception as api_error: # This catches errors during PlayerProfileV2 instantiation or its internal get_request
            logger.error(f"nba_api playerprofilev2 instantiation or initial request failed for ID {player_id}: {api_error}", exc_info=True)
            # Try to get raw response if it's a JSONDecodeError from within nba_api's HTTP handling
            raw_response_text = None
            if isinstance(api_error, json.JSONDecodeError) and hasattr(profile_endpoint, 'nba_response') and profile_endpoint.nba_response and hasattr(profile_endpoint.nba_response, '_response'):
                raw_response_text = profile_endpoint.nba_response._response
                logger.error(f"Raw NBA API response that caused JSONDecodeError (first 500 chars): {raw_response_text[:500]}")
            
            error_msg = Errors.PLAYER_PROFILE_API.format(identifier=player_actual_name, error=str(api_error))
            return format_response(error=error_msg)

        # Check for expected datasets before trying to get_data_frame()
        def get_df_safe(dataset_name):
            if hasattr(profile_endpoint, dataset_name):
                dataset = getattr(profile_endpoint, dataset_name)
                if hasattr(dataset, 'get_data_frame'):
                    return dataset.get_data_frame()
            logger.warning(f"Dataset '{dataset_name}' not found or not a valid DataSet in PlayerProfileV2 response for player {player_actual_name} (ID: {player_id}). API might have returned unexpected structure.")
            return pd.DataFrame() # Return empty DataFrame if dataset is missing

        career_totals_rs_df = get_df_safe('career_totals_regular_season')
        season_totals_rs_df = get_df_safe('season_totals_regular_season')
        career_totals_ps_df = get_df_safe('career_totals_post_season')
        season_totals_ps_df = get_df_safe('season_totals_post_season')
        season_highs_df = get_df_safe('season_highs')
        career_highs_df = get_df_safe('career_highs')
        next_game_df = get_df_safe('next_game')

        season_highs_dict = _process_dataframe(season_highs_df, single_row=True)
        career_highs_dict = _process_dataframe(career_highs_df, single_row=True)
        next_game_dict = _process_dataframe(next_game_df, single_row=True)
        
        career_totals_rs = _process_dataframe(career_totals_rs_df, single_row=True)
        season_totals_rs_list = _process_dataframe(season_totals_rs_df, single_row=False)
        career_totals_ps = _process_dataframe(career_totals_ps_df, single_row=True)
        season_totals_ps_list = _process_dataframe(season_totals_ps_df, single_row=False)

        # Check if essential data was processed. Regular season totals are considered essential.
        if career_totals_rs is None or season_totals_rs_list is None:
            logger.error(f"Essential profile data (regular season totals) processing failed for {player_actual_name}.")
            error_msg = Errors.PLAYER_PROFILE_PROCESSING.format(identifier=player_actual_name)
            return format_response(error=error_msg)
        
        # Postseason data can be empty, so process them but don't error out if they are None/empty.
        # The frontend will handle displaying them if available.

        logger.info(f"fetch_player_profile_logic completed for '{player_actual_name}'")
        return format_response({
            "player_name": player_actual_name, "player_id": player_id,
            "player_info": player_info_dict or {},
            "per_mode_requested": effective_per_mode, # Use the effective_per_mode
            "career_highs": career_highs_dict or {},
            "season_highs": season_highs_dict or {},
            "next_game": next_game_dict or {},
            "career_totals": {
                "regular_season": career_totals_rs or {},
                "post_season": career_totals_ps or {}
            },
            "season_totals": {
                "regular_season": season_totals_rs_list or [],
                "post_season": season_totals_ps_list or []
            }
        })
    except PlayerNotFoundError as e:
        logger.warning(f"PlayerNotFoundError in fetch_player_profile_logic: {e}")
        return format_response(error=str(e))
    except ValueError as e:
        logger.warning(f"ValueError in fetch_player_profile_logic: {e}")
        return format_response(error=str(e))
    except Exception as e:
        logger.critical(f"Unexpected error in fetch_player_profile_logic for '{player_name}': {e}", exc_info=True)
        error_msg = Errors.PLAYER_PROFILE_UNEXPECTED.format(identifier=player_name, error=str(e)) # Corrected
        return format_response(error=error_msg)
