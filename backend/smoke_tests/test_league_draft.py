# backend/smoke_tests/test_league_draft.py
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

from backend.api_tools.league_draft import fetch_draft_history_logic
from nba_api.stats.library.parameters import LeagueID

async def run_draft_test(test_name_suffix: str, **kwargs):
    filters_str = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    test_name = f"Draft History ({filters_str}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_draft_history_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "draft_picks" in result_data and isinstance(result_data["draft_picks"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched draft history. Picks found: {len(result_data['draft_picks'])}")
                if result_data["draft_picks"]:
                    sample_pick = result_data["draft_picks"][0]
                    logger.info(f"  Sample Pick: Year {sample_pick.get('SEASON')}, Round {sample_pick.get('ROUND_NUMBER')}, Pick {sample_pick.get('OVERALL_PICK')}, Player {sample_pick.get('PLAYER_NAME')}")
            elif "draft_picks" in result_data and not result_data["draft_picks"]:
                 logger.info(f"SUCCESS: {test_name} - No draft picks found (empty list returned as expected for these filters).")
            else:
                logger.warning(f"WARNING: {test_name} - Data structure not as expected.")
                print(json.dumps(result_data, indent=2))
        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
    logger.info("-" * 70)

async def main():
    # Test 1: All drafts (might be large, API might limit or timeout if not careful) - let's use a specific year
    await run_draft_test(" - 2023 Draft", season_year_nullable="2023")

    # Test 2: Specific year and round
    await run_draft_test(" - 2022 Draft, Round 1", season_year_nullable="2022", round_num_nullable=1)

    # Test 3: Specific year and team (e.g., Lakers Team ID: 1610612747)
    await run_draft_test(" - 2021 Draft, Lakers", season_year_nullable="2021", team_id_nullable=1610612747)
    
    # Test 4: Specific overall pick for a year
    await run_draft_test(" - 2020 Draft, Pick 1", season_year_nullable="2020", overall_pick_nullable=1)

    # Test 5: Invalid year format
    await run_draft_test(" - Invalid Year", season_year_nullable="23")
    
    # Test 6: Invalid League ID
    await run_draft_test(" - Invalid League", league_id_nullable="XYZ")

if __name__ == "__main__":
    asyncio.run(main())