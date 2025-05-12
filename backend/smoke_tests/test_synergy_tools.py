# backend/smoke_tests/test_synergy_tools.py
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

from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from nba_api.stats.library.parameters import (
    LeagueID, PerModeSimple, PlayerOrTeamAbbreviation, SeasonTypeAllStar
)
from backend.config import settings # For settings.CURRENT_NBA_SEASON

async def run_synergy_test(test_name_suffix: str, **kwargs):
    # Construct a descriptive name from kwargs, excluding None values
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None and k != "season"]
    if "season" in kwargs and kwargs["season"] is not None:
        filters_list.insert(0, f"season={kwargs['season']}")
    else:
        filters_list.insert(0, f"season={settings.CURRENT_NBA_SEASON}")

    filters_str = ", ".join(filters_list)
    test_name = f"Synergy Play Types ({filters_str}{test_name_suffix})"
    logger.info(f"--- Testing {test_name} ---")
    
    # Ensure all required args for fetch_synergy_play_types_logic are present or defaulted
    params = {
        "league_id": kwargs.get("league_id", LeagueID.nba),
        "per_mode": kwargs.get("per_mode", PerModeSimple.per_game),
        "player_or_team": kwargs.get("player_or_team", PlayerOrTeamAbbreviation.team),
        "season_type": kwargs.get("season_type", SeasonTypeAllStar.regular),
        "season": kwargs.get("season", settings.CURRENT_NBA_SEASON),
        "play_type_nullable": kwargs.get("play_type_nullable"),
        "type_grouping_nullable": kwargs.get("type_grouping_nullable"),
        "bypass_cache": kwargs.get("bypass_cache", False)
    }
    
    result_json = await asyncio.to_thread(fetch_synergy_play_types_logic, **params)
    
    try:
        result_data = json.loads(result_json)
        # print(json.dumps(result_data, indent=2)) # Uncomment for full output
        
        if "error" not in result_data:
            if "synergy_stats" in result_data and isinstance(result_data["synergy_stats"], list):
                logger.info(f"SUCCESS: {test_name} - Fetched Synergy stats. Entries found: {len(result_data['synergy_stats'])}")
                if result_data["synergy_stats"]:
                    sample_entry = result_data["synergy_stats"][0]
                    logger.info(f"  Sample Entry: PlayType {sample_entry.get('PLAY_TYPE')}, Team {sample_entry.get('TEAM_ABBREVIATION') or sample_entry.get('PLAYER_NAME')}, PPP {sample_entry.get('PPP')}")
            elif "synergy_stats" in result_data and not result_data["synergy_stats"] and result_data.get("message"):
                 logger.info(f"SUCCESS (No Data): {test_name} - {result_data.get('message')}")
            elif "synergy_stats" in result_data and not result_data["synergy_stats"]:
                 logger.info(f"SUCCESS (No Data): {test_name} - No Synergy stats found (empty list returned).")
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
    # Target season from the successful example provided
    test_season_example = "2023-24"
    logger.info(f"Targeting season: {test_season_example} for Synergy tests based on working example.")

    # Test Case from Example: Player, PRRollman, 2018-19, Totals
    await run_synergy_test(f" - Player, PRRollman, {test_season_example}, Totals",
                           player_or_team=PlayerOrTeamAbbreviation.player,
                           season=test_season_example,
                           play_type_nullable="PRRollman",
                           per_mode=PerModeSimple.totals,
                           type_grouping_nullable="offensive") # Example used offensive

    # Additional test with another common play type for that season
    await run_synergy_test(f" - Player, Isolation, {test_season_example}, Totals",
                           player_or_team=PlayerOrTeamAbbreviation.player,
                           season=test_season_example,
                           play_type_nullable="Isolation",
                           per_mode=PerModeSimple.totals,
                           type_grouping_nullable="offensive")

    # Test Team data for a common play type for that season
    await run_synergy_test(f" - Team, Transition, {test_season_example}, PerGame",
                           player_or_team=PlayerOrTeamAbbreviation.team,
                           season=test_season_example,
                           play_type_nullable="Transition",
                           per_mode=PerModeSimple.per_game,
                           type_grouping_nullable="offensive")


    # Validation Tests (can use a more recent season for these, e.g., 2022-23)
    validation_season = "2022-23"
    logger.info(f"Running validation tests against season: {validation_season}")
    
    await run_synergy_test(" - Invalid PlayType",
                           player_or_team=PlayerOrTeamAbbreviation.team,
                           season=validation_season,
                           play_type_nullable="InvalidPlay")
    
    await run_synergy_test(" - Invalid TypeGrouping",
                           player_or_team=PlayerOrTeamAbbreviation.team,
                           season=validation_season,
                           type_grouping_nullable="InvalidGroup")

    await run_synergy_test(" - Invalid PlayerOrTeam",
                           player_or_team="X",
                           season=validation_season)

if __name__ == "__main__":
    asyncio.run(main())