"""
Raw output test script for NBA Player Tracking API endpoints.
Tests raw responses from clutch, shooting, rebounding, passing, and player info endpoints.
"""

from typing import Dict, Any
from nba_api.stats.endpoints import (
    playerdashboardbyclutch,
    playerdashboardbyshootingsplits,
    playerdashptreb,
    playerdashptpass,
    commonplayerinfo,
    playerdashptshots
)
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar,
    PerModeDetailed
)
import json
from datetime import datetime

# Test configuration
TEST_PLAYER_ID = "2544"  # LeBron James
TEST_SEASON = "2023-24"
DEFAULT_TIMEOUT = 30

def get_raw_player_info(player_id: str = TEST_PLAYER_ID) -> Dict[str, Any]:
    """
    Fetches raw player info directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        
    Returns:
        Dict containing raw API response
    """
    try:
        info = commonplayerinfo.CommonPlayerInfo(
            player_id=player_id,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id
                }
            },
            "data": info.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "commonplayerinfo",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_clutch_stats(
    player_id: str = TEST_PLAYER_ID,
    season: str = TEST_SEASON,
    measure_type: str = "Base",
    per_mode: str = PerModeDetailed.totals,
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    shot_clock_range: str = None,
    game_segment: str = None,
    period: int = 0,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    location: str = None,
    outcome: str = None,
    vs_conference: str = None,
    vs_division: str = None,
    season_segment: str = None,
    date_from: str = None,
    date_to: str = None
) -> Dict[str, Any]:
    """
    Fetches raw clutch stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        measure_type: One of: Base, Advanced, Misc, Four Factors, Scoring, Opponent, Usage
        per_mode: One of: Totals, PerGame, MinutesPer, Per48, Per40, Per36, PerMinute, etc.
        plus_minus: Include plus minus stats (Y/N)
        pace_adjust: Include pace adjusted stats (Y/N)
        rank: Include stat rankings (Y/N)
        shot_clock_range: Shot clock range filter
        game_segment: Game segment filter (First Half, Second Half, Overtime)
        period: Period filter (0 for all)
        last_n_games: Last N games filter
        month: Month filter (0 for all)
        opponent_team_id: Filter by opponent team
        location: Home/Road filter
        outcome: W/L filter
        vs_conference: Conference filter
        vs_division: Division filter
        season_segment: Season segment filter
        date_from: Start date filter
        date_to: End date filter
        
    Returns:
        Dict containing raw API response with all clutch time periods
    """
    try:
        clutch_stats = playerdashboardbyclutch.PlayerDashboardByClutch(
            player_id=player_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            measure_type_detailed=measure_type,
            per_mode_detailed=per_mode,
            plus_minus=plus_minus,
            pace_adjust=pace_adjust,
            rank=rank,
            shot_clock_range=shot_clock_range,
            game_segment_nullable=game_segment,
            period=period,
            last_n_games=last_n_games,
            month=month,
            opponent_team_id=opponent_team_id,
            location_nullable=location,
            outcome_nullable=outcome,
            vs_conference_nullable=vs_conference,
            vs_division_nullable=vs_division,
            season_segment_nullable=season_segment,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Get all available clutch time period data
        data = clutch_stats.get_normalized_dict()
        
        # Verify all expected data sets are present
        expected_sets = [
            "OverallPlayerDashboard",
            "Last5Min5PointPlayerDashboard",
            "Last3Min5PointPlayerDashboard", 
            "Last1Min5PointPlayerDashboard",
            "Last30Sec3PointPlayerDashboard",
            "Last10Sec3PointPlayerDashboard",
            "Last5MinPlusMinus5PointPlayerDashboard",
            "Last3MinPlusMinus5PointPlayerDashboard",
            "Last1MinPlusMinus5PointPlayerDashboard"
        ]
        
        missing_sets = [s for s in expected_sets if s not in data]
        if missing_sets:
            print(f"Warning: Missing expected data sets: {missing_sets}")
        
        return {
            "meta": {
                "endpoint": "playerdashboardbyclutch",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "season": season,
                    "measure_type": measure_type,
                    "per_mode": per_mode,
                    "plus_minus": plus_minus,
                    "pace_adjust": pace_adjust,
                    "rank": rank,
                    "filters": {
                        "shot_clock_range": shot_clock_range,
                        "game_segment": game_segment,
                        "period": period,
                        "last_n_games": last_n_games,
                        "month": month,
                        "opponent_team_id": opponent_team_id,
                        "location": location,
                        "outcome": outcome,
                        "vs_conference": vs_conference,
                        "vs_division": vs_division,
                        "season_segment": season_segment,
                        "date_range": {
                            "from": date_from,
                            "to": date_to
                        }
                    }
                }
            },
            "data": data
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashboardbyclutch",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shooting_splits(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw shooting splits directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        shooting_stats = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
            player_id=player_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashboardbyshootingsplits",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "season": season
                }
            },
            "data": shooting_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashboardbyshootingsplits",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_rebounding_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw rebounding stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        reb_stats = playerdashptreb.PlayerDashPtReb(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptreb",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": reb_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptreb",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_passing_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw passing stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        pass_stats = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptpass",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": pass_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptpass",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shot_stats(player_id: str = TEST_PLAYER_ID, season: str = TEST_SEASON) -> Dict[str, Any]:
    """
    Fetches raw shot stats directly from the NBA API.
    
    Args:
        player_id: The NBA player ID
        season: Season in format "YYYY-YY"
        
    Returns:
        Dict containing raw API response
    """
    try:
        # First get player's team ID from common info
        info_response = get_raw_player_info(player_id)
        if info_response["data"] is None:
            raise Exception("Could not get player team ID")
            
        team_id = info_response["data"]["CommonPlayerInfo"][0]["TEAM_ID"]
        
        shot_stats = playerdashptshots.PlayerDashPtShots(
            player_id=player_id,
            team_id=team_id,
            season=season,
            season_type_all_star=SeasonTypeAllStar.regular,
            timeout=DEFAULT_TIMEOUT
        )
        return {
            "meta": {
                "endpoint": "playerdashptshots",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season
                }
            },
            "data": shot_stats.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playerdashptshots",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def analyze_response(response: Dict[str, Any]) -> None:
    """
    Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response dictionary
    """
    if response["data"] is None:
        print(f"Error: {response['meta'].get('error', 'Unknown error')}")
        return

    print(f"\nEndpoint: {response['meta']['endpoint']}")
    print("Parameters:", response['meta']['params'])
    
    # Analyze data structure
    data = response["data"]
    print("\nTop-level keys:", list(data.keys()))
    
    # Look for common data structures
    for key in data:
        if isinstance(data[key], list):
            print(f"\n{key} contains {len(data[key])} records")
            if data[key]:
                print(f"Sample {key} keys:", list(data[key][0].keys()) if isinstance(data[key][0], dict) else "Not a dict")

def main():
    """Run raw API tests and save results."""
    
    # Test different measure types and per modes for clutch stats
    measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Usage"]
    per_modes = [PerModeDetailed.totals, PerModeDetailed.per_game, PerModeDetailed.per36]
    
    print("\nTesting clutch stats with different configurations...")
    for measure_type in measure_types:
        for per_mode in per_modes:
            print(f"\nTesting clutch stats with measure_type={measure_type}, per_mode={per_mode}")
            response = get_raw_clutch_stats(
                measure_type=measure_type,
                per_mode=per_mode,
                plus_minus="Y"
            )
            analyze_response(response)
    
    # Test other endpoints
    print("\nTesting player info...")
    analyze_response(get_raw_player_info())
    
    print("\nTesting shooting splits...")
    analyze_response(get_raw_shooting_splits())
    
    print("\nTesting rebounding stats...")
    analyze_response(get_raw_rebounding_stats())
    
    print("\nTesting passing stats...")
    analyze_response(get_raw_passing_stats())
    
    print("\nTesting shot stats...")
    analyze_response(get_raw_shot_stats())
    
    # Save all test results to file
    results = {
        "clutch_stats": {
            "base_totals": get_raw_clutch_stats(),
            "advanced_per_game": get_raw_clutch_stats(measure_type="Advanced", per_mode=PerModeDetailed.per_game),
            "scoring_per36": get_raw_clutch_stats(measure_type="Scoring", per_mode=PerModeDetailed.per36)
        },
        "player_info": get_raw_player_info(),
        "shooting_splits": get_raw_shooting_splits(),
        "rebounding_stats": get_raw_rebounding_stats(),
        "passing_stats": get_raw_passing_stats(),
        "shot_stats": get_raw_shot_stats()
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"raw_player_tracking_test_{timestamp}.json"
    
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main()