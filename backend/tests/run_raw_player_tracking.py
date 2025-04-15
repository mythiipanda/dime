"""
Raw output test script for NBA Player Tracking API endpoints.
Tests raw responses from clutch, shooting, rebounding, passing, and player info endpoints.
"""

from typing import Dict, Any
from nba_api.stats.endpoints import (
    playerdashboardbyclutch,
    playerdashboardbyshootingsplits,
    playerdashptreb,
    playerdashptpass,
    commonplayerinfo,
    playerdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)
import json
from datetime import datetime

# Test configuration
TEST_PLAYER_ID = "2544"  # LeBron James
TEST_SEASON = "2023-24"
DEFAULT_TIMEOUT = 30

def get_raw_player_info(player_id: str = TEST_PLAYER_ID) -> Dict[str, Any]:
    """
    Fetches raw player info directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        
    Returns:
        Dict containing raw API response
    """
    try:
        info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id
                }
            },
            "data": info.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_clutch_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw clutch stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        clutch_stats = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashboardbyclutch",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "season": season
                }
            },
            "data": clutch_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashboardbyclutch",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shooting_splits(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw shooting splits directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        shooting_stats = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
            player_id=player_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashboardbyshootingsplits",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "season": season
                }
            },
            "data": shooting_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashboardbyshootingsplits",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_rebounding_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw rebounding stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        reb_stats = playerdashptreb.PlayerDashPtReb(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptreb",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": reb_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptreb",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_passing_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw passing stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        pass_stats = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptpass",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": pass_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptpass",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shot_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw shot stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        shot_stats = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptshots",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": shot_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptshots",
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
    print("Parameters:", response['meta']['params'])
    
    # Analyze data structure
    data = response["data"]
    print("\nTop-level keys:", list(data.keys()))
    
    # Look for common data structures
    for key in data:
        if isinstance(data[key], list):
            print(f"\n{key} contains {len(data[key])} records")
            if data[key]:
                print(f"Sample {key} keys:", list(data[key][0].keys()) if isinstance(data[key][0], dict) else "Not a dict")

def main():
    """
    Main execution function that tests all player tracking endpoints.
    """
    print(f"Testing Player Tracking endpoints with Player ID: {TEST_PLAYER_ID}, Season: {TEST_SEASON}")
    
    # Dictionary to store all responses
    responses = {
        "player_info": get_raw_player_info(),
        "clutch_stats": get_raw_clutch_stats(),
        "shooting_splits": get_raw_shooting_splits(),
        "rebounding_stats": get_raw_rebounding_stats(),
        "passing_stats": get_raw_passing_stats(),
        "shot_stats": get_raw_shot_stats()
    }
    
    # Analyze each response
    for endpoint_name, response in responses.items():
        print(f"\n=== Testing {endpoint_name} ===")
        analyze_response(response)
    
    # Save full raw responses to file for detailed analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"player_tracking_raw_output_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(responses, f, indent=2, default=str)
    print(f"\nFull raw output saved to {filename}")

if __name__ == "__main__":
    main()