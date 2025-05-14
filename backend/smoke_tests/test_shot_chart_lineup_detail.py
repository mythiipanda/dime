import sys
import os
import asyncio
import json
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.shot_chart_lineup_detail import fetch_shot_chart_lineup_detail_logic
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar, ContextMeasureDetailed
from backend.config import settings

# Example Celtics lineup (Tatum, Brown, White, Holiday, Horford) - IDs might need verification
# Jayson Tatum: 1628369
# Jaylen Brown: 1627759
# Derrick White: 1628401
# Jrue Holiday: 201950
# Al Horford: 201143
# Kristaps Porzingis: 204001
# Celtics Team ID: 1610612738

# More reliable Celtics lineup from 2023-24 (Tatum, Brown, Porzingis, White, Holiday)
# GROUP_ID_CELTICS_23_24 = "1628369 - 1627759 - 204001 - 1628401 - 201950" # Tatum, Brown, Porzingis, White, Holiday
# Simpler, more common lineup for testing (Tatum, Brown, Smart, Horford, Brogdon - from a past season for more data)
# Smart: 1627739, Brogdon: 1627763
# For 2022-23 Celtics: Tatum, Brown, Smart, Horford, White
GROUP_ID_CELTICS_22_23_STARTERS = "1628369 - 1627759 - 1627739 - 201143 - 1628401"
TEAM_ID_CELTICS = 1610612738
SEASON_22_23 = "2022-23"

async def run_test(test_name_suffix: str, **kwargs):
    test_name = f"Shot Chart Lineup Detail ({test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")

    params = {
        "group_id": kwargs.get("group_id", GROUP_ID_CELTICS_22_23_STARTERS),
        "team_id": kwargs.get("team_id", TEAM_ID_CELTICS),
        "season": kwargs.get("season", SEASON_22_23),
        "season_type": kwargs.get("season_type", SeasonTypeAllStar.regular),
        "context_measure": kwargs.get("context_measure", ContextMeasureDetailed.fgm),
        "league_id": kwargs.get("league_id", LeagueID.nba),
        "period": kwargs.get("period", 0),
    }
    # Add other optional params if provided in kwargs
    for k, v in kwargs.items():
        if k not in params and f"{k}_nullable" not in params : # check if it's already a base param
             params[f"{k}_nullable"] = v


    result_json = await asyncio.to_thread(fetch_shot_chart_lineup_detail_logic, **params)

    try:
        result_data = json.loads(result_json)
        if "error" not in result_data:
            assert "shot_chart_details" in result_data, "Missing 'shot_chart_details' key"
            assert "league_averages" in result_data, "Missing 'league_averages' key"
            
            logger.info(f"SUCCESS: {test_name} - Fetched data.")
            if result_data["shot_chart_details"]:
                logger.info(f"  Shot Details Count: {len(result_data['shot_chart_details'])}")
                logger.info(f"  Sample Shot Detail (first): {result_data['shot_chart_details'][0]}")
            else:
                logger.info(f"  No specific shot details found for this lineup/filter (which can be valid).")
            
            if result_data["league_averages"]:
                logger.info(f"  League Averages Count: {len(result_data['league_averages'])}")
                logger.info(f"  Sample League Average (first): {result_data['league_averages'][0]}")
            else:
                logger.info(f"  No league averages found (which can be valid).")

        elif "error" in result_data:
            logger.error(f"ERROR for {test_name}: {result_data['error']}")
            # We expect errors for invalid inputs, so this can be a pass for those tests
            if "Invalid" in result_data["error"] or "not found" in result_data["error"] or "format" in result_data["error"]:
                 logger.info(f"Test passed with expected error: {result_data['error']}")
            else:
                assert False, f"Test failed with unexpected error: {result_data['error']}"
        else:
            logger.warning(f"WARNING: Unexpected response structure for {test_name}.")
            print(json.dumps(result_data, indent=2))
            assert False, "Unexpected response structure"

    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON response for {test_name}: {result_json}")
        assert False, "JSONDecodeError"
    except AssertionError as e:
        logger.error(f"AssertionError for {test_name}: {e}")
        # Optionally re-raise if you want pytest to show it as a failure directly
        # raise e 
    logger.info("-" * 70)


async def main():
    # Test 1: Valid Celtics lineup, 2022-23 Regular Season, FGM
    await run_test("Celtics 22-23 Starters, FGM")

    # Test 2: Valid Celtics lineup, 2022-23 Regular Season, PTS
    await run_test("Celtics 22-23 Starters, PTS", context_measure=ContextMeasureDetailed.pts)

    # Test 3: Valid Celtics lineup, 2022-23 Playoffs
    await run_test("Celtics 22-23 Starters, Playoffs", season_type=SeasonTypeAllStar.playoffs)
    
    # Test 4: Different valid lineup (e.g., Warriors) - Requires finding another GROUP_ID and TeamID
    # For now, let's use a known Warriors lineup from 2021-22 for more data diversity
    # Steph Curry: 201939, Klay Thompson: 202691, Andrew Wiggins: 203952, Draymond Green: 203110, Kevon Looney: 203956
    # Warriors Team ID: 1610612744
    GROUP_ID_WARRIORS_21_22 = "201939 - 202691 - 203952 - 203110 - 203956"
    TEAM_ID_WARRIORS = 1610612744
    SEASON_21_22 = "2021-22"
    await run_test("Warriors 21-22 Starters, FGM", 
                   group_id=GROUP_ID_WARRIORS_21_22, 
                   team_id=TEAM_ID_WARRIORS, 
                   season=SEASON_21_22)

    # Test 5: Invalid GROUP_ID format
    await run_test("Invalid GROUP_ID format", group_id="123-456") # Missing spaces and not enough IDs

    # Test 6: Invalid TeamID (0 is often used for league-wide, but this endpoint needs a specific team)
    await run_test("Invalid TeamID 0", team_id=0)
    
    # Test 7: Invalid TeamID (non-existent)
    await run_test("Non-existent TeamID", team_id=9999999999)

    # Test 8: Invalid season format
    await run_test("Invalid Season Format", season="2023")

    # Test 9: Invalid context_measure
    await run_test("Invalid Context Measure", context_measure="INVALID_MEASURE")
    
    # Test 10: Filter by Period 1
    await run_test("Celtics 22-23 Starters, Period 1", period=1)

    # Test 11: Filter by Date Range (ensure dates are within the season)
    await run_test("Celtics 22-23 Starters, Date Range", date_from_nullable="2022-11-01", date_to_nullable="2022-11-30")

if __name__ == "__main__":
    asyncio.run(main())