"""
Raw output test script for NBA Game API endpoints.
Tests raw responses from boxscore, play-by-play, and shot chart endpoints.
"""

from typing import Dict, Any
from nba_api.stats.endpoints import (
    boxscoretraditionalv2,
    playbyplay,
    shotchartdetail
)
import json
from datetime import datetime

# Test configuration
TEST_GAME_ID = "0022300643"  # Replace with a valid game ID
DEFAULT_TIMEOUT = 30

def get_raw_boxscore(game_id: str = TEST_GAME_ID) -> Dict[str, Any]:
    """
    Fetches raw box score data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        
    Returns:
        Dict containing raw API response
    """
    try:
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "boxscoretraditionalv2",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id
                }
            },
            "data": {
                "player_stats": boxscore.player_stats.get_dict(),
                "team_stats": boxscore.team_stats.get_dict(),
                "team_starter_bench_stats": boxscore.team_starter_bench_stats.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "boxscoretraditionalv2",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_playbyplay(game_id: str = TEST_GAME_ID) -> Dict[str, Any]:
    """
    Fetches raw play-by-play data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        
    Returns:
        Dict containing raw API response
    """
    try:
        pbp = playbyplay.PlayByPlay(
            game_id=game_id,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playbyplay",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id
                }
            },
            "data": {
                "play_by_play": pbp.play_by_play.get_dict(),
                "available_video": pbp.available_video.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playbyplay",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shotchart(game_id: str = TEST_GAME_ID) -> Dict[str, Any]:
    """
    Fetches raw shot chart data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        
    Returns:
        Dict containing raw API response
    """
    try:
        shotchart = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id,
            team_id=0,
            player_id=0,
            context_measure_simple="FGA",
            season_nullable="2023-24",
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "shotchartdetail",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id,
                    "season": "2023-24"
                }
            },
            "data": {
                "shot_chart_detail": shotchart.shot_chart_detail.get_dict(),
                "league_averages": shotchart.league_averages.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "shotchartdetail",
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
    for section, data in response["data"].items():
        print(f"\nSection: {section}")
        if isinstance(data, dict):
            print("Keys:", list(data.keys()))
            
            # If there's resultSet data, analyze its structure
            if "resultSets" in data:
                print("\nResultSets:")
                for result_set in data["resultSets"]:
                    print(f"- Name: {result_set.get('name')}")
                    print(f"  Columns: {result_set.get('headers')}")
                    print(f"  Row count: {len(result_set.get('rowSet', []))}")

def main():
    """
    Main execution function that tests all game tracking endpoints.
    """
    print(f"Testing Game endpoints with Game ID: {TEST_GAME_ID}")
    
    # Dictionary to store all responses
    responses = {
        "boxscore": get_raw_boxscore(),
        "playbyplay": get_raw_playbyplay(),
        "shotchart": get_raw_shotchart()
    }
    
    # Analyze each response
    for endpoint_name, response in responses.items():
        print(f"\n=== Testing {endpoint_name} ===")
        analyze_response(response)
    
    # Save full raw responses to file for detailed analysis
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"game_tools_raw_output_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(responses, f, indent=2, default=str)
    print(f"\nFull raw output saved to {filename}")

if __name__ == "__main__":
    main()