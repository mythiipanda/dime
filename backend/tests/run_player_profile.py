"""Test script for NBA Player Profile logic.

Tests the fetch_player_profile_logic function from backend.api_tools.player_tools.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any

from nba_api.stats.library.parameters import PerModeDetailed
from backend.config import CURRENT_SEASON
from backend.api_tools.player_tools import fetch_player_profile_logic

# Test configuration
EXAMPLE_PLAYER = "LeBron James"
INVALID_PLAYER = "Invalid Player XYZ"
CURRENT_PLAYER = "Victor Wembanyama"

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
            
        print(f"Success! Found profile for {response.get('player_name', 'Unknown Player')}.")
        print("Data Sections:", list(response.keys()))
        if response.get('career_highs'):
             print("Career Highs Sample:", list(response['career_highs'].keys())[:5]) # Show first 5 keys
        if response.get('next_game'):
             print("Next Game Info:", response['next_game'])
        return response
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return {"error": str(e)}

def test_player_profile(
    player_name: str = EXAMPLE_PLAYER,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the player profile tool."""
    print(f"\n=== Testing Player Profile Tool for '{player_name}', Mode: {per_mode} ===\n")
    
    result = fetch_player_profile_logic(player_name, per_mode)
    return {
        "meta": {
            "tool": "fetch_player_profile_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "per_mode": per_mode
            }
        },
        "response": analyze_response(result, "Player Profile Tool")
    }

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_player": test_player_profile(player_name=INVALID_PLAYER),
        "invalid_per_mode": test_player_profile(player_name=EXAMPLE_PLAYER, per_mode="invalid_mode")
    }
    
    return results

def main():
    """Run all player profile tests and save results."""
    print("Testing Player Profile Tool...")
    
    results = {
        "lebron_per_game": test_player_profile(player_name=EXAMPLE_PLAYER, per_mode=PerModeDetailed.per_game),
        "lebron_totals": test_player_profile(player_name=EXAMPLE_PLAYER, per_mode=PerModeDetailed.totals),
        "wemby_per_game": test_player_profile(player_name=CURRENT_PLAYER, per_mode=PerModeDetailed.per_game),
        "error_cases": test_error_cases()
    }
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"player_profile_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 