# backend/smoke_tests/test_search_logic.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.search import search_players_logic, search_teams_logic, search_games_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar
from backend.config import settings # For default season

async def run_search_test(logic_function, test_name_prefix, query, **kwargs):
    test_name = f"{test_name_prefix} (Query: '{query}')"
    logger.info(f"--- Testing {test_name} ---")
    
    params = {"query": query, **kwargs}
    result_json = await asyncio.to_thread(logic_function, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "players" in result_data:
                logger.info(f"SUCCESS: {test_name} - Found {len(result_data['players'])} players.")
                if result_data['players']:
                    logger.info(f"  Sample Player: {result_data['players'][0].get('full_name')}")
            elif "teams" in result_data:
                logger.info(f"SUCCESS: {test_name} - Found {len(result_data['teams'])} teams.")
                if result_data['teams']:
                    logger.info(f"  Sample Team: {result_data['teams'][0].get('full_name')}")
            elif "games" in result_data:
                logger.info(f"SUCCESS: {test_name} - Found {len(result_data['games'])} games.")
                if result_data['games']:
                    logger.info(f"  Sample Game: {result_data['games'][0].get('MATCHUP')} on {result_data['games'][0].get('GAME_DATE')}")
            else:
                logger.warning(f"WARNING: {test_name} - Data structure not as expected (no players, teams, or games key).")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    current_season = settings.CURRENT_NBA_SEASON
    past_season = "2022-23"

    # Test Player Search
    await run_search_test(search_players_logic, "Player Search", query="LeBron")
    await run_search_test(search_players_logic, "Player Search", query="Jokic", limit=3)
    await run_search_test(search_players_logic, "Player Search - Short Query", query="L") # Expect error or empty
    await run_search_test(search_players_logic, "Player Search - No Results", query="NonExistentPlayerXYZ")

    # Test Team Search
    await run_search_test(search_teams_logic, "Team Search", query="Lakers")
    await run_search_test(search_teams_logic, "Team Search", query="Bos", limit=1)
    await run_search_test(search_teams_logic, "Team Search - Abbreviation", query="GSW")
    await run_search_test(search_teams_logic, "Team Search - No Results", query="NonExistentTeamXYZ")

    # Test Game Search
    await run_search_test(search_games_logic, "Game Search - Single Team", query="Lakers", season=past_season)
    await run_search_test(search_games_logic, "Game Search - Matchup", query="LAL vs BOS", season=past_season, limit=5)
    await run_search_test(search_games_logic, "Game Search - Matchup with 'at'", query="Warriors at Suns", season=past_season)
    await run_search_test(search_games_logic, "Game Search - No Results", query="NonExistentTeamXYZ", season=past_season)
    await run_search_test(search_games_logic, "Game Search - Invalid Season", query="Lakers", season="2023")
    await run_search_test(search_games_logic, "Game Search - Empty Query", query="", season=past_season)


if __name__ == "__main__":
    asyncio.run(main())