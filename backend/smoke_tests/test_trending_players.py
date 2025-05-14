# backend/smoke_tests/test_trending_players.py
import sys
import os
import asyncio
import json
import logging
from typing import Optional, Dict, Any 
import pytest 

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.api_tools.trending_tools import fetch_top_performers_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, StatCategoryAbbreviation, PerMode48, Scope, LeagueID
from backend.config import settings

# Test Constants
CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

async def run_trending_players_test_with_assertions(
    description: str, 
    expect_api_error: bool = False, 
    expect_empty_list_no_error: bool = False, 
    **kwargs: Any
):
    # Construct a descriptive name from kwargs
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None]
    filters_str = ", ".join(filters_list)
    test_name = f"Top Performers ({filters_str}) - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json_str = await asyncio.to_thread(fetch_top_performers_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        assert "top_performers" not in result_data or not result_data.get("top_performers"), \
            f"Expected 'top_performers' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_list_no_error:
        assert "error" not in result_data, f"Expected no error for empty list for '{description}', but got: {result_data.get('error')}"
        assert "stat_category" in result_data, f"'stat_category' key missing for empty list case for '{description}'"
        assert "top_performers" in result_data and isinstance(result_data["top_performers"], list) and not result_data["top_performers"], \
            f"Expected 'top_performers' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty list, no error for '{description}'). Stat Category: {result_data.get('stat_category')}")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "stat_category" in result_data, f"'stat_category' key missing for '{description}'"
        assert "top_performers" in result_data and isinstance(result_data["top_performers"], list), \
            f"'top_performers' key missing or not a list for '{description}'. Response: {result_data}"
        
        if result_data["top_performers"]:
            assert len(result_data["top_performers"]) <= kwargs.get("top_n", 5), \
                f"Expected at most {kwargs.get('top_n', 5)} performers, got {len(result_data['top_performers'])}"
            
            sample_performer = result_data["top_performers"][0]
            returned_stat_category = result_data["stat_category"] 
            
            assert "PLAYER" in sample_performer, f"'PLAYER' missing in sample performer for '{description}'"
            assert "RANK" in sample_performer, f"'RANK' missing in sample performer for '{description}'"
            assert returned_stat_category in sample_performer, \
                f"Stat category key '{returned_stat_category}' missing in sample performer for '{description}'. Keys: {sample_performer.keys()}"
            
            logger.info(f"SUCCESS for '{description}': Fetched {len(result_data['top_performers'])} top performers for {returned_stat_category}.")
            logger.info(f"  Sample Performer (Rank {sample_performer.get('RANK')}): {sample_performer.get('PLAYER')} with {sample_performer.get(returned_stat_category)} {returned_stat_category}")
        else:
            logger.info(f"SUCCESS for '{description}': Fetched 0 top performers (empty list for valid params). Stat Category: {result_data.get('stat_category')}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        ("Defaults (PTS, Current Season, Top 5)", {}, False, False),
        (
            f"{PAST_SEASON} AST Top 3", 
            {"category": StatCategoryAbbreviation.ast, "season": PAST_SEASON, "top_n": 3},
            False, False
        ),
        (
            f"{CURRENT_SEASON} REB Playoffs Top 10", 
            {"category": StatCategoryAbbreviation.reb, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.playoffs, "top_n": 10},
            False, False 
        ),
        (
            f"{PAST_SEASON} Invalid StatCat", 
            {"category": "INVALID_STAT", "season": PAST_SEASON},
            True, False
        ),
        ("Invalid Season Format", {"season": "2023"}, True, False),
        (
            f"{PAST_SEASON} Invalid Top N (0)", 
            {"season": PAST_SEASON, "top_n": 0}, 
            True, False 
        ),
        (
            f"{PAST_SEASON} PTS Totals Top 3",
            {"category": StatCategoryAbbreviation.pts, "season": PAST_SEASON, "per_mode": PerMode48.totals, "top_n": 3},
            False, False
        ),
        (
            f"{CURRENT_SEASON} BLK PreSeason Top 3", 
            {"category": StatCategoryAbbreviation.blk, "season": CURRENT_SEASON, "season_type": SeasonTypeAllStar.preseason, "top_n": 3},
            False, False # Corrected: Expect data, not empty list
        ),
    ]
)
async def test_trending_players_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_trending_players_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_list_no_error=expect_empty,
        **params
    )