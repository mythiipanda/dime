# test_hustle.py
import asyncio
import json
from backend.api_tools.player_dashboard_stats import fetch_player_hustle_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeTime

async def main():
    season = "2023-24"
    season_type = SeasonTypeAllStar.regular
    per_mode = PerModeTime.per_game

    player_name_test = "Alex Caruso"
    print(f"--- Testing Hustle Stats for Player: {player_name_test} ---")
    result_player_json = await asyncio.to_thread(
        fetch_player_hustle_stats_logic,
        player_name=player_name_test,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    try:
        result_player_data = json.loads(result_player_json)
        print(json.dumps(result_player_data, indent=4))
        if "error" not in result_player_data and "hustle_stats" in result_player_data:
            if result_player_data["hustle_stats"]:
                print(f"\nSUCCESS: Fetched hustle stats for {player_name_test}. Count: {len(result_player_data['hustle_stats'])}")
            else:
                print(f"\nNOTE: No hustle stats found for player {player_name_test} with these criteria, or player not in data for this season/type.")
        elif "error" in result_player_data:
            print(f"\nERROR: {result_player_data['error']}")
        else:
            print("\nWARNING: Unexpected response structure for player hustle stats.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for player hustle: {result_player_json}")

    print("\n" + "="*50 + "\n")

    team_id_test = 1610612741 
    print(f"--- Testing Hustle Stats for Team ID: {team_id_test} ---")
    result_team_json = await asyncio.to_thread(
        fetch_player_hustle_stats_logic,
        team_id=team_id_test,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    try:
        result_team_data = json.loads(result_team_json)
        print(json.dumps(result_team_data, indent=4))
        if "error" not in result_team_data and "hustle_stats" in result_team_data:
            print(f"\nSUCCESS: Fetched hustle stats for Team ID {team_id_test}. Count: {len(result_team_data['hustle_stats'])}")
        elif "error" in result_team_data:
            print(f"\nERROR: {result_team_data['error']}")
        else:
            print("\nWARNING: Unexpected response structure for team hustle stats.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for team hustle: {result_team_json}")
        
    print("\n" + "="*50 + "\n")

    print(f"--- Testing League-Wide Hustle Stats (Limited) ---")
    result_league_json = await asyncio.to_thread(
        fetch_player_hustle_stats_logic,
        season=season,
        season_type=season_type,
        per_mode=per_mode
    )
    try:
        result_league_data = json.loads(result_league_json)
        if "error" not in result_league_data and "hustle_stats" in result_league_data:
            print(f"\nSUCCESS: Fetched league-wide hustle stats. Count: {len(result_league_data['hustle_stats'])}")
            if result_league_data["hustle_stats"]:
                 print("Sample of first league hustle entry:")
                 print(json.dumps(result_league_data["hustle_stats"][0], indent=4))
        elif "error" in result_league_data:
            print(f"\nERROR: {result_league_data['error']}")
        else:
            print("\nWARNING: Unexpected response structure for league hustle stats.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response for league hustle: {result_league_json}")

if __name__ == "__main__":
    asyncio.run(main())