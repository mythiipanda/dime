"""Test script for NBA Team Tracking API endpoints.

This script tests all team tracking-related endpoints including passing,
rebounding, and shooting statistics. It includes validation for response
structures and error cases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT

# Test configuration
TEST_TEAM_ID = 1610612747  # Los Angeles Lakers
TEST_SEASON = CURRENT_SEASON
INVALID_TEAM_ID = 9999999  # For error testing

def analyze_response(response: Dict[str, Any], endpoint_name: str = None) -> None:
    """Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response to analyze
        endpoint_name: Optional name of the endpoint for logging
    """
    if endpoint_name:
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

def validate_passing_stats(stats: Dict[str, Any]) -> bool:
    """Validates team passing statistics structure.
    
    Args:
        stats: Passing stats data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        "passes_made", "passes_received"
    }
    
    if not all(field in stats for field in required_fields):
        print(f"Missing required fields in passing stats: {required_fields - set(stats.keys())}")
        return False
        
    # Validate individual pass records
    for pass_list in stats["passes_made"]:
        if not all(field in pass_list for field in ["pass_from", "frequency", "passes", "assists", "shooting"]):
            print("Invalid pass made record structure")
            return False
            
    for pass_list in stats["passes_received"]:
        if not all(field in pass_list for field in ["pass_to", "frequency", "passes", "assists", "shooting"]):
            print("Invalid pass received record structure")
            return False
            
    return True

def validate_rebounding_stats(stats: Dict[str, Any]) -> bool:
    """Validates team rebounding statistics structure.
    
    Args:
        stats: Rebounding stats data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        "overall", "shot_type", "shot_distance", "rebound_distance"
    }
    
    if not all(field in stats for field in required_fields):
        print(f"Missing required fields in rebounding stats: {required_fields - set(stats.keys())}")
        return False
        
    # Validate overall structure
    overall_fields = {
        "total", "offensive", "defensive", "contested",
        "uncontested", "contested_pct"
    }
    if not all(field in stats["overall"] for field in overall_fields):
        print(f"Missing required fields in overall rebounding: {overall_fields - set(stats['overall'].keys())}")
        return False
        
    return True

def validate_shooting_stats(stats: Dict[str, Any]) -> bool:
    """Validates team shooting statistics structure.
    
    Args:
        stats: Shooting stats data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        "general", "shot_clock", "dribbles", "touch_time",
        "defender_distance"
    }
    
    if not all(field in stats for field in required_fields):
        print(f"Missing required fields in shooting stats: {required_fields - set(stats.keys())}")
        return False
        
    # Validate shot type records
    for shot_type, data in stats["general"].items():
        required_shot_fields = {
            "frequency", "fgm", "fga", "fg_pct", "efg_pct"
        }
        if not all(field in data for field in required_shot_fields):
            print(f"Invalid shot type record structure for {shot_type}")
            return False
            
    return True

def get_raw_team_passing(
    team_id: int = TEST_TEAM_ID,
    season: str = TEST_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the team passing tracking endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get stats for
        season_type: Type of season (regular, playoffs, etc.)
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Passing Tracking ===\n")
    
    try:
        pass_stats = teamdashptpass.TeamDashPtPass(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "teamdashptpass",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season,
                    "season_type": season_type,
                    "per_mode": per_mode
                }
            },
            "data": {
                "passes_made": pass_stats.passes_made.get_dict(),
                "passes_received": pass_stats.passes_received.get_dict()
            }
        }
        
        analyze_response(result, "Team Passing Tracking")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teamdashptpass",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Passing Tracking")
        return error_result

def get_raw_team_rebounding(
    team_id: int = TEST_TEAM_ID,
    season: str = TEST_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the team rebounding tracking endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get stats for
        season_type: Type of season (regular, playoffs, etc.)
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Rebounding Tracking ===\n")
    
    try:
        reb_stats = teamdashptreb.TeamDashPtReb(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "teamdashptreb",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season,
                    "season_type": season_type,
                    "per_mode": per_mode
                }
            },
            "data": {
                "overall": reb_stats.overall_rebounding.get_dict(),
                "shot_type": reb_stats.shot_type_rebounding.get_dict(),
                "shot_distance": reb_stats.shot_distance_rebounding.get_dict(),
                "rebound_distance": reb_stats.reb_distance_rebounding.get_dict()
            }
        }
        
        analyze_response(result, "Team Rebounding Tracking")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teamdashptreb",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Rebounding Tracking")
        return error_result

def get_raw_team_shooting(
    team_id: int = TEST_TEAM_ID,
    season: str = TEST_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the team shooting tracking endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get stats for
        season_type: Type of season (regular, playoffs, etc.)
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Shooting Tracking ===\n")
    
    try:
        shot_stats = teamdashptshots.TeamDashPtShots(
            team_id=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_simple=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "teamdashptshots",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season,
                    "season_type": season_type,
                    "per_mode": per_mode
                }
            },
            "data": {
                "general": shot_stats.general_shooting.get_dict(),
                "shot_clock": shot_stats.shot_clock_shooting.get_dict(),
                "dribbles": shot_stats.dribble_shooting.get_dict(),
                "touch_time": shot_stats.touch_time_shooting.get_dict(),
                "defender_distance": shot_stats.closest_defender_shooting.get_dict()
            }
        }
        
        analyze_response(result, "Team Shooting Tracking")
        return result
        
    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teamdashptshots",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Shooting Tracking")
        return error_result

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_team_id": {
            "passing": get_raw_team_passing(team_id=INVALID_TEAM_ID),
            "rebounding": get_raw_team_rebounding(team_id=INVALID_TEAM_ID),
            "shooting": get_raw_team_shooting(team_id=INVALID_TEAM_ID)
        },
        "invalid_season": {
            "passing": get_raw_team_passing(season="2023"),
            "rebounding": get_raw_team_rebounding(season="invalid"),
            "shooting": get_raw_team_shooting(season="2023-99")
        }
    }
    
    return results

def main():
    """Run all team tracking tests and save results."""
    print("Testing Team Tracking endpoints...")
    
    # Run all tests
    results = {
        "passing": {
            "per_game": get_raw_team_passing(per_mode=PerModeDetailed.per_game),
            "totals": get_raw_team_passing(per_mode=PerModeDetailed.totals)
        },
        "rebounding": {
            "per_game": get_raw_team_rebounding(per_mode=PerModeDetailed.per_game),
            "totals": get_raw_team_rebounding(per_mode=PerModeDetailed.totals)
        },
        "shooting": {
            "per_game": get_raw_team_shooting(per_mode=PerModeDetailed.per_game),
            "totals": get_raw_team_shooting(per_mode=PerModeDetailed.totals)
        },
        "error_cases": test_error_cases()
    }
    
    # Validate responses
    print("\n=== Validating Responses ===\n")
    
    if results["passing"]["per_game"]["data"]:
        print("Validating passing stats...")
        is_valid = validate_passing_stats(results["passing"]["per_game"]["data"])
        print(f"Passing stats validation: {'Passed' if is_valid else 'Failed'}")
        
    if results["rebounding"]["per_game"]["data"]:
        print("\nValidating rebounding stats...")
        is_valid = validate_rebounding_stats(results["rebounding"]["per_game"]["data"])
        print(f"Rebounding stats validation: {'Passed' if is_valid else 'Failed'}")
        
    if results["shooting"]["per_game"]["data"]:
        print("\nValidating shooting stats...")
        is_valid = validate_shooting_stats(results["shooting"]["per_game"]["data"])
        print(f"Shooting stats validation: {'Passed' if is_valid else 'Failed'}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"team_tracking_raw_output_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main()