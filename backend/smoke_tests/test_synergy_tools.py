# backend/smoke_tests/test_synergy_tools.py
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

from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from nba_api.stats.library.parameters import (
    LeagueID, PerModeSimple, PlayerOrTeamAbbreviation, SeasonTypeAllStar
)
from backend.config import settings # For settings.CURRENT_NBA_SEASON

# Test Constants
SYNERGY_TEST_SEASON = "2023-24" # Based on original test's working example
SYNERGY_VALIDATION_SEASON = "2022-23"

async def run_synergy_test_with_assertions(
    description: str, 
    expect_api_error: bool = False, 
    expect_empty_list_no_error: bool = False, 
    **kwargs: Any
):
    # Construct a descriptive name from kwargs, excluding None values
    filters_list = [f"{k}={v}" for k, v in kwargs.items() if v is not None and k != "season"]
    effective_season = kwargs.get("season", SYNERGY_TEST_SEASON) # Default to SYNERGY_TEST_SEASON if not provided
    filters_list.insert(0, f"season={effective_season}")
    filters_str = ", ".join(filters_list)
    test_name = f"Synergy Play Types ({filters_str}) - {description}"
    logger.info(f"--- Testing {test_name} ---")
    
    # Ensure all required args for fetch_synergy_play_types_logic are present or defaulted
    # Logic function itself has defaults, so we just pass through kwargs
    # but ensure `season` is explicitly passed if not in kwargs, defaulting to SYNERGY_TEST_SEASON
    call_params = {"season": effective_season, **kwargs}

    result_json_str = await asyncio.to_thread(fetch_synergy_play_types_logic, **call_params)
    result_data = json.loads(result_json_str)
    # logger.debug(f"Full API Response for {test_name}: {json.dumps(result_data, indent=2)}")

    if expect_api_error:
        assert "error" in result_data, f"Expected API error for '{description}', but 'error' key missing. Response: {result_data}"
        assert "synergy_stats" not in result_data or not result_data.get("synergy_stats"), \
            f"Expected 'synergy_stats' to be absent or empty on API error for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected API error for '{description}'): {result_data.get('error')}")
    elif expect_empty_list_no_error:
        assert "error" not in result_data, f"Expected no error for empty list for '{description}', but got: {result_data.get('error')}"
        assert "synergy_stats" in result_data and isinstance(result_data["synergy_stats"], list) and not result_data["synergy_stats"], \
            f"Expected 'synergy_stats' to be an empty list for '{description}'. Response: {result_data}"
        logger.info(f"SUCCESS (expected empty list, no error for '{description}').")
    else: # Expect successful data
        assert "error" not in result_data, f"Expected successful data for '{description}', but got error: {result_data.get('error')}"
        assert "synergy_stats" in result_data and isinstance(result_data["synergy_stats"], list), \
            f"'synergy_stats' key missing or not a list for '{description}'. Response: {result_data}"
        assert len(result_data["synergy_stats"]) > 0, f"Expected non-empty 'synergy_stats' list for '{description}'. Response: {result_data}"
        
        sample_entry = result_data["synergy_stats"][0]
        assert "PLAY_TYPE" in sample_entry, f"'PLAY_TYPE' missing in sample entry for '{description}'"
        assert "PPP" in sample_entry, f"'PPP' missing in sample entry for '{description}'"
        # Player or Team specific key
        is_player_data = kwargs.get("player_or_team") == PlayerOrTeamAbbreviation.player
        if is_player_data:
            assert "PLAYER_NAME" in sample_entry, f"'PLAYER_NAME' missing for player data in '{description}'"
        else:
            assert "TEAM_ABBREVIATION" in sample_entry, f"'TEAM_ABBREVIATION' missing for team data in '{description}'"
            
        logger.info(f"SUCCESS for '{description}': Fetched {len(result_data['synergy_stats'])} entries. Sample PlayType: {sample_entry.get('PLAY_TYPE')}")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description_suffix, params, expect_error, expect_empty",
    [
        (
            "Player, PRRollman, Totals, Offensive",
            {"player_or_team": PlayerOrTeamAbbreviation.player, "season": SYNERGY_TEST_SEASON, "play_type_nullable": "PRRollman", "per_mode": PerModeSimple.totals, "type_grouping_nullable": "offensive"},
            False, False
        ),
        (
            "Player, Isolation, Totals, Offensive",
            {"player_or_team": PlayerOrTeamAbbreviation.player, "season": SYNERGY_TEST_SEASON, "play_type_nullable": "Isolation", "per_mode": PerModeSimple.totals, "type_grouping_nullable": "offensive"},
            False, False
        ),
        (
            "Team, Transition, PerGame, Offensive",
            {"player_or_team": PlayerOrTeamAbbreviation.team, "season": SYNERGY_TEST_SEASON, "play_type_nullable": "Transition", "per_mode": PerModeSimple.per_game, "type_grouping_nullable": "offensive"},
            False, False
        ),
        # Validation Tests
        (
            "Invalid PlayType",
            {"player_or_team": PlayerOrTeamAbbreviation.team, "season": SYNERGY_VALIDATION_SEASON, "play_type_nullable": "InvalidPlay"},
            True, False
        ),
        (
            "Missing PlayType",
            {"player_or_team": PlayerOrTeamAbbreviation.team, "season": SYNERGY_TEST_SEASON, "type_grouping_nullable": "offensive"},
            True, False # Should return SYNERGY_PLAY_TYPE_REQUIRED error
        ),
        (
            "Invalid TypeGrouping",
            {"player_or_team": PlayerOrTeamAbbreviation.team, "season": SYNERGY_VALIDATION_SEASON, "type_grouping_nullable": "InvalidGroup"},
            True, False
        ),
        (
            "Invalid PlayerOrTeam Value",
            {"player_or_team": "X", "season": SYNERGY_VALIDATION_SEASON}, # "X" is not a valid PlayerOrTeamAbbreviation
            True, False
        ),
        (
            "Potentially Empty - WNBA League, PRRollman", # Synergy might not have WNBA PRRollman data
            {"league_id": LeagueID.wnba, "player_or_team": PlayerOrTeamAbbreviation.player, "season": SYNERGY_TEST_SEASON, "play_type_nullable": "PRRollman", "per_mode": PerModeSimple.totals, "type_grouping_nullable": "offensive"},
            False, True # Expecting no error, but an empty list
        )
    ]
)
async def test_synergy_scenarios(description_suffix: str, params: Dict[str, Any], expect_error: bool, expect_empty: bool):
    await run_synergy_test_with_assertions(
        description=description_suffix,
        expect_api_error=expect_error,
        expect_empty_list_no_error=expect_empty,
        **params
    )