"""
Advanced Analytics Routes for NBA Data

This module provides FastAPI routes for advanced NBA analytics including:
- RAPTOR-style player ratings
- Advanced team efficiency metrics
- Player impact analysis
- Lineup effectiveness analysis
- Shot quality and expected value metrics
- Clutch performance analysis
- Matchup advantages analysis
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime

# Import our API tools
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_tools.advanced_metrics import fetch_player_advanced_analysis_logic, find_similar_players
from api_tools.league_dash_player_stats import get_league_player_stats
from api_tools.league_dash_team_stats import get_league_team_stats
from api_tools.player_clutch import get_player_clutch_stats
from api_tools.league_lineups import get_league_lineups
from api_tools.player_estimated_metrics import get_player_estimated_metrics
from api_tools.team_estimated_metrics import get_team_estimated_metrics
from api_tools.matchup_tools import get_player_season_matchups
from api_tools.shot_charts import get_player_shot_chart_data
from api_tools.player_shooting_tracking import get_player_shots_tracking
from api_tools.team_shooting_tracking import get_team_shooting_stats

router = APIRouter(prefix="/advanced-analytics", tags=["Advanced Analytics"])

@router.get("/raptor-metrics")
async def get_raptor_metrics(
    season: str = Query("2024-25", description="NBA season (e.g., '2024-25')"),
    player_id: Optional[int] = Query(None, description="Specific player ID"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Get RAPTOR-style advanced metrics for players

    RAPTOR (Robust Algorithm using Player Tracking and On/off Ratings) is an advanced
    metric that estimates a player's impact on team performance per 100 possessions.
    """
    try:
        if player_id:
            result = get_player_raptor_metrics(
                player_id=player_id,
                season=season,
                return_dataframe=return_dataframe
            )
        else:
            # Return league-wide RAPTOR metrics
            result = {"error": "League-wide RAPTOR metrics not yet implemented. Please provide a player_id."}

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating RAPTOR metrics: {str(e)}")

@router.get("/player-impact")
async def get_player_impact_analysis(
    player_id: int = Query(..., description="Player ID"),
    season: str = Query("2024-25", description="NBA season"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Comprehensive player impact analysis including:
    - Advanced metrics (PER, BPM, VORP, Win Shares)
    - On/off court impact
    - Clutch performance
    - Shot quality metrics
    - Similar player comparisons
    """
    try:
        # Get advanced metrics using the available function
        from api_tools.utils import get_player_name_from_id
        player_name = get_player_name_from_id(player_id)

        if not player_name:
            raise HTTPException(status_code=404, detail=f"Player with ID {player_id} not found")

        # Get comprehensive advanced analysis
        advanced_analysis = fetch_player_advanced_analysis_logic(
            player_name=player_name,
            season=season,
            return_dataframe=return_dataframe
        )

        # Get clutch stats
        clutch_stats = get_player_clutch_stats(
            player_id=player_id,
            season=season,
            return_dataframe=return_dataframe
        )

        # Get shooting tracking
        shooting_tracking = get_player_shots_tracking(
            player_id=player_id,
            season=season,
            return_dataframe=return_dataframe
        )

        # Get shot chart data for shot quality analysis
        shot_chart = get_player_shot_chart_data(
            player_id=player_id,
            season=season,
            return_dataframe=return_dataframe
        )

        result = {
            "player_id": player_id,
            "player_name": player_name,
            "season": season,
            "advanced_analysis": advanced_analysis,
            "clutch_performance": clutch_stats,
            "shooting_tracking": shooting_tracking,
            "shot_quality": shot_chart,
            "analysis_timestamp": datetime.now().isoformat()
        }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing player impact: {str(e)}")

@router.get("/team-efficiency")
async def get_team_efficiency_metrics(
    team_id: Optional[int] = Query(None, description="Specific team ID"),
    season: str = Query("2024-25", description="NBA season"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Advanced team efficiency analysis including:
    - Offensive and defensive efficiency
    - Pace and possession metrics
    - Four factors analysis
    - Lineup effectiveness
    - Shot quality metrics
    """
    try:
        # Get basic team stats
        team_stats = await get_league_team_stats(
            season=season,
            measure_type="Advanced",
            return_dataframe=True
        )

        # Get estimated metrics
        estimated_metrics = await get_team_estimated_metrics(
            season=season,
            return_dataframe=True
        )

        # Get team shooting tracking
        shooting_tracking = await get_team_shooting_stats(
            season=season,
            return_dataframe=True
        )

        # Get lineup data
        lineup_data = await get_league_lineups(
            season=season,
            group_quantity=5,  # 5-man lineups
            measure_type="Advanced",
            return_dataframe=True
        )

        result = {
            "season": season,
            "team_stats": team_stats,
            "estimated_metrics": estimated_metrics,
            "shooting_tracking": shooting_tracking,
            "lineup_effectiveness": lineup_data,
            "analysis_timestamp": datetime.now().isoformat()
        }

        if team_id:
            result["team_id"] = team_id

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing team efficiency: {str(e)}")

@router.get("/lineup-analysis")
async def get_lineup_analysis(
    team_id: Optional[int] = Query(None, description="Specific team ID"),
    season: str = Query("2024-25", description="NBA season"),
    group_quantity: int = Query(5, description="Number of players in lineup (2-5)"),
    min_minutes: float = Query(50.0, description="Minimum minutes played together"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Comprehensive lineup effectiveness analysis including:
    - Net rating and efficiency metrics
    - Offensive and defensive performance
    - Pace and possession data
    - Plus/minus impact
    - Usage and role analysis
    """
    try:
        # Get lineup data
        lineup_data = await get_league_lineups(
            season=season,
            team_id=team_id,
            group_quantity=group_quantity,
            measure_type="Advanced",
            min_min=min_minutes,
            return_dataframe=True
        )

        # Get base lineup stats
        base_lineup_data = await get_league_lineups(
            season=season,
            team_id=team_id,
            group_quantity=group_quantity,
            measure_type="Base",
            min_min=min_minutes,
            return_dataframe=True
        )

        result = {
            "season": season,
            "group_quantity": group_quantity,
            "min_minutes": min_minutes,
            "advanced_lineup_stats": lineup_data,
            "base_lineup_stats": base_lineup_data,
            "analysis_timestamp": datetime.now().isoformat()
        }

        if team_id:
            result["team_id"] = team_id

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing lineups: {str(e)}")

@router.get("/clutch-performance")
async def get_clutch_performance_analysis(
    player_id: Optional[int] = Query(None, description="Specific player ID"),
    team_id: Optional[int] = Query(None, description="Specific team ID"),
    season: str = Query("2024-25", description="NBA season"),
    clutch_time: str = Query("Last 5 Minutes", description="Clutch time definition"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Comprehensive clutch performance analysis including:
    - Performance in close games
    - Late-game efficiency
    - Pressure situation metrics
    - Clutch shooting and decision making
    """
    try:
        if player_id:
            # Get player clutch stats
            clutch_stats = await get_player_clutch_stats(
                player_id=player_id,
                season=season,
                clutch_time=clutch_time,
                return_dataframe=True
            )

            result = {
                "player_id": player_id,
                "season": season,
                "clutch_time": clutch_time,
                "clutch_performance": clutch_stats,
                "analysis_timestamp": datetime.now().isoformat()
            }
        else:
            # Get league-wide clutch performance
            league_clutch = await get_league_player_stats(
                season=season,
                measure_type="Base",
                clutch_time=clutch_time,
                return_dataframe=True
            )

            result = {
                "season": season,
                "clutch_time": clutch_time,
                "league_clutch_performance": league_clutch,
                "analysis_timestamp": datetime.now().isoformat()
            }

        if team_id:
            result["team_id"] = team_id

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing clutch performance: {str(e)}")

@router.get("/shot-quality")
async def get_shot_quality_analysis(
    player_id: Optional[int] = Query(None, description="Specific player ID"),
    team_id: Optional[int] = Query(None, description="Specific team ID"),
    season: str = Query("2024-25", description="NBA season"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Shot quality and expected value analysis including:
    - Shot selection efficiency
    - Expected vs actual field goal percentage
    - Shot difficulty metrics
    - Zone-based shooting analysis
    - Defender distance impact
    """
    try:
        if player_id:
            # Get player shot chart
            shot_chart = await get_player_shot_chart_data(
                player_id=player_id,
                season=season,
                return_dataframe=True
            )

            # Get shooting tracking
            shooting_tracking = await get_player_shots_tracking(
                player_id=player_id,
                season=season,
                return_dataframe=True
            )

            result = {
                "player_id": player_id,
                "season": season,
                "shot_chart_data": shot_chart,
                "shooting_tracking": shooting_tracking,
                "analysis_timestamp": datetime.now().isoformat()
            }
        else:
            # Get team shooting data
            team_shooting = await get_team_shooting_stats(
                season=season,
                team_id=team_id,
                return_dataframe=True
            )

            result = {
                "season": season,
                "team_shooting_data": team_shooting,
                "analysis_timestamp": datetime.now().isoformat()
            }

        if team_id:
            result["team_id"] = team_id

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing shot quality: {str(e)}")

@router.get("/matchup-advantages")
async def get_matchup_advantages(
    player_id: int = Query(..., description="Player ID"),
    season: str = Query("2024-25", description="NBA season"),
    return_dataframe: bool = Query(False, description="Return DataFrame format")
):
    """
    Player vs player matchup analysis including:
    - Head-to-head performance
    - Defensive impact
    - Matchup efficiency
    - Historical performance
    """
    try:
        # Get player matchups
        matchups = await get_player_season_matchups(
            player_id=player_id,
            season=season,
            return_dataframe=True
        )

        result = {
            "player_id": player_id,
            "season": season,
            "matchup_data": matchups,
            "analysis_timestamp": datetime.now().isoformat()
        }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing matchup advantages: {str(e)}")
