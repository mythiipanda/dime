"""Test script for NBA Team API endpoints.

This script tests all team-related endpoints including basic info, roster,
stats, and historical data. It includes validation for response structures
and error cases.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

from nba_api.stats.endpoints import (
    teaminfocommon,
    commonteamroster,
    teamdashboardbygeneralsplits,
    teamdashptpass,
    teamyearbyyearstats
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonTypeAllStar,
    PerModeDetailed,
    MeasureTypeDetailedDefense
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT

# Test configuration
EXAMPLE_TEAM_ID = 1610612747  # Los Angeles Lakers
INVALID_TEAM_ID = 9999999  # For error testing

def analyze_response(response: Dict[str, Any], endpoint_name: str) -> None:
    """Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response to analyze
        endpoint_name: Name of the endpoint for logging
    """
    print(f"\nAnalyzing response from {endpoint_name}:")
    
    if response.get("error"):
        print(f"Error: {response['error']}")
        return
        
    meta = response.get("meta", {})
    print(f"Version: {meta.get('version')}")
    print(f"Parameters: {meta.get('parameters')}")
    
    data = response.get("data", {})
    if isinstance(data, list):
        print(f"Found {len(data)} records")
        if data:
            print("\nSample record structure:")
            print(json.dumps(data[0], indent=2))
    elif isinstance(data, dict):
        print("\nData structure:")
        print(json.dumps(list(data.keys()), indent=2))

def validate_team_info(info: Dict[str, Any]) -> bool:
    """Validates team information structure.
    
    Args:
        info: Team info data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        "TEAM_ID", "TEAM_NAME", "TEAM_CITY", "TEAM_ABBREVIATION",
        "TEAM_CONFERENCE", "TEAM_DIVISION", "W", "L", "PCT",
        "CONF_RANK", "DIV_RANK"
    }
    
    if not all(field in info for field in required_fields):
        print(f"Missing required fields in team info: {required_fields - set(info.keys())}")
        return False
        
    return True

def validate_roster_player(player: Dict[str, Any]) -> bool:
    """Validates player information in roster.
    
    Args:
        player: Player data to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = {
        "PLAYER_ID", "PLAYER", "NUM", "POSITION",
        "HEIGHT", "WEIGHT", "AGE", "EXP"
    }
    
    if not all(field in player for field in required_fields):
        print(f"Missing required fields in player: {required_fields - set(player.keys())}")
        return False
        
    return True

def get_raw_team_info(team_id: str = EXAMPLE_TEAM_ID, season: str = CURRENT_SEASON) -> Dict[str, Any]:
    """Test the team info common endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get info for
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Info Common ===\n")
    
    try:
        info = teaminfocommon.TeamInfoCommon(
            team_id=team_id,
            season_nullable=season,
            league_id=LeagueID.nba,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "teaminfocommon",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": {
                "team_info": info.team_info_common.get_dict(),
                "season_ranks": info.team_season_ranks.get_dict()
            }
        }
        
        analyze_response(result, "Team Info Common")
        return result

    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teaminfocommon",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Info Common")
        return error_result

def get_raw_team_roster(team_id: str = EXAMPLE_TEAM_ID, season: str = CURRENT_SEASON) -> Dict[str, Any]:
    """Test the common team roster endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get roster for
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Common Team Roster ===\n")
    
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season=season,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "commonteamroster",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": {
                "roster": roster.common_team_roster.get_dict(),
                "coaches": roster.coaches.get_dict()
            }
        }
        
        analyze_response(result, "Common Team Roster")
        return result

    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "commonteamroster",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Common Team Roster")
        return error_result

def get_raw_team_stats(
    team_id: str = EXAMPLE_TEAM_ID,
    season: str = CURRENT_SEASON,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.per_game
) -> Dict[str, Any]:
    """Test the team dashboard general splits endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        season: Season to get stats for
        measure_type: Type of stats to get
        per_mode: Stats calculation mode
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Dashboard General Splits ===\n")
    
    try:
        dashboard = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=season,
            measure_type_detailed_defense=measure_type,
            per_mode_detailed=per_mode,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get all available data tables
        data_tables = {}
        for attr in dir(dashboard):
            if not attr.startswith('_') and hasattr(getattr(dashboard, attr), 'get_dict'):
                data_tables[attr] = getattr(dashboard, attr).get_dict()
        
        result = {
            "meta": {
                "endpoint": "teamdashboardbygeneralsplits",
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "team_id": team_id,
                    "season": season,
                    "measure_type": measure_type,
                    "per_mode": per_mode
                }
            },
            "data": data_tables
        }
        
        analyze_response(result, "Team Dashboard General Splits")
        return result

    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teamdashboardbygeneralsplits",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Dashboard General Splits")
        return error_result

def get_raw_team_history(team_id: str = EXAMPLE_TEAM_ID) -> Dict[str, Any]:
    """Test the team year by year stats endpoint.
    
    Args:
        team_id: The NBA team ID to test with
        
    Returns:
        Dict containing the test results
    """
    print("\n=== Testing Team Year By Year Stats ===\n")
    
    try:
        history = teamyearbyyearstats.TeamYearByYearStats(
            team_id=team_id,
            league_id=LeagueID.nba,
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode_simple=PerModeDetailed.per_game,
            timeout=DEFAULT_TIMEOUT
        )
        
        result = {
            "meta": {
                "endpoint": "teamyearbyyearstats",
                "timestamp": datetime.now().isoformat(),
                "parameters": {"team_id": team_id}
            },
            "data": history.get_normalized_dict()
        }
        
        analyze_response(result, "Team Year By Year Stats")
        return result

    except Exception as e:
        error_result = {
            "meta": {
                "endpoint": "teamyearbyyearstats",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }
        analyze_response(error_result, "Team Year By Year Stats")
        return error_result

def test_error_cases() -> Dict[str, Any]:
    """Test error handling for various scenarios."""
    print("\n=== Testing Error Cases ===\n")
    
    results = {
        "invalid_team_id": {
            "info": get_raw_team_info(INVALID_TEAM_ID),
            "roster": get_raw_team_roster(INVALID_TEAM_ID)
        },
        "invalid_season": {
            "info": get_raw_team_info(season="2023"),
            "stats": get_raw_team_stats(season="invalid")
        },
        "invalid_measure_type": get_raw_team_stats(measure_type="invalid")
    }
    
    return results

def main():
    """Run all team tools tests and save results."""
    print("Testing Team Tools endpoints...")
    
    # Run all tests
    results = {
        "team_info": get_raw_team_info(),
        "roster": get_raw_team_roster(),
        "stats": {
            "per_game": get_raw_team_stats(per_mode=PerModeDetailed.per_game),
            "totals": get_raw_team_stats(per_mode=PerModeDetailed.totals)
        },
        "history": get_raw_team_history(),
        "error_cases": test_error_cases()
    }
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"team_tools_raw_output_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main()