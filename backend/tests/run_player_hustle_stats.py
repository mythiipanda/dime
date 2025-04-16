"""Test script for NBA Player Hustle Stats logic.

Tests the fetch_player_hustle_stats_logic function from backend.api_tools.player_tools.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any

from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed
from backend.config import CURRENT_SEASON
from backend.api_tools.player_tools import fetch_player_hustle_stats_logic

# Test configuration
INVALID_SEASON = "2023/24"  # Invalid season format

# Create output directory if it doesn't exist
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def analyze_response(response_str: str, endpoint_name: str) -> Dict[str, Any]:
    """Analyzes and prints information about the tool response."""
    print(f"\nAnalyzing response from {endpoint_name}:")
    
    try:
        response = json.loads(response_str)
        if "error" in response:
            print(f"Error: {response['error']}")
            return response
            
        print(f"Success! Found hustle stats for {len(response.get('hustle_stats', []))} players.")
        if response.get('hustle_stats'):
             print("Sample record structure:")
             print(json.dumps(response['hustle_stats'][0], indent=2))
        return response
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return {"error": str(e)}

def test_player_hustle_stats(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the player hustle stats tool."""
    print(f"\n=== Testing Player Hustle Stats Tool for Season: {season}, Type: {season_type}, Mode: {per_mode} ===\n")
    
    result = fetch_player_hustle_stats_logic(season, season_type, per_mode)
    return {
        "meta": {
            "tool": "fetch_player_hustle_stats_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        },
        "response": analyze_response(result, "Player Hustle Stats Tool")
    }

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_season": test_player_hustle_stats(season=INVALID_SEASON),
        "invalid_per_mode": test_player_hustle_stats(per_mode="invalid_mode"),
        "invalid_season_type": test_player_hustle_stats(season_type="invalid_type")
    }
    
    return results

def main():
    """Run all player hustle stats tests and save results."""
    print("Testing Player Hustle Stats Tool...")
    
    results = {
        "per_game": test_player_hustle_stats(per_mode=PerModeDetailed.per_game),
        "totals": test_player_hustle_stats(per_mode=PerModeDetailed.totals),
        "per36": test_player_hustle_stats(per_mode=PerModeDetailed.per_36),
        "error_cases": test_error_cases()
    }
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"player_hustle_stats_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 