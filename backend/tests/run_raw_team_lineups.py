"""Raw output test script for NBA League Lineups endpoint.

Tests raw responses from leaguedashlineups endpoint.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any, Optional

from nba_api.stats.endpoints import leaguedashlineups
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT

# Test configuration
EXAMPLE_TEAM_ID = 1610612747  # Lakers

# Create output directory if it doesn't exist
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_raw_lineups(
    team_id: Optional[int] = None,
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeDetailedDefense.base,
    month: int = 0,
    opponent_team_id: int = 0,
    last_n_games: int = 0
) -> Dict[str, Any]:
    """Fetches raw lineup data directly from the NBA API."""
    try:
        lineups = leaguedashlineups.LeagueDashLineups(
            team_id_nullable=team_id,
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed_defense=measure_type,
            month=month,
            opponent_team_id=opponent_team_id,
            last_n_games=last_n_games,
            timeout=DEFAULT_TIMEOUT
        )
        
        lineups_raw = lineups.lineups.get_dict()
        processed_lineups = []
        if "resultSets" in lineups_raw:
            headers = lineups_raw["resultSets"][0]["headers"]
            for row in lineups_raw["resultSets"][0].get("rowSet", []):
                 processed_lineups.append(dict(zip(headers, row)))

        return {
            "meta": {
                "endpoint": "leaguedashlineups",
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
            "data": {
                "lineups": processed_lineups
            }
        }
        
    except Exception as e:
        return {
            "meta": {
                "endpoint": "leaguedashlineups",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def analyze_response(response: Dict[str, Any]) -> None:
    """Analyzes and prints information about the API response structure."""
    if response["data"] is None:
        print(f"Error: {response['meta'].get('error', 'Unknown error')}")
        return

    print(f"\nEndpoint: {response['meta']['endpoint']}")
    print("Parameters:", response['meta']['parameters'])
    
    data = response["data"]
    if isinstance(data, dict) and 'lineups' in data:
        lineups_list = data['lineups']
        print(f"\nFound {len(lineups_list)} lineup records")
        if lineups_list:
            print(f"Sample lineup keys:", list(lineups_list[0].keys()))

def main():
    """Run raw API tests and save results."""
    print("Testing League Dash Lineups endpoint...")
    
    results = {
        "all_teams_current_season_base": get_raw_lineups(),
        "lakers_current_season_advanced": get_raw_lineups(
            team_id=EXAMPLE_TEAM_ID,
            measure_type=MeasureTypeDetailedDefense.advanced
         ),
         "all_teams_last_10_games": get_raw_lineups(
             last_n_games=10
         ),
         "lakers_vs_clippers": get_raw_lineups(
             team_id=EXAMPLE_TEAM_ID,
             opponent_team_id=1610612746 # Clippers ID
         ),
         "all_teams_december": get_raw_lineups(
             month=3 # December is month 3 (Oct=1, Nov=2, Dec=3)
         )
    }
    
    for test_name, response in results.items():
        print(f"\n=== Analyzing Test: {test_name} ===")
        analyze_response(response)
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"team_lineups_raw_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 