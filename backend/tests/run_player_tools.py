"""Test script for NBA Player Tools logic.

This script tests all player-related tool functions from backend.api_tools.player_tools,
including player info, career stats, game logs, awards, shot charts, and defense stats.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any, Optional

from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerMode36,
    PerModeDetailed
)
from backend.config import CURRENT_SEASON
from backend.api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic,
    fetch_player_stats_logic,
    fetch_player_shotchart_logic,
    fetch_player_defense_logic
)

# Test configuration
EXAMPLE_PLAYER = "LeBron James"  # Known valid player
INVALID_PLAYER = "Invalid Player Name"  # For error testing
INVALID_SEASON = "2023/24"  # Invalid season format
CURRENT_PLAYER = "Victor Wembanyama"  # Current player for recent stats

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
            
        print(f"Success! Data structure:")
        print(json.dumps(list(response.keys()), indent=2))
        return response
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return {"error": str(e)}

def test_player_info(player_name: str = EXAMPLE_PLAYER) -> Dict[str, Any]:
    """Test the player info tool."""
    print(f"\n=== Testing Player Info Tool for '{player_name}' ===\n")
    
    result = fetch_player_info_logic(player_name)
    return {
        "meta": {
            "tool": "fetch_player_info_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {"player_name": player_name}
        },
        "response": analyze_response(result, "Player Info Tool")
    }

def test_player_gamelog(
    player_name: str = EXAMPLE_PLAYER,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> Dict[str, Any]:
    """Test the player game log tool."""
    print(f"\n=== Testing Player Game Log Tool for '{player_name}', Season: {season} ===\n")
    
    result = fetch_player_gamelog_logic(player_name, season, season_type)
    return {
        "meta": {
            "tool": "fetch_player_gamelog_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "season": season,
                "season_type": season_type
            }
        },
        "response": analyze_response(result, "Player Game Log Tool")
    }

def test_player_career_stats(
    player_name: str = EXAMPLE_PLAYER,
    per_mode36: str = PerMode36.per_game
) -> Dict[str, Any]:
    """Test the player career stats tool."""
    print(f"\n=== Testing Player Career Stats Tool for '{player_name}' ===\n")
    
    result = fetch_player_career_stats_logic(player_name, per_mode36)
    return {
        "meta": {
            "tool": "fetch_player_career_stats_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "per_mode36": per_mode36
            }
        },
        "response": analyze_response(result, "Player Career Stats Tool")
    }

def test_player_awards(player_name: str = EXAMPLE_PLAYER) -> Dict[str, Any]:
    """Test the player awards tool."""
    print(f"\n=== Testing Player Awards Tool for '{player_name}' ===\n")
    
    result = fetch_player_awards_logic(player_name)
    return {
        "meta": {
            "tool": "fetch_player_awards_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {"player_name": player_name}
        },
        "response": analyze_response(result, "Player Awards Tool")
    }

def test_player_stats(
    player_name: str = EXAMPLE_PLAYER,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> Dict[str, Any]:
    """Test the comprehensive player stats tool."""
    print(f"\n=== Testing Player Stats Tool for '{player_name}', Season: {season} ===\n")
    
    result = fetch_player_stats_logic(player_name, season, season_type)
    return {
        "meta": {
            "tool": "fetch_player_stats_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "season": season,
                "season_type": season_type
            }
        },
        "response": analyze_response(result, "Player Stats Tool")
    }

def test_player_shotchart(
    player_name: str = EXAMPLE_PLAYER,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> Dict[str, Any]:
    """Test the player shot chart tool."""
    print(f"\n=== Testing Player Shot Chart Tool for '{player_name}', Season: {season} ===\n")
    
    result = fetch_player_shotchart_logic(player_name, season, season_type)
    return {
        "meta": {
            "tool": "fetch_player_shotchart_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "season": season,
                "season_type": season_type
            }
        },
        "response": analyze_response(result, "Player Shot Chart Tool")
    }

def test_player_defense(
    player_name: str = EXAMPLE_PLAYER,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the player defense stats tool."""
    print(f"\n=== Testing Player Defense Tool for '{player_name}', Season: {season} ===\n")
    
    result = fetch_player_defense_logic(player_name, season, season_type, per_mode)
    return {
        "meta": {
            "tool": "fetch_player_defense_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "player_name": player_name,
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode
            }
        },
        "response": analyze_response(result, "Player Defense Tool")
    }

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_player": {
            "info": test_player_info(INVALID_PLAYER),
            "gamelog": test_player_gamelog(INVALID_PLAYER),
            "career": test_player_career_stats(INVALID_PLAYER),
            "awards": test_player_awards(INVALID_PLAYER)
        },
        "invalid_season": {
            "gamelog": test_player_gamelog(EXAMPLE_PLAYER, INVALID_SEASON),
            "shotchart": test_player_shotchart(EXAMPLE_PLAYER, INVALID_SEASON),
            "defense": test_player_defense(EXAMPLE_PLAYER, INVALID_SEASON)
        },
        "invalid_per_mode": {
            "career": test_player_career_stats(EXAMPLE_PLAYER, "invalid_mode"),
            "defense": test_player_defense(EXAMPLE_PLAYER, CURRENT_SEASON, SeasonTypeAllStar.regular, "invalid_mode")
        }
    }
    
    return results

def main():
    """Run all player tools tests and save results."""
    print("Testing Player Tools...")
    
    # Run defense test first to avoid timeout issues
    results = {
        "defense": {
            "lebron": test_player_defense(EXAMPLE_PLAYER),
            "wemby": test_player_defense(CURRENT_PLAYER)
        },
        "player_info": test_player_info(),
        "career_stats": {
            "per_game": test_player_career_stats(per_mode36=PerMode36.per_game),
            "totals": test_player_career_stats(per_mode36=PerMode36.totals),
            "per36": test_player_career_stats(per_mode36=PerMode36.per_36)
        },
        "current_player": {
            "info": test_player_info(CURRENT_PLAYER),
            "gamelog": test_player_gamelog(CURRENT_PLAYER),
            "shotchart": test_player_shotchart(CURRENT_PLAYER)
        },
        "comprehensive": test_player_stats(),
        "awards": test_player_awards(),
        "shotchart": test_player_shotchart(),
        "error_cases": test_error_cases()
    }
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"player_tools_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 