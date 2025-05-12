# backend/smoke_tests/test_game_finder.py
import sys
import os
import asyncio
import json
import logging

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.game_finder import fetch_league_games_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, LeagueID

# Constants for testing
TEAM_ID_LAL = 1610612747 # Los Angeles Lakers
PLAYER_ID_LEBRON = 2544 # LeBron James
SEASON_2022_23 = "2022-23"
SEASON_2023_24 = "2023-24" # Current or recent season for more data

async def run_game_finder_test(test_name: str, **kwargs):
    logger.info(f"--- Testing {test_name} ---")
    logger.info(f"Parameters: {kwargs}")
    
    result_json = await asyncio.to_thread(fetch_league_games_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        elif "games" in result_data:
            games_found = len(result_data["games"])
            logger.info(f"SUCCESS: {test_name} - Found {games_found} games.")
            if games_found > 0 and games_found <= 5: # Print details only for a few games
                logger.info("Sample games:")
                for i, game in enumerate(result_data["games"][:5]):
                    logger.info(f"  Game {i+1}: {game.get('GAME_DATE_FORMATTED', game.get('GAME_DATE'))} - {game.get('MATCHUP')} - Score: {game.get('PTS')}")
            elif games_found == 0:
                 logger.info(f"No games found for {test_name}, which might be expected for very specific criteria.")
            else:
                logger.info(f"First game sample: {result_data['games'][0].get('GAME_DATE_FORMATTED', result_data['games'][0].get('GAME_DATE'))} - {result_data['games'][0].get('MATCHUP')}")

        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            print(json.dumps(result_data, indent=2))
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: Games for a specific team in a season
    await run_game_finder_test(
        "Lakers Games 2022-23 Regular Season",
        team_id_nullable=TEAM_ID_LAL,
        season_nullable=SEASON_2022_23,
        season_type_nullable=SeasonTypeAllStar.regular # Corrected attribute
    )

    # Test 2: Games for a specific player in a season
    await run_game_finder_test(
        "LeBron James Games 2022-23 Regular Season",
        player_id_nullable=PLAYER_ID_LEBRON,
        season_nullable=SEASON_2022_23,
        season_type_nullable=SeasonTypeAllStar.regular # Corrected attribute
    )

    # Test 3: Games within a date range for a specific season (should bypass date-only error)
    await run_game_finder_test(
        "Games in Oct 2023 for 2023-24 Season",
        season_nullable=SEASON_2023_24,
        date_from_nullable="2023-10-01",
        date_to_nullable="2023-10-31"
    )

    # Test 4: Trigger the date-only error
    await run_game_finder_test(
        "Date-Only Query (expecting error)",
        date_from_nullable="2023-10-01",
        date_to_nullable="2023-10-05"
    )
    
    # Test 5: Player search without player_id (expecting error)
    await run_game_finder_test(
        "Player Search No ID (expecting error)",
        player_or_team_abbreviation='P'
        # player_id_nullable is omitted
    )

    # Test 6: Broad query (all teams, all seasons - should be limited)
    # This can be slow and return a lot of data, so the function limits it.
    # logger.info("Note: The following 'All Games' test might be slow and is limited to 200 results by the logic.")
    # await run_game_finder_test(
    #     "All Games (Limited)",
    #     league_id_nullable=LeagueID.nba 
    # )

if __name__ == "__main__":
    asyncio.run(main())