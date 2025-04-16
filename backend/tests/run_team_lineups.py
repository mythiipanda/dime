"""Test script for NBA Team Lineups logic.

Tests the fetch_team_lineups_logic function from backend.api_tools.team_tools.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any, Optional

from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)
from backend.config import CURRENT_SEASON
from backend.api_tools.team_tools import fetch_team_lineups_logic

# Test configuration
EXAMPLE_TEAM_ID = 1610612747  # Lakers
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
            
        lineups_data = response.get('lineups', [])
        print(f"Success! Found stats for {len(lineups_data)} lineups.")
        if lineups_data:
             print("Sample lineup record structure:")
             print(json.dumps(lineups_data[0], indent=2))
        print("Applied Filters:", response.get('filters'))
        return response
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return {"error": str(e)}

def test_team_lineups(
    team_id: Optional[int] = None,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base,
    month: int = 0,
    opponent_team_id: int = 0,
    last_n_games: int = 0
) -> Dict[str, Any]:
    """Test the team lineups tool."""
    print(f"\n=== Testing Team Lineups Tool ===\nParams: team_id={team_id}, season={season}, type={season_type}, mode={per_mode}, measure={measure_type}, month={month}, opp={opponent_team_id}, lastN={last_n_games}")
    
    result = fetch_team_lineups_logic(
        team_id=team_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        month=month,
        opponent_team_id=opponent_team_id,
        last_n_games=last_n_games
    )
    return {
        "meta": {
            "tool": "fetch_team_lineups_logic",
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "team_id": team_id,
                "season": season,
                "season_type": season_type,
                "per_mode": per_mode,
                "measure_type": measure_type,
                "month": month,
                "opponent_team_id": opponent_team_id,
                "last_n_games": last_n_games
            }
        },
        "response": analyze_response(result, "Team Lineups Tool")
    }

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_season": test_team_lineups(season=INVALID_SEASON),
        "invalid_per_mode": test_team_lineups(per_mode="invalid_mode"),
        "invalid_measure_type": test_team_lineups(measure_type="invalid_type"),
        "invalid_month": test_team_lineups(month=13),
        "invalid_team_id": test_team_lineups(team_id=99999999) # Assuming this ID is invalid
    }
    
    return results

def main():
    """Run all team lineups tests and save results."""
    print("Testing Team Lineups Tool...")
    
    results = {
        "all_teams_current_season_base": test_team_lineups(),
        "lakers_current_season_advanced": test_team_lineups(
            team_id=EXAMPLE_TEAM_ID,
            measure_type=MeasureTypeDetailedDefense.advanced
         ),
         "all_teams_last_10_games": test_team_lineups(
             last_n_games=10
         ),
         "lakers_vs_clippers": test_team_lineups(
             team_id=EXAMPLE_TEAM_ID,
             opponent_team_id=1610612746 # Clippers ID
         ),
         "all_teams_december": test_team_lineups(
             month=3 # December
         ),
         "error_cases": test_error_cases()
    }
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"team_lineups_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 