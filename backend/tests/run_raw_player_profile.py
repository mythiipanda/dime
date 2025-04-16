"""Raw output test script for NBA Player Profile V2 endpoint.

Tests raw responses from playerprofilev2 endpoint.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from typing import Dict, Any

from nba_api.stats.endpoints import playerprofilev2
from nba_api.stats.library.parameters import PerModeDetailed
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT

# Test configuration
EXAMPLE_PLAYER_ID = 2544  # LeBron James
INVALID_PLAYER_ID = 99999999

# Create output directory if it doesn't exist
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_raw_profile(player_id: int, per_mode: str = PerModeDetailed.per_game) -> Dict[str, Any]:
    """Fetches raw profile data directly from the NBA API."""
    try:
        profile = playerprofilev2.PlayerProfileV2(
            player_id=player_id,
            per_mode36=per_mode, # API uses per_mode36
            timeout=DEFAULT_TIMEOUT
        )
        
        # Extract all available dataframes
        data_frames = {}
        for attr in dir(profile):
            if not attr.startswith('_') and hasattr(getattr(profile, attr), 'get_dict'):
                try:
                    data_frames[attr] = getattr(profile, attr).get_dict()
                except Exception as e:
                    print(f"Warning: Could not get dict for {attr}: {e}")
                    data_frames[attr] = None # Store None if get_dict fails
        
        return {
            "meta": {
                "endpoint": "playerprofilev2",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "player_id": player_id,
                    "per_mode": per_mode
                }
            },
            "data": data_frames
        }
        
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerprofilev2",
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
    print("\nAvailable data sections:", list(data.keys()))
    
    for section, content in data.items():
        if content is None:
             print(f"\n{section}: Failed to retrieve data.")
             continue

        # Check if content itself is the result set dictionary 
        # or if it contains a 'resultSets' key
        result_set_data = None
        if isinstance(content, dict):
            if "resultSets" in content and content["resultSets"]:
                 result_set_data = content["resultSets"][0] # Standard nba_api structure
            elif "headers" in content and "rowSet" in content:
                 result_set_data = content # Sometimes the dict *is* the result set
        
        if result_set_data:
            record_count = len(result_set_data.get("rowSet", []))
            headers = result_set_data.get("headers", [])
            print(f"\n{section} contains {record_count} records")
            if record_count > 0:
                print(f"  Headers: {headers}")
        else:
            # Handle cases where content might be a simple list or other structure if needed
            print(f"\n{section}: Non-standard format or empty - Type: {type(content)}")

def main():
    """Run raw API tests and save results."""
    print(f"Testing Player Profile V2 endpoint for Player ID: {EXAMPLE_PLAYER_ID}")
    
    results = {
        "lebron_per_game": get_raw_profile(EXAMPLE_PLAYER_ID, PerModeDetailed.per_game),
        "lebron_totals": get_raw_profile(EXAMPLE_PLAYER_ID, PerModeDetailed.totals),
        "lebron_per_36": get_raw_profile(EXAMPLE_PLAYER_ID, PerModeDetailed.per_36),
        "invalid_player": get_raw_profile(INVALID_PLAYER_ID),
        "invalid_per_mode": get_raw_profile(EXAMPLE_PLAYER_ID, "Invalid")
    }
    
    for test_name, response in results.items():
        print(f"\n=== Analyzing Test: {test_name} ===")
        analyze_response(response)
    
    # Save results to test_output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"player_profile_raw_output_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main() 