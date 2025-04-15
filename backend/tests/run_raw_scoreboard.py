"""
Raw output test script for NBA Live Scoreboard API endpoint.
This script makes direct API calls to understand the unprocessed data structure.
"""

from typing import Dict, Any
from nba_api.live.nba.endpoints import scoreboard
import json
import sys
from datetime import datetime

def get_raw_scoreboard() -> Dict[str, Any]:
    """
    Fetches raw scoreboard data directly from the NBA API without any processing.
    
    Returns:
        Dict[str, Any]: Complete raw response from the NBA API
        
    Raises:
        Exception: If API call fails or data cannot be retrieved
    """
    try:
        # Direct API call
        board = scoreboard.ScoreBoard()
        
        # Get raw dictionary data
        raw_data = board.get_dict()
        
        return {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "endpoint": "scoreboard",
                "version": "raw"
            },
            "data": raw_data
        }
        
    except Exception as e:
        return {
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "endpoint": "scoreboard",
                "version": "raw",
                "error": str(e)
            },
            "data": None
        }

def main():
    """
    Main execution function that fetches and displays raw API data.
    """
    print("Fetching raw NBA Live Scoreboard data...")
    
    result = get_raw_scoreboard()
    
    # Pretty print the result
    print("\nRaw Response Structure:")
    print(json.dumps(result, indent=2, default=str))
    
    # Additional analysis
    if result["data"]:
        print("\nTop-level keys in response:")
        print(list(result["data"].keys()))
        
        if "games" in result["data"]:
            print(f"\nNumber of games: {len(result['data']['games'])}")
            
            if result["data"]["games"]:
                print("\nSample game keys:")
                print(list(result["data"]["games"][0].keys()))

if __name__ == "__main__":
    main()