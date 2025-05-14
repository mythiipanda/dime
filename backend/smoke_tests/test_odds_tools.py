# backend/smoke_tests/test_odds_tools.py
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

from backend.api_tools.odds_tools import fetch_odds_data_logic
# from backend.config import settings # Not directly needed by fetch_odds_data_logic signature

async def run_odds_test_with_assertions(bypass_cache: bool, description_suffix: str = ""):
    test_name = f"Odds Data (bypass_cache={bypass_cache}{description_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_odds_data_logic, bypass_cache=bypass_cache)
    
    try:
        result_data = json.loads(result_json)
        # logger.debug(json.dumps(result_data, indent=2))
        
        assert "error" not in result_data, f"API returned an error for {test_name}: {result_data.get('error')}"
        assert "games" in result_data, f"'games' key missing for {test_name}"
        assert isinstance(result_data["games"], list), f"'games' should be a list for {test_name}"

        if result_data["games"]:
            logger.info(f"SUCCESS: {test_name} - Fetched odds data. Games Found: {len(result_data['games'])}")
            sample_game = result_data["games"][0]
            assert "gameId" in sample_game, f"'gameId' missing in sample game for {test_name}"
            assert "markets" in sample_game, f"'markets' missing in sample game for {test_name}"
            assert isinstance(sample_game["markets"], list), f"'markets' should be a list in sample game for {test_name}"
            logger.info(f"  Sample Game ID: {sample_game.get('gameId')}, Markets: {len(sample_game.get('markets', []))}")
            if sample_game.get('markets'):
                market_name = sample_game["markets"][0].get('name', 'N/A')
                logger.info(f"    Sample Market: {market_name}")
        else:
            logger.info(f"SUCCESS (No Data): {test_name} - No games with odds data found (empty list returned). This is normal if no games today or no odds available.")
            
    except json.JSONDecodeError:
        logger.error(f"JSONDecodeError for {test_name}: Could not decode JSON response: {result_json}")
        assert False, f"JSONDecodeError for {test_name}"
    logger.info("-" * 70)

@pytest.mark.asyncio
async def test_odds_data_bypass_cache():
    "Test fetching odds data bypassing the cache."
    await run_odds_test_with_assertions(bypass_cache=True, description_suffix=" - Bypass Cache")

@pytest.mark.asyncio
async def test_odds_data_with_caching_sequence():
    "Test fetching odds data with cache, checking sequence with sleeps."
    
    logger.info("Starting odds data caching sequence test...")
    # Test 1: First call (cache miss for API, populates cache)
    await run_odds_test_with_assertions(bypass_cache=False, description_suffix=" - Cache Seq Call 1")
    
    logger.info("Waiting for 5 seconds (should hit hourly cache bucket if timestamping is similar)...")
    await asyncio.sleep(5)
    # Test 2: Second call (should ideally hit application-level timestamp cache bucket)
    await run_odds_test_with_assertions(bypass_cache=False, description_suffix=" - Cache Seq Call 2 (after 5s)")

    # The odds API cache is typically longer (e.g., 1 hour). A short sleep like 12s won't reliably test expiry.
    # For smoke test purposes, testing bypass and non-bypass is the main goal here.
    # A more elaborate cache expiry test would require mocking time or a much longer wait.
    logger.info("Odds data caching sequence (basic check) completed.")