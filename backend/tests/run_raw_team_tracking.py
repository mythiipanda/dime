"""
Raw output test script for NBA Team Tracking API endpoints.
Tests raw responses from passing, rebounding, and shooting endpoints.
"""

from typing import Dict, Any
from nba_api.stats.endpoints import (
    teamdashptpass,
    teamdashptreb,
    teamdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)
import json
from datetime import datetime

# Test configuration
TEST_TEAM_ID = "1610612737"  # Atlanta Hawks
TEST_SEASON = "2023-24"
DEFAULT_TIMEOUT = 30

def get_raw_team_passing(team_id: str = TEST_TEAM_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw passing stats directly from the NBA API.
    
    Args:
        team_id: The NBA team ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        passing_stats = teamdashptpass.TeamDashPtPass(
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode_simple=PerModeDetailed.per_game,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "teamdashptpass",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": passing_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "teamdashptpass",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_team_rebounding(team_id: str = TEST_TEAM_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw rebounding stats directly from the NBA API.
    
    Args:
        team_id: The NBA team ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        rebounding_stats = teamdashptreb.TeamDashPtReb(
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode_simple=PerModeDetailed.per_game,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "teamdashptreb",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": rebounding_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "teamdashptreb",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_team_shooting(team_id: str = TEST_TEAM_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw shooting stats directly from the NBA API.
    
    Args:
        team_id: The NBA team ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        shooting_stats = teamdashptshots.TeamDashPtShots(
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode_simple=PerModeDetailed.per_game,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "teamdashptshots",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": shooting_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "teamdashptshots",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def analyze_response(response: Dict[str, Any]) -> None:
    """
    Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response dictionary
    """
    if response["data"] is None:
        print(f"Error: {response['meta'].get('error', 'Unknown error')}")
        return

    print(f"\nEndpoint: {response['meta']['endpoint']}")
    print("Response structure:")
    
    # Analyze top-level keys
    print("\nTop-level keys:")
    print(list(response["data"].keys()))
    
    # If there are resultSets, analyze their structure
    if "resultSets" in response["data"]:
        print("\nResultSets names:")
        for result_set in response["data"]["resultSets"]:
            print(f"- {result_set.get('name', 'unnamed')}")

def main():
    """
    Main execution function that tests all team tracking endpoints.
    """
    print(f"Testing Team Tracking endpoints with Team ID: {TEST_TEAM_ID}, Season: {TEST_SEASON}")
    
    # Test passing stats
    print("\n=== Testing Team Passing Stats ===")
    passing_response = get_raw_team_passing()
    analyze_response(passing_response)
    
    # Test rebounding stats
    print("\n=== Testing Team Rebounding Stats ===")
    rebounding_response = get_raw_team_rebounding()
    analyze_response(rebounding_response)
    
    # Test shooting stats
    print("\n=== Testing Team Shooting Stats ===")
    shooting_response = get_raw_team_shooting()
    analyze_response(shooting_response)
    
    # Save full raw responses to file for detailed analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"team_tracking_raw_output_{timestamp}.json"
    
    full_output = {
        "passing": passing_response,
        "rebounding": rebounding_response,
        "shooting": shooting_response
    }
    
    with open(filename, 'w') as f:
        json.dump(full_output, f, indent=2, default=str)
    print(f"\nFull raw output saved to {filename}")

if __name__ == "__main__":
    main()