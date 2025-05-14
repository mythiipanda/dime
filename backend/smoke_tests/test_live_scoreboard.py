# backend/smoke_tests/test_live_scoreboard.py
import sys
import os
import asyncio
import json
import logging
import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic
# from backend.config import settings # Not directly needed unless settings influence the call

async def run_live_scoreboard_test_with_assertions(bypass_cache: bool, description_suffix: str = ""):
    test_name = f"Live Scoreboard (bypass_cache={bypass_cache}){description_suffix}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_league_scoreboard_logic, bypass_cache=bypass_cache)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        assert "error" not in result_data, f"API returned an error for {test_name}: {result_data.get('error')}"
        assert "games" in result_data, f"'games' key missing for {test_name}"
        assert isinstance(result_data["games"], list), f"'games' should be a list for {test_name}"
        assert "gameDate" in result_data, f"'gameDate' key missing for {test_name}"

        logger.info(f"SUCCESS: {test_name} - Fetched live scoreboard. Game Date: {result_data.get('gameDate')}, Games Found: {len(result_data['games'])}")
        if result_data["games"]:
            sample_game = result_data["games"][0]
            home_team_tricode = sample_game.get('homeTeam',{}).get('teamTricode', 'N/A')
            away_team_tricode = sample_game.get('awayTeam',{}).get('teamTricode', 'N/A')
            game_status_text = sample_game.get('gameStatusText', 'N/A')
            logger.info(f"  Sample Game: {home_team_tricode} vs {away_team_tricode}, Status: {game_status_text}")
        
    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_live_scoreboard_bypass_cache():
    "Test fetching live scoreboard bypassing the cache."
    await run_live_scoreboard_test_with_assertions(bypass_cache=True, description_suffix=" - Bypass Cache")

@pytest.mark.asyncio
async def test_live_scoreboard_with_caching_sequence():
    "Test fetching live scoreboard with cache, checking sequence with sleeps."
    
    logger.info("Starting caching sequence test...")
    # Test 1: First call (cache miss for API, populates cache)
    await run_live_scoreboard_test_with_assertions(bypass_cache=False, description_suffix=" - Cache Seq Call 1")
    
    logger.info("Waiting for 5 seconds (within typical 10s cache bucket)...")
    await asyncio.sleep(5)
    # Test 2: Second call (should ideally hit application-level timestamp cache bucket)
    await run_live_scoreboard_test_with_assertions(bypass_cache=False, description_suffix=" - Cache Seq Call 2 (after 5s)")

    logger.info("Waiting for 12 seconds (should be new 10s cache bucket)...")
    await asyncio.sleep(12)
    # Test 3: Third call (new timestamp bucket, likely cache miss for API, repopulates cache)
    await run_live_scoreboard_test_with_assertions(bypass_cache=False, description_suffix=" - Cache Seq Call 3 (after 12s)")
    logger.info("Caching sequence test completed.")