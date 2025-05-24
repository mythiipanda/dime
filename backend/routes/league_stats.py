import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, status
from typing import Dict, Any, Optional
import json

from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerMode48,
    LeagueID,
    MeasureTypeDetailedDefense,
    Conference,
    Division
)

from api_tools.league_dash_team_stats import fetch_league_team_stats_logic
from api_tools.league_dash_player_stats import fetch_league_player_stats_logic
from api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic
from api_tools.team_estimated_metrics import fetch_team_estimated_metrics_logic
from api_tools.comprehensive_analytics import get_comprehensive_league_data, get_player_advanced_analytics
from core.errors import Errors
from utils.validation import validate_season_format
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/league",
    tags=["League Statistics"]
)

async def _handle_league_stats_logic_call(
    logic_function: callable,
    endpoint_name: str,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """Helper to call league-related logic, parse JSON, and handle errors."""
    try:
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        result_json_string = await asyncio.to_thread(logic_function, *args, **filtered_kwargs)
        result_data = json.loads(result_json_string)

        if isinstance(result_data, dict) and 'error' in result_data:
            error_detail = result_data['error']
            logger.error(f"Error from {logic_function.__name__} with args {args}, kwargs {filtered_kwargs}: {error_detail}")
            status_code_to_raise = status.HTTP_404_NOT_FOUND if "not found" in error_detail.lower() else \
                                   status.HTTP_400_BAD_REQUEST if "invalid" in error_detail.lower() else \
                                   status.HTTP_500_INTERNAL_SERVER_ERROR
            if "nba api error" in error_detail.lower() or "external api" in error_detail.lower():
                status_code_to_raise = status.HTTP_502_BAD_GATEWAY
            raise HTTPException(status_code=status_code_to_raise, detail=error_detail)
        return result_data
    except HTTPException as http_exc:
        raise http_exc
    except json.JSONDecodeError as json_err:
        func_name = logic_function.__name__
        logger.error(f"Failed to parse JSON response from {func_name} for args {args}, kwargs {filtered_kwargs}: {json_err}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=Errors.JSON_PROCESSING_ERROR)
    except Exception as e:
        func_name = logic_function.__name__
        logger.critical(f"Unexpected error in API route calling {func_name} for {endpoint_name}: {str(e)}", exc_info=True)
        error_msg_template = getattr(Errors, 'UNEXPECTED_ERROR', "An unexpected server error occurred: {error}")
        detail_msg = error_msg_template.format(error=f"processing {endpoint_name.lower()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail_msg)

@router.get(
    "/team-stats",
    summary="Get League-Wide Team Statistics",
    description="Fetches comprehensive league-wide team statistics for a specified season and criteria.",
    response_model=Dict[str, Any]
)
async def get_league_team_stats_endpoint(
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"),
    season_type: Optional[str] = Query(SeasonTypeAllStar.regular, description="Type of season (e.g., 'Regular Season', 'Playoffs')."),
    per_mode: Optional[str] = Query(PerMode48.per_game, description="Statistical mode (e.g., 'PerGame', 'Totals', 'MinutesPer')."),
    measure_type: Optional[str] = Query(MeasureTypeDetailedDefense.base, description="Category of stats (e.g., 'Base', 'Advanced', 'Scoring')."),
    league_id: Optional[str] = Query(LeagueID.nba, description="League ID (e.g., '00' for NBA)."),
    conference: Optional[str] = Query(None, description=f"Conference filter (e.g., '{Conference.east}', '{Conference.west}')."),
    division: Optional[str] = Query(None, description=f"Division filter (e.g., '{Division.east}', '{Division.west}')."),
    team_id: Optional[int] = Query(None, description="Filter by specific team ID."),
    date_from: Optional[str] = Query(None, description="Start date (MM/DD/YYYY) for filtering games.", regex=r"^\d{2}/\d{2}/\d{4}$"),
    date_to: Optional[str] = Query(None, description="End date (MM/DD/YYYY) for filtering games.", regex=r"^\d{2}/\d{2}/\d{4}$"),
    location: Optional[str] = Query(None, description="Filter by game location (e.g., 'Home', 'Road')."),
    outcome: Optional[str] = Query(None, description="Filter by game outcome (e.g., 'W', 'L')."),
    season_segment: Optional[str] = Query(None, description="Filter by season segment (e.g., 'Post All-Star', 'Pre All-Star')."),
    vs_conference: Optional[str] = Query(None, description=f"Filter by opponent conference (e.g., '{Conference.east}', '{Conference.west}')."),
    vs_division: Optional[str] = Query(None, description=f"Filter by opponent division (e.g., '{Division.east}', '{Division.west}').")
) -> Dict[str, Any]:
    """
    Endpoint to retrieve league-wide team statistics.
    Uses `fetch_league_team_stats_logic` from `league_dash_team_stats.py`.

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.
    - **season_type** (str, optional): e.g., "Regular Season". Default: "Regular Season".
    - **per_mode** (str, optional): e.g., "PerGame". Default: "PerGame".
    - **measure_type** (str, optional): e.g., "Base". Default: "Base".
    - **league_id** (str, optional): e.g., "00" for NBA. Default: "00".
    - **conference** (str, optional): e.g., "East".
    - **division** (str, optional): e.g., "Atlantic".
    - **team_id** (int, optional): Specific team ID.
    - **date_from** (str, optional): MM/DD/YYYY.
    - **date_to** (str, optional): MM/DD/YYYY.
    - **location** (str, optional): "Home" or "Road".
    - **outcome** (str, optional): "W" or "L".
    - **season_segment** (str, optional): "Post All-Star" or "Pre All-Star".
    - **vs_conference** (str, optional): Opponent conference.
    - **vs_division** (str, optional): Opponent division.

    Successful Response (200 OK):
    Returns a dictionary containing parameters and league-wide team statistics.
    Refer to `fetch_league_team_stats_logic` docstring in `league_dash_team_stats.py` for detailed structure.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid.
    - 500 Internal Server Error / 502 Bad Gateway: For unexpected errors or issues fetching/processing data.
    """
    logger.info(f"Received GET /league/team-stats request. Season: {season}, Type: {season_type}, PerMode: {per_mode}, Measure: {measure_type}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    stats_kwargs = {
        "season": season_to_use,
        "season_type": season_type,
        "per_mode": per_mode,
        "measure_type": measure_type,
        "league_id": league_id,
        "conference": conference,
        "division": division,
        "team_id": team_id,
        "date_from": date_from,
        "date_to": date_to,
        "location": location,
        "outcome": outcome,
        "season_segment": season_segment,
        "vs_conference": vs_conference,
        "vs_division": vs_division
    }

    return await _handle_league_stats_logic_call(
        fetch_league_team_stats_logic, "league team stats",
        **stats_kwargs
    )

@router.get(
    "/player-stats",
    summary="Get League-Wide Player Statistics",
    description="Fetches comprehensive league-wide player statistics for a specified season and criteria.",
    response_model=Dict[str, Any]
)
async def get_league_player_stats_endpoint(
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"),
    season_type: Optional[str] = Query("Regular Season", description="Type of season (e.g., 'Regular Season', 'Playoffs')."),
    per_mode: Optional[str] = Query("PerGame", description="Statistical mode (e.g., 'PerGame', 'Totals', 'Per36')."),
    measure_type: Optional[str] = Query("Base", description="Category of stats (e.g., 'Base', 'Advanced', 'Scoring')."),
    team_id: Optional[str] = Query("", description="Filter by specific team ID."),
    player_position: Optional[str] = Query("", description="Filter by player position (e.g., 'G', 'F', 'C')."),
    player_experience: Optional[str] = Query("", description="Filter by player experience (e.g., 'Rookie', 'Veteran')."),
    starter_bench: Optional[str] = Query("", description="Filter by starter/bench status (e.g., 'Starters', 'Bench')."),
    date_from: Optional[str] = Query("", description="Start date (MM/DD/YYYY) for filtering games."),
    date_to: Optional[str] = Query("", description="End date (MM/DD/YYYY) for filtering games."),
    game_segment: Optional[str] = Query("", description="Filter by game segment (e.g., 'First Half', 'Second Half')."),
    last_n_games: Optional[int] = Query(0, description="Filter by last N games (0 for all games)."),
    league_id: Optional[str] = Query("00", description="League ID (e.g., '00' for NBA)."),
    location: Optional[str] = Query("", description="Filter by game location (e.g., 'Home', 'Road')."),
    month: Optional[int] = Query(0, description="Filter by month (0-12, 0 for all months)."),
    opponent_team_id: Optional[int] = Query(0, description="Filter by opponent team ID."),
    outcome: Optional[str] = Query("", description="Filter by game outcome (e.g., 'W', 'L')."),
    period: Optional[int] = Query(0, description="Filter by period (0-4, 0 for all periods)."),
    season_segment: Optional[str] = Query("", description="Filter by season segment (e.g., 'Post All-Star', 'Pre All-Star')."),
    vs_conference: Optional[str] = Query("", description="Filter by opponent conference (e.g., 'East', 'West')."),
    vs_division: Optional[str] = Query("", description="Filter by opponent division.")
) -> Dict[str, Any]:
    """
    Endpoint to retrieve league-wide player statistics.
    Uses `fetch_league_player_stats_logic` from `league_dash_player_stats.py`.

    This endpoint provides comprehensive player statistics across the league:
    - Basic and advanced statistics
    - Scoring and defensive metrics
    - Player rankings
    - Filtering by team, position, experience, etc.

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.
    - **season_type** (str, optional): e.g., "Regular Season". Default: "Regular Season".
    - **per_mode** (str, optional): e.g., "PerGame". Default: "PerGame".
    - **measure_type** (str, optional): e.g., "Base". Default: "Base".
    - **team_id** (str, optional): Specific team ID filter.
    - **player_position** (str, optional): Position filter (G, F, C).
    - **player_experience** (str, optional): Experience filter.
    - **starter_bench** (str, optional): Role filter.
    - **date_from** (str, optional): MM/DD/YYYY.
    - **date_to** (str, optional): MM/DD/YYYY.
    - **game_segment** (str, optional): Game segment filter.
    - **last_n_games** (int, optional): Last N games filter.
    - **league_id** (str, optional): League ID.
    - **location** (str, optional): "Home" or "Road".
    - **month** (int, optional): Month filter (0-12).
    - **opponent_team_id** (int, optional): Opponent team filter.
    - **outcome** (str, optional): "W" or "L".
    - **period** (int, optional): Period filter (0-4).
    - **season_segment** (str, optional): Season segment filter.
    - **vs_conference** (str, optional): Opponent conference.
    - **vs_division** (str, optional): Opponent division.

    Successful Response (200 OK):
    Returns a dictionary containing parameters and league-wide player statistics.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid.
    - 500 Internal Server Error / 502 Bad Gateway: For unexpected errors.
    """
    logger.info(f"Received GET /league/player-stats request. Season: {season}, Type: {season_type}, PerMode: {per_mode}, Measure: {measure_type}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    player_stats_kwargs = {
        "season": season_to_use,
        "season_type": season_type,
        "per_mode": per_mode,
        "measure_type": measure_type,
        "team_id": team_id,
        "player_position": player_position,
        "player_experience": player_experience,
        "starter_bench": starter_bench,
        "date_from": date_from,
        "date_to": date_to,
        "game_segment": game_segment,
        "last_n_games": last_n_games,
        "league_id": league_id,
        "location": location,
        "month": month,
        "opponent_team_id": opponent_team_id,
        "outcome": outcome,
        "period": period,
        "season_segment": season_segment,
        "vs_conference": vs_conference,
        "vs_division": vs_division
    }

    return await _handle_league_stats_logic_call(
        fetch_league_player_stats_logic, "league player stats",
        **player_stats_kwargs
    )

@router.get(
    "/player-estimated-metrics",
    summary="Get League-Wide Player Estimated Metrics",
    description="Fetches estimated metrics (E_OFF_RATING, E_DEF_RATING, E_NET_RATING, etc.) for all players.",
    response_model=Dict[str, Any]
)
async def get_league_player_estimated_metrics_endpoint(
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"),
    season_type: Optional[str] = Query("Regular Season", description="Type of season (e.g., 'Regular Season', 'Playoffs')."),
    league_id: Optional[str] = Query("00", description="League ID (e.g., '00' for NBA).")
) -> Dict[str, Any]:
    """
    Endpoint to retrieve league-wide player estimated metrics.
    Uses `fetch_player_estimated_metrics_logic` from `player_estimated_metrics.py`.

    This endpoint provides estimated metrics for all players:
    - E_OFF_RATING: Estimated Offensive Rating
    - E_DEF_RATING: Estimated Defensive Rating
    - E_NET_RATING: Estimated Net Rating
    - E_PACE: Estimated Pace
    - E_AST_RATIO: Estimated Assist Ratio
    - E_OREB_PCT: Estimated Offensive Rebound Percentage
    - E_DREB_PCT: Estimated Defensive Rebound Percentage
    - E_REB_PCT: Estimated Total Rebound Percentage
    - E_TM_TOV_PCT: Estimated Team Turnover Percentage
    - E_USG_PCT: Estimated Usage Percentage

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.
    - **season_type** (str, optional): e.g., "Regular Season". Default: "Regular Season".
    - **league_id** (str, optional): League ID. Default: "00" (NBA).

    Successful Response (200 OK):
    Returns a dictionary containing parameters and player estimated metrics.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid.
    - 500 Internal Server Error / 502 Bad Gateway: For unexpected errors.
    """
    logger.info(f"Received GET /league/player-estimated-metrics request. Season: {season}, Type: {season_type}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    estimated_metrics_kwargs = {
        "season": season_to_use,
        "season_type": season_type,
        "league_id": league_id
    }

    return await _handle_league_stats_logic_call(
        fetch_player_estimated_metrics_logic, "player estimated metrics",
        **estimated_metrics_kwargs
    )

@router.get(
    "/team-estimated-metrics",
    summary="Get League-Wide Team Estimated Metrics",
    description="Fetches estimated metrics for all teams including offensive/defensive ratings, pace, etc.",
    response_model=Dict[str, Any]
)
async def get_league_team_estimated_metrics_endpoint(
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON} in logic.", regex=r"^\d{4}-\d{2}$"),
    season_type: Optional[str] = Query("", description="Type of season. Default: '' (Regular Season)."),
    league_id: Optional[str] = Query("00", description="League ID. Default: '00' (NBA).")
) -> Dict[str, Any]:
    """
    Endpoint to retrieve league-wide team estimated metrics.
    Uses `fetch_team_estimated_metrics_logic` from `team_estimated_metrics.py`.

    This endpoint provides estimated metrics for all teams:
    - E_OFF_RATING: Estimated Offensive Rating
    - E_DEF_RATING: Estimated Defensive Rating
    - E_NET_RATING: Estimated Net Rating
    - E_PACE: Estimated Pace
    - E_AST_RATIO: Estimated Assist Ratio
    - E_OREB_PCT: Estimated Offensive Rebound Percentage
    - E_DREB_PCT: Estimated Defensive Rebound Percentage
    - E_REB_PCT: Estimated Total Rebound Percentage
    - E_TM_TOV_PCT: Estimated Team Turnover Percentage

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.
    - **season_type** (str, optional): Season type. Default: "".
    - **league_id** (str, optional): League ID. Default: "00".

    Successful Response (200 OK):
    Returns a dictionary containing parameters and team estimated metrics.

    Error Responses:
    - 400 Bad Request: If query parameters are invalid.
    - 500 Internal Server Error / 502 Bad Gateway: For unexpected errors.
    """
    logger.info(f"Received GET /league/team-estimated-metrics request. Season: {season}, Type: {season_type}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    team_estimated_metrics_kwargs = {
        "season": season_to_use,
        "season_type": season_type,
        "league_id": league_id
    }

    return await _handle_league_stats_logic_call(
        fetch_team_estimated_metrics_logic, "team estimated metrics",
        **team_estimated_metrics_kwargs
    )

@router.get(
    "/comprehensive-data",
    summary="Get Comprehensive League Data",
    description="Loads all league data efficiently for team/player pages to avoid multiple API calls.",
    response_model=Dict[str, Any]
)
async def get_comprehensive_league_data_endpoint(
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON}.", regex=r"^\d{4}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to load comprehensive league data efficiently.

    This endpoint loads all player and team data at once to avoid multiple API calls:
    - Basic player statistics
    - Advanced player statistics
    - Player estimated metrics
    - Team statistics
    - Team estimated metrics
    - League averages

    This data can then be used to populate individual team/player pages efficiently.

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.

    Successful Response (200 OK):
    Returns comprehensive league data with status and counts.

    Error Responses:
    - 400 Bad Request: If season format is invalid.
    - 500 Internal Server Error: For unexpected errors.
    """
    logger.info(f"Received GET /league/comprehensive-data request. Season: {season}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    try:
        result = await get_comprehensive_league_data(season_to_use)
        return result
    except Exception as e:
        logger.error(f"Error in comprehensive league data endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error loading comprehensive data: {str(e)}")

@router.get(
    "/player-advanced-analytics/{player_id}",
    summary="Get Advanced Player Analytics",
    description="Get comprehensive advanced analytics for a specific player including custom metrics and percentiles.",
    response_model=Dict[str, Any]
)
async def get_player_advanced_analytics_endpoint(
    player_id: int,
    season: Optional[str] = Query(None, description=f"NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to {settings.CURRENT_NBA_SEASON}.", regex=r"^\d{4}-\d{2}$")
) -> Dict[str, Any]:
    """
    Endpoint to get advanced analytics for a specific player.

    This endpoint provides comprehensive advanced metrics:
    - True Shooting Percentage
    - Effective Field Goal Percentage
    - Points/Rebounds/Assists per minute
    - Usage Rate and Player Impact Estimate
    - Estimated offensive/defensive ratings
    - Percentile rankings vs league

    Path Parameters:
    - **player_id** (int): NBA player ID.

    Query Parameters:
    - **season** (str, optional): YYYY-YY format. Defaults to current season.

    Successful Response (200 OK):
    Returns advanced analytics and percentile rankings for the player.

    Error Responses:
    - 400 Bad Request: If season format is invalid.
    - 404 Not Found: If player not found.
    - 500 Internal Server Error: For unexpected errors.
    """
    logger.info(f"Received GET /league/player-advanced-analytics/{player_id} request. Season: {season}")

    season_to_use = season or settings.CURRENT_NBA_SEASON
    if not validate_season_format(season_to_use):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Errors.INVALID_SEASON_FORMAT.format(season=season_to_use))

    try:
        result = await get_player_advanced_analytics(player_id, season_to_use)

        if 'error' in result.get('advanced_metrics', {}):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player {player_id} not found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in player advanced analytics endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error calculating advanced analytics: {str(e)}")