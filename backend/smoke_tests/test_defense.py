# test_defense.py
import asyncio
import json
from backend.api_tools.player_dashboard_stats import fetch_player_defense_logic # Corrected import
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeSimple

async def main():
    player_name = "Rudy Gobert" 
    season = "2023-24"        
    season_type = SeasonTypeAllStar.regular
    
    print(f"--- Testing Defense Stats for {player_name} (Default PerMode) ---")
    result_default_json = await asyncio.to_thread(
        fetch_player_defense_logic,
        player_name=player_name,
        season=season,
        season_type=season_type
    )
    try:
        result_default_data = json.loads(result_default_json)
        print(json.dumps(result_default_data, indent=4))
        if "error" not in result_default_data and "summary" in result_default_data:
            print(f"\nSUCCESS: Fetched default per mode defense stats. Games Played: {result_default_data['summary'].get('games_played')}")
        elif "error" in result_default_data:
            print(f"\nERROR: {result_default_data['error']}")
        else:
            print("\nWARNING: Unexpected response structure for default per mode.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for default per_mode: {result_default_json}")

    print("\n" + "="*50 + "\n")

    per_mode_totals = PerModeSimple.totals 
    print(f"--- Testing Defense Stats for {player_name} (PerMode: {per_mode_totals}) ---")
    result_totals_json = await asyncio.to_thread(
        fetch_player_defense_logic,
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode_totals
    )
    try:
        result_totals_data = json.loads(result_totals_json)
        print(json.dumps(result_totals_data, indent=4))
        if "error" not in result_totals_data and "summary" in result_totals_data:
            print(f"\nSUCCESS: Fetched totals per mode defense stats. Games Played: {result_totals_data['summary'].get('games_played')}")
        elif "error" in result_totals_data:
            print(f"\nERROR: {result_totals_data['error']}")
        else:
            print("\nWARNING: Unexpected response structure for totals per mode.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for totals per_mode: {result_totals_json}")

if __name__ == "__main__":
    asyncio.run(main())