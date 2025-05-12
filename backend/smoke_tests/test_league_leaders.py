# backend/smoke_tests/test_league_leaders.py
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

from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, PerMode48, Scope, StatCategoryAbbreviation
from backend.config import settings

async def run_league_leaders_test(test_name_suffix: str, season: str, **kwargs):
    test_name = f"League Leaders ({season}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    # Ensure all required args for fetch_league_leaders_logic are present or defaulted
    params = {
        "season": season,
        "stat_category": kwargs.get("stat_category", StatCategoryAbbreviation.pts),
        "season_type": kwargs.get("season_type", SeasonTypeAllStar.regular),
        "per_mode": kwargs.get("per_mode", PerMode48.per_game),
        "league_id": kwargs.get("league_id", LeagueID.nba),
        "scope": kwargs.get("scope", Scope.s), # 'S' for Season, 'RS' for Regular Season, 'A' for All Star
        "top_n": kwargs.get("top_n", 5)
    }

    result_json = await asyncio.to_thread(fetch_league_leaders_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "leaders" in result_data and isinstance(result_data["leaders"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched league leaders. Count: {len(result_data['leaders'])}")
                if result_data["leaders"]:
                    sample_leader = result_data["leaders"][0]
                    logger.info(f"  Sample Leader (Rank {sample_leader.get('RANK')}): {sample_leader.get('PLAYER')} with {sample_leader.get(params['stat_category'])} {params['stat_category']}")
            elif "leaders" in result_data and not result_data["leaders"]:
                 logger.info(f"SUCCESS: {test_name} - No league leaders found (empty list returned as expected for these params).")
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
    current_season_from_settings = settings.CURRENT_NBA_SEASON # "2024-25"
    past_season = "2022-23"

    # Test 1: Default PTS leaders for current season
    await run_league_leaders_test(" - PTS Leaders, Default Params", season=current_season_from_settings)

    # Test 2: AST leaders for a past season, top 3
    await run_league_leaders_test(f" - {past_season} AST Leaders, Top 3", 
                                  season=past_season, 
                                  stat_category=StatCategoryAbbreviation.ast, 
                                  top_n=3)

    # Test 3: REB leaders for playoffs
    await run_league_leaders_test(f" - {past_season} REB Leaders, Playoffs", 
                                  season=past_season, 
                                  stat_category=StatCategoryAbbreviation.reb, 
                                  season_type=SeasonTypeAllStar.playoffs,
                                  top_n=5)

    # Test 4: Invalid StatCategory
    await run_league_leaders_test(f" - {past_season} Invalid StatCat", 
                                  season=past_season, 
                                  stat_category="INVALID_STAT")
    
    # Test 5: Invalid Season Format
    await run_league_leaders_test(" - Invalid Season Format", season="2023")

    # Test 6: Invalid PerMode
    await run_league_leaders_test(f" - {past_season} Invalid PerMode", 
                                  season=past_season, 
                                  per_mode="InvalidMode")

if __name__ == "__main__":
    asyncio.run(main())