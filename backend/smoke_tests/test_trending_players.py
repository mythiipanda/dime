# backend/smoke_tests/test_trending_players.py
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

from backend.api_tools.trending_tools import fetch_top_performers_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, StatCategoryAbbreviation, PerMode48, Scope, LeagueID
from backend.config import settings

async def run_trending_players_test(test_name_suffix: str, **kwargs):
    # Construct a descriptive name from kwargs
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    filters_str = ", ".join(filters_list)
    test_name = f"Top Performers ({filters_str}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json = await asyncio.to_thread(fetch_top_performers_logic, **kwargs)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "top_performers" in result_data and isinstance(result_data["top_performers"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched top performers. Count: {len(result_data['top_performers'])}")
                if result_data["top_performers"]:
                    sample_performer = result_data["top_performers"][0]
                    stat_cat = result_data.get("stat_category", "N/A")
                    logger.info(f"  Sample Performer (Rank {sample_performer.get('RANK')}): {sample_performer.get('PLAYER')} with {sample_performer.get(stat_cat)} {stat_cat}")
            elif "top_performers" in result_data and not result_data["top_performers"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No top performers found (empty list returned).")
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
    current_season = settings.CURRENT_NBA_SEASON
    past_season = "2022-23"

    # Test 1: Default params (PTS, current season, top 5)
    await run_trending_players_test(" - Defaults")

    # Test 2: Top 3 AST leaders for a past season
    await run_trending_players_test(f" - {past_season} AST Top 3", 
                                  category=StatCategoryAbbreviation.ast, 
                                  season=past_season, 
                                  top_n=3)

    # Test 3: Top 10 REB leaders for playoffs, current season
    await run_trending_players_test(f" - {current_season} REB Playoffs Top 10", 
                                  category=StatCategoryAbbreviation.reb, 
                                  season_type=SeasonTypeAllStar.playoffs,
                                  top_n=10)

    # Test 4: Invalid StatCategory
    await run_trending_players_test(f" - {past_season} Invalid StatCat", 
                                  category="INVALID_STAT", 
                                  season=past_season)
    
    # Test 5: Invalid Season Format
    await run_trending_players_test(" - Invalid Season Format", season="2023")

    # Test 6: Invalid top_n
    await run_trending_players_test(f" - {past_season} Invalid Top N", 
                                  season=past_season, 
                                  top_n=0)
    
    # Test 7: Different PerMode (Totals)
    await run_trending_players_test(f" - {past_season} PTS Totals Top 3",
                                  category=StatCategoryAbbreviation.pts,
                                  season=past_season,
                                  per_mode=PerMode48.totals,
                                  top_n=3)

if __name__ == "__main__":
    asyncio.run(main())