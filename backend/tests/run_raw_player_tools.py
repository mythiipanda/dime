"""Test script for NBA Player API endpoints.

This script tests all player-related endpoints including basic info, career stats,
dashboard splits, and player tracking data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional

from nba_api.stats.endpoints import (
    playerdashboardbyclutch,
    playerdashboardbygamesplits,
    playerdashboardbygeneralsplits,
    playerdashboardbylastngames,
    playerdashboardbyshootingsplits,
    playerdashboardbyteamperformance,
    playerdashboardbyyearoveryear,
    playercareerstats,
    commonplayerinfo,
    playerdashptreb,
    playerdashptpass,
    playerdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonAll,
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT

# Test configuration
EXAMPLE_PLAYER_ID = 2544  # LeBron James
INVALID_PLAYER_ID = 99999999  # For error testing

def analyze_response(response: Dict[str, Any], endpoint_name: str) -> None:
    """Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response to analyze
        endpoint_name: Name of the endpoint for logging
    """
    print(f"\nAnalyzing response from {endpoint_name}:")
    
    if response.get("error"):
        print(f"Error: {response['error']}")
        return
        
    meta = response.get("meta", {})
    print(f"Version: {meta.get('version')}")
    print(f"Parameters: {meta.get('parameters')}")
    
    data = response.get("data", {})
    if isinstance(data, list):
        print(f"Found {len(data)} records")
        if data:
            print("\nSample record structure:")
            print(json.dumps(data[0], indent=2))
    elif isinstance(data, dict):
        print("\nData structure:")
        print(json.dumps(list(data.keys()), indent=2))

def test_player_info(player_id: str = EXAMPLE_PLAYER_ID) -> Dict[str, Any]:
    """Test the common player info endpoint.
    
    Args:
        player_id: The NBA player ID to test with
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Common Player Info ===\n")
    
    try:
        info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "parameters": {"player_id": player_id}
            },
            "data": {
                "common_info": info.common_player_info.get_dict(),
                "headline_stats": info.player_headline_stats.get_dict()
            }
        }
        
        analyze_response(result, "Common Player Info")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Common Player Info")
        return error_result

def test_player_career_stats(
    player_id: str = EXAMPLE_PLAYER_ID,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the player career stats endpoint.
    
    Args:
        player_id: The NBA player ID to test with
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Player Career Stats ===\n")
    
    try:
        career = playercareerstats.PlayerCareerStats(
            player_id=player_id,
            per_mode36=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "playercareerstats",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "player_id": player_id,
                    "per_mode": per_mode
                }
            },
            "data": {
                "career_totals_regular_season": career.career_totals_regular_season.get_dict(),
                "career_totals_post_season": career.career_totals_post_season.get_dict(),
                "season_totals_regular_season": career.season_totals_regular_season.get_dict(),
                "season_totals_post_season": career.season_totals_post_season.get_dict()
            }
        }
        
        analyze_response(result, "Player Career Stats")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "playercareerstats",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Player Career Stats")
        return error_result

def test_player_tracking_stats(
    player_id: str = EXAMPLE_PLAYER_ID,
    season: str = CURRENT_SEASON
) -> Dict[str, Any]:
    """Test player tracking endpoints.
    
    Args:
        player_id: The NBA player ID to test with
        season: Season to get stats for
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Player Tracking Stats ===\n")
    
    try:
        # Get player info first to get team ID
        info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        info_dict = info.get_normalized_dict()
        team_id = info_dict["CommonPlayerInfo"][0]["TEAM_ID"]
        
        # Test rebounding stats
        print("\nTesting rebounding stats...")
        reb_stats = playerdashptreb.PlayerDashPtReb(
            player_id=player_id,
            team_id=team_id,
            season=season,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Test passing stats
        print("\nTesting passing stats...")
        pass_stats = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season=season,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Test shot stats
        print("\nTesting shot stats...")
        shot_stats = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            season=season,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "player_tracking",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": {
                "rebounding": {
                    "overall": reb_stats.overall_rebounding.get_dict(),
                    "shot_type": reb_stats.shot_type_rebounding.get_dict(),
                    "num_contested": reb_stats.num_contested_rebounding.get_dict(),
                    "shot_distance": reb_stats.shot_distance_rebounding.get_dict(),
                    "rebound_distance": reb_stats.reb_distance_rebounding.get_dict()
                },
                "passing": {
                    "passes_made": pass_stats.passes_made.get_dict(),
                    "passes_received": pass_stats.passes_received.get_dict()
                },
                "shots": {
                    "overall": shot_stats.overall.get_dict(),
                    "general": shot_stats.general_shooting.get_dict(),
                    "shot_clock": shot_stats.shot_clock_shooting.get_dict(),
                    "dribble": shot_stats.dribble_shooting.get_dict(),
                    "closest_defender": shot_stats.closest_defender_shooting.get_dict(),
                    "touch_time": shot_stats.touch_time_shooting.get_dict()
                }
            }
        }
        
        analyze_response(result, "Player Tracking Stats")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "player_tracking",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Player Tracking Stats")
        return error_result

def test_player_dashboard_splits(
    player_id: str = EXAMPLE_PLAYER_ID,
    season: str = CURRENT_SEASON,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test various player dashboard split endpoints.
    
    Args:
        player_id: The NBA player ID to test with
        season: Season to get stats for
        measure_type: Type of stats to get
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Player Dashboard Splits ===\n")
    
    splits = [
        ("Clutch", playerdashboardbyclutch.PlayerDashboardByClutch),
        ("Game Splits", playerdashboardbygamesplits.PlayerDashboardByGameSplits),
        ("General Splits", playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits),
        ("Last N Games", playerdashboardbylastngames.PlayerDashboardByLastNGames),
        ("Shooting Splits", playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits),
        ("Team Performance", playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance),
        ("Year Over Year", playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear)
    ]
    
    results = {}
    
    for split_name, endpoint in splits:
        print(f"\nTesting {split_name} Dashboard...")
        try:
            dashboard = endpoint(
                player_id=player_id,
                season=season,
                measure_type_detailed_defense=measure_type,
                per_mode_detailed=per_mode,
                timeout=DEFAULT_TIMEOUT
            )
            
            # Get all available data tables
            data_tables = {}
            for attr in dir(dashboard):
                if not attr.startswith('_') and hasattr(getattr(dashboard, attr), 'get_dict'):
                    data_tables[attr] = getattr(dashboard, attr).get_dict()
            
            results[split_name.lower().replace(" ", "_")] = {
                "meta": {
                    "endpoint": endpoint.__name__,
                    "timestamp": datetime.now().isoformat(),
                    "parameters": {
                        "player_id": player_id,
                        "season": season,
                        "measure_type": measure_type,
                        "per_mode": per_mode
                    }
                },
                "data": data_tables
            }
            
        except Exception as e:
            results[split_name.lower().replace(" ", "_")] = {
                "meta": {
                    "endpoint": endpoint.__name__,
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                },
                "data": None
            }
    
    return results

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_player_id": test_player_info(INVALID_PLAYER_ID),
        "invalid_season": test_player_tracking_stats(season="invalid"),
        "invalid_measure_type": test_player_dashboard_splits(measure_type="invalid")
    }
    
    return results

def main():
    """Run all player tools tests and save results."""
    print("Testing Player Tools endpoints...")
    
    # Run all tests
    results = {
        "player_info": test_player_info(),
        "career_stats": {
            "per_game": test_player_career_stats(per_mode=PerModeDetailed.per_game),
            "totals": test_player_career_stats(per_mode=PerModeDetailed.totals),
            "per36": test_player_career_stats(per_mode=PerModeDetailed.per36)
        },
        "tracking_stats": test_player_tracking_stats(),
        "dashboard_splits": test_player_dashboard_splits(),
        "error_cases": test_error_cases()
    }
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"player_tools_raw_output_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main()