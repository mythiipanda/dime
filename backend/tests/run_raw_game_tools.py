"""
Raw output test script for NBA Game API endpoints.
Tests raw responses from boxscore, play-by-play, shot chart, and league games endpoints.
"""

from typing import Dict, Any
from nba_api.stats.endpoints import (
    boxscoretraditionalv2,
    playbyplay,
    shotchartdetail,
    leaguegamefinder
)
from nba_api.stats.library.parameters import SeasonTypeAllStar
import json
from datetime import datetime

# Test configuration
TEST_GAME_ID = "0022300643"  # Replace with a valid game ID
TEST_TEAM_ID = 1610612747  # Lakers
TEST_PLAYER_ID = 2544  # LeBron James
DEFAULT_TIMEOUT = 30

def get_raw_boxscore(game_id: str = TEST_GAME_ID) -> Dict[str, Any]:
    """
    Fetches raw box score data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        
    Returns:
        Dict containing raw API response with player stats, team stats, and starters/bench breakdown
    """
    try:
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process player stats
        player_stats_raw = boxscore.player_stats.get_dict()
        player_stats = []
        
        if "resultSets" in player_stats_raw:
            for row in player_stats_raw["resultSets"][0].get("rowSet", []):
                headers = player_stats_raw["resultSets"][0]["headers"]
                row_dict = dict(zip(headers, row))
                player = {
                    "player_id": row_dict.get("PLAYER_ID"),
                    "name": row_dict.get("PLAYER_NAME"),
                    "team": row_dict.get("TEAM_ABBREVIATION"),
                    "position": row_dict.get("START_POSITION", ""),
                    "minutes": row_dict.get("MIN", "0"),
                    "points": row_dict.get("PTS", 0),
                    "rebounds": {
                        "offensive": row_dict.get("OREB", 0),
                        "defensive": row_dict.get("DREB", 0),
                        "total": row_dict.get("REB", 0)
                    },
                    "assists": row_dict.get("AST", 0),
                    "steals": row_dict.get("STL", 0),
                    "blocks": row_dict.get("BLK", 0),
                    "turnovers": row_dict.get("TO", 0),
                    "fouls": row_dict.get("PF", 0),
                    "shooting": {
                        "fg": f"{row_dict.get('FGM', 0)}-{row_dict.get('FGA', 0)}",
                        "fg_pct": row_dict.get("FG_PCT", 0.0),
                        "fg3": f"{row_dict.get('FG3M', 0)}-{row_dict.get('FG3A', 0)}",
                        "fg3_pct": row_dict.get("FG3_PCT", 0.0),
                        "ft": f"{row_dict.get('FTM', 0)}-{row_dict.get('FTA', 0)}",
                        "ft_pct": row_dict.get("FT_PCT", 0.0)
                    },
                    "plus_minus": row_dict.get("PLUS_MINUS", 0)
                }
                player_stats.append(player)
        
        return {
            "meta": {
                "endpoint": "boxscoretraditionalv2",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id
                }
            },
            "data": {
                "player_stats": player_stats,
                "team_stats": boxscore.team_stats.get_dict(),
                "team_starter_bench_stats": boxscore.team_starter_bench_stats.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "boxscoretraditionalv2",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_playbyplay(
    game_id: str = TEST_GAME_ID,
    start_period: int = 0,
    end_period: int = 0
) -> Dict[str, Any]:
    """
    Fetches raw play-by-play data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        start_period: Starting period filter (0 for all)
        end_period: Ending period filter (0 for all)
        
    Returns:
        Dict containing raw API response with filtered play-by-play data
    """
    try:
        pbp = playbyplay.PlayByPlay(
            game_id=game_id,
            start_period=start_period,
            end_period=end_period,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process play-by-play data
        plays_raw = pbp.play_by_play.get_dict()
        plays = []
        
        if "resultSets" in plays_raw:
            for row in plays_raw["resultSets"][0].get("rowSet", []):
                headers = plays_raw["resultSets"][0]["headers"]
                row_dict = dict(zip(headers, row))
                
                # Determine which team the play belongs to
                team = "home" if row_dict.get("HOMEDESCRIPTION") else "away" if row_dict.get("VISITORDESCRIPTION") else "neutral"
                
                play = {
                    "period": row_dict.get("PERIOD", 0),
                    "clock": row_dict.get("PCTIMESTRING", ""),
                    "event_type": row_dict.get("EVENTMSGTYPE", 0),
                    "description": row_dict.get("HOMEDESCRIPTION" if team == "home" else "VISITORDESCRIPTION", ""),
                    "team": team,
                    "score": row_dict.get("SCORE", ""),
                    "margin": row_dict.get("SCOREMARGIN", "")
                }
                plays.append(play)
        
        return {
            "meta": {
                "endpoint": "playbyplay",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id,
                    "start_period": start_period,
                    "end_period": end_period
                }
            },
            "data": {
                "plays": plays,
                "available_video": pbp.available_video.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "playbyplay",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_shotchart(game_id: str = TEST_GAME_ID) -> Dict[str, Any]:
    """
    Fetches raw shot chart data directly from the NBA API.
    
    Args:
        game_id: The NBA game ID
        
    Returns:
        Dict containing raw API response with shot locations and league averages
    """
    try:
        shotchart = shotchartdetail.ShotChartDetail(
            game_id_nullable=game_id,
            team_id=0,
            player_id=0,
            context_measure_simple="FGA",
            season_nullable="2023-24",
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process shot chart data
        shots_raw = shotchart.shot_chart_detail.get_dict()
        shots = []
        
        if "resultSets" in shots_raw:
            for row in shots_raw["resultSets"][0].get("rowSet", []):
                headers = shots_raw["resultSets"][0]["headers"]
                row_dict = dict(zip(headers, row))
                
                shot = {
                    "team": {
                        "id": row_dict.get("TEAM_ID"),
                        "name": row_dict.get("TEAM_NAME")
                    },
                    "player": {
                        "id": row_dict.get("PLAYER_ID"),
                        "name": row_dict.get("PLAYER_NAME")
                    },
                    "location": {
                        "x": row_dict.get("LOC_X"),
                        "y": row_dict.get("LOC_Y")
                    },
                    "shot_type": row_dict.get("SHOT_TYPE"),
                    "shot_zone": {
                        "basic": row_dict.get("SHOT_ZONE_BASIC"),
                        "area": row_dict.get("SHOT_ZONE_AREA"),
                        "range": row_dict.get("SHOT_ZONE_RANGE")
                    },
                    "shot_distance": row_dict.get("SHOT_DISTANCE"),
                    "made": row_dict.get("SHOT_MADE_FLAG") == 1,
                    "period": row_dict.get("PERIOD"),
                    "game_clock": row_dict.get("GAME_CLOCK"),
                    "shot_clock": row_dict.get("SHOT_CLOCK")
                }
                shots.append(shot)
        
        return {
            "meta": {
                "endpoint": "shotchartdetail",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_id": game_id,
                    "season": "2023-24"
                }
            },
            "data": {
                "shots": shots,
                "league_averages": shotchart.league_averages.get_dict()
            }
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "shotchartdetail",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            },
            "data": None
        }

def get_raw_league_games(
    player_or_team: str = 'T',
    player_id: int = None,
    team_id: int = None,
    season: str = None,
    season_type: str = None,
    league_id: str = None,
    date_from: str = None,
    date_to: str = None
) -> Dict[str, Any]:
    """
    Fetches raw league games data directly from the NBA API.
    
    Args:
        player_or_team: Search by 'P' (Player) or 'T' (Team)
        player_id: Player ID (required if player_or_team='P')
        team_id: Team ID (required if player_or_team='T')
        season: Season identifier
        season_type: Season type
        league_id: League ID
        date_from: Start date filter (MM/DD/YYYY)
        date_to: End date filter (MM/DD/YYYY)
        
    Returns:
        Dict containing raw API response with filtered games
    """
    try:
        gamefinder = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team,
            player_id_nullable=player_id,
            team_id_nullable=team_id,
            season_nullable=season,
            season_type_nullable=season_type,
            league_id_nullable=league_id,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=DEFAULT_TIMEOUT
        )
        
        return {
            "meta": {
                "endpoint": "leaguegamefinder",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "player_or_team": player_or_team,
                    "player_id": player_id,
                    "team_id": team_id,
                    "season": season,
                    "season_type": season_type,
                    "league_id": league_id,
                    "date_from": date_from,
                    "date_to": date_to
                }
            },
            "data": gamefinder.get_normalized_dict()
        }
    except Exception as e:
        return {
            "meta": {
                "endpoint": "leaguegamefinder",
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
    if isinstance(data, dict):
        print("\nData sections:", list(data.keys()))
        for section, content in data.items():
            if isinstance(content, list):
                print(f"\n{section} contains {len(content)} records")
                if content:
                    print(f"Sample record keys:", list(content[0].keys()) if isinstance(content[0], dict) else "Not a dict")
            elif isinstance(content, dict):
                print(f"\n{section} keys:", list(content.keys()))

def test_invalid_game_id():
    """Test behavior with invalid game ID formats"""
    invalid_ids = ["", "123", "abcd", "0022300999999"]
    
    print("\nTesting invalid game IDs...")
    for game_id in invalid_ids:
        print(f"\nTesting game_id: '{game_id}'")
        boxscore = get_raw_boxscore(game_id)
        analyze_response(boxscore)

def test_period_filters():
    """Test play-by-play with different period filters"""
    print("\nTesting period filters...")
    
    # Test first half
    print("\nTesting first half (periods 1-2)")
    pbp = get_raw_playbyplay(TEST_GAME_ID, 1, 2)
    analyze_response(pbp)
    
    # Test second half
    print("\nTesting second half (periods 3-4)")
    pbp = get_raw_playbyplay(TEST_GAME_ID, 3, 4)
    analyze_response(pbp)

def test_league_games():
    """Test league games finder with different filters"""
    print("\nTesting league games finder...")
    
    # Test by team
    print("\nTesting team games")
    team_games = get_raw_league_games(
        player_or_team='T',
        team_id=TEST_TEAM_ID,
        season="2023-24",
        season_type=SeasonTypeAllStar.regular
    )
    analyze_response(team_games)
    
    # Test by player
    print("\nTesting player games")
    player_games = get_raw_league_games(
        player_or_team='P',
        player_id=TEST_PLAYER_ID,
        season="2023-24",
        season_type=SeasonTypeAllStar.regular
    )
    analyze_response(player_games)

def main():
    """Run raw API tests and save results."""
    print(f"Testing Game endpoints with Game ID: {TEST_GAME_ID}")
    
    # Test basic endpoints
    print("\nTesting basic endpoints...")
    responses = {
        "boxscore": get_raw_boxscore(),
        "playbyplay": get_raw_playbyplay(),
        "shotchart": get_raw_shotchart()
    }
    
    for endpoint_name, response in responses.items():
        print(f"\n=== Testing {endpoint_name} ===")
        analyze_response(response)
    
    # Run additional test suites
    test_invalid_game_id()
    test_period_filters()
    test_league_games()
    
    # Save all test results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"game_tools_raw_output_{timestamp}.json"
    
    # Add league games tests to responses
    responses.update({
        "team_games": get_raw_league_games(player_or_team='T', team_id=TEST_TEAM_ID),
        "player_games": get_raw_league_games(player_or_team='P', player_id=TEST_PLAYER_ID)
    })
    
    with open(filename, "w") as f:
        json.dump(responses, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

if __name__ == "__main__":
    main()