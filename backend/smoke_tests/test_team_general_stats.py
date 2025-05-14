# backend/smoke_tests/test_team_general_stats.py
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

from backend.api_tools.team_general_stats import fetch_team_stats_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID
from backend.config import settings

# Test Constants
TEAM_ID_LAKERS = "1610612747"
TEAM_ABBREV_CELTICS = "BOS"
TEAM_ID_CELTICS_INT = 1610612738 # For opponent_team_id
INVALID_TEAM_IDENTIFIER = "INVALID_TEAM_XYZ"
INVALID_SEASON_FORMAT = "2023"
INVALID_PER_MODE = "InvalidPerMode"
INVALID_MEASURE_TYPE = "InvalidMeasure"

CURRENT_SEASON = settings.CURRENT_NBA_SEASON
PAST_SEASON = "2022-23"

async def run_team_stats_test_with_assertions(
    description: str, 
    expect_api_error: bool = False, 
    **kwargs: Any
):
    test_name = f"Team General Stats - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    result_json_str = await asyncio.to_thread(fetch_team_stats_logic, **kwargs)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        # Check that primary data keys are not present or are empty
        assert "team_id" not in result_data or not result_data["team_id"], f"Expected no 'team_id' on API error for '{description}'"
        assert "current_stats" not in result_data or not result_data["current_stats"], f"Expected no 'current_stats' on API error for '{description}'"
        assert "historical_stats" not in result_data or not result_data["historical_stats"], f"Expected no 'historical_stats' on API error for '{description}'"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "team_id" in result_data and isinstance(result_data["team_id"], int), \
            f"'team_id' key missing or not an int for '{description}'. Response: {result_data}"
        assert "current_stats" in result_data and isinstance(result_data["current_stats"], dict), \
            f"'current_stats' key missing or not a dict for '{description}'. Response: {result_data}"
        assert "historical_stats" in result_data and isinstance(result_data["historical_stats"], list), \
            f"'historical_stats' key missing or not a list for '{description}'. Response: {result_data}"

        assert result_data["current_stats"].get("GP") is not None or result_data["current_stats"].get("W_PCT") is not None, \
            f"Expected 'GP' or 'W_PCT' in current_stats for '{description}'"

        # Historical stats can be empty if it's the team's first season or specific filters yield no past data
        if result_data["historical_stats"]:
            assert "TEAM_ID" in result_data["historical_stats"][0], f"'TEAM_ID' missing in historical_stats item for '{description}'"
        
        logger.info(f"SUCCESS for '{description}': Fetched data for Team ID {result_data['team_id']} ({result_data.get('team_name')}). Current GP: {result_data['current_stats'].get('GP')}, Historical entries: {len(result_data['historical_stats'])}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error",
    [
        ("Lakers, Defaults", {"team_identifier": TEAM_ID_LAKERS}, False),
        (
            "Celtics, Past Season, Totals, Advanced", 
            {"team_identifier": TEAM_ABBREV_CELTICS, "season": PAST_SEASON, "per_mode": PerModeDetailed.totals, "measure_type": MeasureTypeDetailedDefense.advanced},
            False
        ),
        (
            "Lakers, Past Season, Dec 2022", 
            {"team_identifier": TEAM_ID_LAKERS, "season": PAST_SEASON, "date_from": "2022-12-01", "date_to": "2022-12-31"},
            False
        ),
        (
            "Lakers vs Celtics, Past Season", 
            {"team_identifier": TEAM_ID_LAKERS, "season": PAST_SEASON, "opponent_team_id": TEAM_ID_CELTICS_INT},
            False
        ),
        ("Invalid Team Identifier", {"team_identifier": INVALID_TEAM_IDENTIFIER}, True),
        ("Lakers, Invalid Season Format", {"team_identifier": TEAM_ID_LAKERS, "season": INVALID_SEASON_FORMAT}, True),
        ("Lakers, Past Season, Invalid PerMode", {"team_identifier": TEAM_ID_LAKERS, "season": PAST_SEASON, "per_mode": INVALID_PER_MODE}, True),
        ("Lakers, Past Season, Invalid MeasureType", {"team_identifier": TEAM_ID_LAKERS, "season": PAST_SEASON, "measure_type": INVALID_MEASURE_TYPE}, True),
    ]
)
async def test_team_general_stats_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool):
    # Add default season if not specified, as logic might rely on it
    if 'season' not in params:
        params['season'] = CURRENT_SEASON
        
    await run_team_stats_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        **params
    )