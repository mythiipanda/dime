"""
Raw output test script for NBA League API endpoints.
Tests raw responses from standings, scoreboard, draft history, and league leaders endpoints.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from nba_api.stats.endpoints import (
    leaguestandingsv3,
    scoreboardv2,
    drafthistory,
    leagueleaders,
    leaguedashlineups,
    leaguehustlestatsplayer
)
from nba_api.stats.library.parameters import (
    LeagueID,
    SeasonType,
    PerMode48,
    Scope,
    StatCategoryAbbreviation,
    SeasonTypeAllStar,
    PerModeDetailed
)
from backend.config import CURRENT_SEASON, DEFAULT_TIMEOUT
from backend.api_tools.utils import format_response

def get_raw_standings(
    season: str = CURRENT_SEASON,
    season_type: str = SeasonTypeAllStar.regular
) -> dict:
    """
    Fetches raw standings data directly from the NBA API.
    
    Args:
        season: Season identifier (e.g., "2023-24")
        season_type: Season type (e.g., "Regular Season", "Playoffs")
        
    Returns:
        Dict containing raw API response with standings data
    """
    try:
        standings = leaguestandingsv3.LeagueStandingsV3(
            season=season,
            season_type=season_type,
            timeout=DEFAULT_TIMEOUT
        )
        
        standings_df = standings.standings.get_data_frame()
        if standings_df.empty:
            return format_response({"standings": []})
        
        # Process standings data
        processed_standings = []
        for _, row in standings_df.iterrows():
            try:
                standing = {
                    "TeamID": int(row["TeamID"]),
                    "TeamName": f"{row['TeamCity']} {row['TeamName']}".strip(),
                    "Conference": row["Conference"],
                    "PlayoffRank": int(row["PlayoffRank"]),
                    "WinPct": float(row["WinPCT"]),
                    "GB": float(row.get("ConferenceGamesBack", 0)),
                    "L10": row["L10"],
                    "STRK": row["strCurrentStreak"],
                    "WINS": int(row["WINS"]),
                    "LOSSES": int(row["LOSSES"]),
                    "HOME": row["HOME"],
                    "ROAD": row["ROAD"],
                    "Division": row["Division"],
                    "ClinchIndicator": row.get("ClinchIndicator", ""),
                    "DivisionRank": int(row["DivisionRank"]),
                    "ConferenceRecord": row["ConferenceRecord"],
                    "DivisionRecord": row["DivisionRecord"]
                }
                processed_standings.append(standing)
            except (ValueError, KeyError) as e:
                print(f"Error processing standing row: {e}")
                continue
        
        return format_response({
            "meta": {
                "endpoint": "leaguestandingsv3",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "season": season,
                    "season_type": season_type
                }
            },
            "data": {
                "standings": processed_standings
            }
        })
        
    except Exception as e:
        return format_response(
            error=f"API error fetching standings for season {season}: {str(e)}"
        )

def get_raw_scoreboard(
    game_date: str = datetime.today().strftime('%Y-%m-%d'),
    league_id: str = LeagueID.nba,
    day_offset: int = 0
) -> dict:
    """
    Fetches raw scoreboard data directly from the NBA API.
    
    Args:
        game_date: Game date in YYYY-MM-DD format
        league_id: League ID (e.g., "00" for NBA)
        day_offset: Days to offset from game_date
        
    Returns:
        Dict containing raw API response with game data
    """
    try:
        board = scoreboardv2.ScoreboardV2(
            game_date=game_date,
            league_id=league_id,
            day_offset=day_offset,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Process game header data
        game_header = []
        game_header_df = board.game_header.get_data_frame()
        if not game_header_df.empty:
            for _, row in game_header_df.iterrows():
                game = {
                    "GAME_ID": row.get("GAME_ID"),
                    "GAME_STATUS_ID": int(row.get("GAME_STATUS_ID")),
                    "GAME_STATUS_TEXT": row.get("GAME_STATUS_TEXT"),
                    "HOME_TEAM_ID": int(row.get("HOME_TEAM_ID")),
                    "VISITOR_TEAM_ID": int(row.get("VISITOR_TEAM_ID")),
                    "GAME_DATE_EST": row.get("GAME_DATE_EST"),
                    "GAME_TIME_EST": row.get("GAME_TIME_EST"),
                    "NATL_TV_BROADCASTER_ABBREVIATION": row.get("NATL_TV_BROADCASTER_ABBREVIATION", "")
                }
                game_header.append(game)
        
        # Process line score data
        line_score = []
        line_score_df = board.line_score.get_data_frame()
        if not line_score_df.empty:
            for _, row in line_score_df.iterrows():
                score = {
                    "GAME_ID": row.get("GAME_ID"),
                    "TEAM_ID": int(row.get("TEAM_ID")),
                    "TEAM_ABBREVIATION": row.get("TEAM_ABBREVIATION"),
                    "TEAM_CITY_NAME": row.get("TEAM_CITY_NAME"),
                    "TEAM_NICKNAME": row.get("TEAM_NICKNAME"),
                    "PTS": int(row.get("PTS", 0)),
                    "PTS_QTR1": int(row.get("PTS_QTR1", 0)),
                    "PTS_QTR2": int(row.get("PTS_QTR2", 0)),
                    "PTS_QTR3": int(row.get("PTS_QTR3", 0)),
                    "PTS_QTR4": int(row.get("PTS_QTR4", 0)),
                    "PTS_OT1": int(row.get("PTS_OT1", 0)),
                    "PTS_OT2": int(row.get("PTS_OT2", 0)),
                    "PTS_OT3": int(row.get("PTS_OT3", 0)),
                    "PTS_OT4": int(row.get("PTS_OT4", 0))
                }
                line_score.append(score)
        
        return format_response({
            "meta": {
                "endpoint": "scoreboardv2",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "game_date": game_date,
                    "league_id": league_id,
                    "day_offset": day_offset
                }
            },
            "data": {
                "game_header": game_header,
                "line_score": line_score
            }
        })
        
    except Exception as e:
        return format_response(
            error=f"API error fetching scoreboard for date {game_date}: {str(e)}"
        )

def get_raw_draft_history(
    season_year: str = None,
    league_id: str = LeagueID.nba
) -> dict:
    """
    Fetches raw draft history data directly from the NBA API.
    
    Args:
        season_year: Draft year in YYYY format (None for all years)
        league_id: League ID (e.g., "00" for NBA)
        
    Returns:
        Dict containing raw API response with draft picks
    """
    try:
        draft = drafthistory.DraftHistory(
            season_year_nullable=season_year,
            league_id=league_id,
            timeout=DEFAULT_TIMEOUT
        )
        
        draft_list = []
        draft_df = draft.draft_history.get_data_frame()
        if not draft_df.empty:
            for _, row in draft_df.iterrows():
                pick = {
                    "PERSON_ID": int(row.get("PERSON_ID")),
                    "PLAYER_NAME": row.get("PLAYER_NAME"),
                    "SEASON": row.get("SEASON"),
                    "ROUND_NUMBER": int(row.get("ROUND_NUMBER")),
                    "ROUND_PICK": int(row.get("ROUND_PICK")),
                    "OVERALL_PICK": int(row.get("OVERALL_PICK")),
                    "TEAM_ID": int(row.get("TEAM_ID")),
                    "TEAM_CITY": row.get("TEAM_CITY"),
                    "TEAM_NAME": row.get("TEAM_NAME"),
                    "ORGANIZATION": row.get("ORGANIZATION"),
                    "ORGANIZATION_TYPE": row.get("ORGANIZATION_TYPE")
                }
                draft_list.append(pick)
        
        return format_response({
            "meta": {
                "endpoint": "drafthistory",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "season_year": season_year or "All",
                    "league_id": league_id
                }
            },
            "data": {
                "draft_picks": draft_list
            }
        })
        
    except Exception as e:
        return format_response(
            error=f"API error fetching draft history for year {season_year or 'All'}: {str(e)}"
        )

def get_raw_league_leaders(
    season: str = CURRENT_SEASON,
    stat_category: str = "PTS",
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game
) -> dict:
    """
    Fetches raw league leaders data directly from the NBA API.
    
    Args:
        season: Season identifier (e.g., "2023-24")
        stat_category: Statistical category (e.g., "PTS", "AST", "REB")
        season_type: Season type (e.g., "Regular Season", "Playoffs")
        per_mode: Mode of stats (e.g., "PerGame", "Totals")
        
    Returns:
        Dict containing raw API response with league leaders
    """
    try:
        leaders = leagueleaders.LeagueLeaders(
            season=season,
            stat_category_abbreviation=stat_category,
            season_type_all_star=season_type,
            per_mode48=per_mode,
            timeout=DEFAULT_TIMEOUT
        )
        
        leaders_list = []
        leaders_df = leaders.league_leaders.get_data_frame()
        if not leaders_df.empty:
            for _, row in leaders_df.iterrows():
                leader = {
                    "PLAYER_ID": int(row.get("PLAYER_ID")),
                    "RANK": int(row.get("RANK")),
                    "PLAYER": row.get("PLAYER"),
                    "TEAM": row.get("TEAM"),
                    "GP": int(row.get("GP")),
                    "MIN": float(row.get("MIN")),
                    "FGM": float(row.get("FGM")),
                    "FGA": float(row.get("FGA")),
                    "FG_PCT": float(row.get("FG_PCT")),
                    "FG3M": float(row.get("FG3M")),
                    "FG3A": float(row.get("FG3A")),
                    "FG3_PCT": float(row.get("FG3_PCT")),
                    "FTM": float(row.get("FTM")),
                    "FTA": float(row.get("FTA")),
                    "FT_PCT": float(row.get("FT_PCT")),
                    "OREB": float(row.get("OREB")),
                    "DREB": float(row.get("DREB")),
                    "REB": float(row.get("REB")),
                    "AST": float(row.get("AST")),
                    "STL": float(row.get("STL")),
                    "BLK": float(row.get("BLK")),
                    "TOV": float(row.get("TOV")),
                    "PTS": float(row.get("PTS")),
                    "EFF": float(row.get("EFF"))
                }
                leaders_list.append(leader)
        
        return format_response({
            "meta": {
                "endpoint": "leagueleaders",
                "timestamp": datetime.now().isoformat(),
                "params": {
                    "season": season,
                    "stat_category": stat_category,
                    "season_type": season_type,
                    "per_mode": per_mode
                }
            },
            "data": {
                "leaders": leaders_list
            }
        })
        
    except Exception as e:
        return format_response(
            error=f"API error fetching league leaders for {stat_category}, season {season}: {str(e)}"
        )

def test_standings_variations():
    """Test standings endpoint with different parameters"""
    print("\n=== Testing standings variations ===\n")
    
    # Test current season
    print("\nTesting current season standings")
    response = get_raw_standings()
    analyze_response(response)
    
    # Test previous season
    print("\nTesting previous season standings")
    prev_season = f"{int(CURRENT_SEASON[:4])-1}-{int(CURRENT_SEASON[5:])-1}"
    response = get_raw_standings(season=prev_season)
    analyze_response(response)
    
    # Test invalid season format
    print("\nTesting invalid season format")
    response = get_raw_standings(season="2023")
    analyze_response(response)

def test_scoreboard_variations():
    """Test scoreboard endpoint with different parameters"""
    print("\n=== Testing scoreboard variations ===\n")
    
    # Test current date
    print("\nTesting current date scoreboard")
    response = get_raw_scoreboard()
    analyze_response(response)
    
    # Test specific date
    print("\nTesting specific date scoreboard")
    response = get_raw_scoreboard(game_date="2024-02-01")
    analyze_response(response)
    
    # Test invalid date format
    print("\nTesting invalid date format")
    response = get_raw_scoreboard(game_date="02/01/2024")
    analyze_response(response)

def test_draft_variations():
    """Test draft history endpoint with different parameters"""
    print("\n=== Testing draft history variations ===\n")
    
    # Test all years
    print("\nTesting all years draft history")
    response = get_raw_draft_history()
    analyze_response(response)
    
    # Test specific year
    print("\nTesting specific year draft history")
    response = get_raw_draft_history(season_year="2023")
    analyze_response(response)
    
    # Test future year
    print("\nTesting future year draft history")
    response = get_raw_draft_history(season_year="2025")
    analyze_response(response)

def test_league_leaders_variations():
    """Test league leaders endpoint with different parameters"""
    print("\n=== Testing league leaders variations ===\n")
    
    stat_categories = ["PTS", "AST", "REB", "STL", "BLK"]
    per_modes = [PerModeDetailed.totals, PerModeDetailed.per_game, PerModeDetailed.per36]
    
    for stat in stat_categories:
        for mode in per_modes:
            print(f"\nTesting {stat} leaders with {mode}")
            response = get_raw_league_leaders(
                stat_category=stat,
                per_mode=mode
            )
            analyze_response(response)
    
    # Test invalid stat category
    print("\nTesting invalid stat category")
    response = get_raw_league_leaders(stat_category="INVALID")
    analyze_response(response)

def analyze_response(response: dict) -> None:
    """
    Analyzes and prints information about the API response structure.
    
    Args:
        response: The API response dictionary
    """
    if "error" in response:
        print(f"Error: {response['error']}")
        return
    
    meta = response.get("meta", {})
    data = response.get("data", {})
    
    print("\nEndpoint:", meta.get("endpoint"))
    print("Parameters:", meta.get("params"))
    
    for section, content in data.items():
        if isinstance(content, list):
            print(f"\n{section} contains {len(content)} records")
            if content:
                print("Sample record keys:", list(content[0].keys()))
        else:
            print(f"\n{section}:", content)

def save_test_results(results: dict) -> None:
    """
    Saves test results to a JSON file.
    
    Args:
        results: Dictionary containing test results
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"league_tools_test_results_{timestamp}.json"
    
    with open(filename, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nTest results saved to {filename}")

def main():
    """Run raw API tests and save results."""
    print("Testing League Tools endpoints...")
    
    # Store all test results
    results = {
        "standings": {
            "current_season": get_raw_standings(),
            "previous_season": get_raw_standings(season=f"{int(CURRENT_SEASON[:4])-1}-{int(CURRENT_SEASON[5:])-1}"),
            "invalid_season": get_raw_standings(season="2023")
        },
        "scoreboard": {
            "current_date": get_raw_scoreboard(),
            "specific_date": get_raw_scoreboard(game_date="2024-02-01"),
            "invalid_date": get_raw_scoreboard(game_date="02/01/2024")
        },
        "draft": {
            "all_years": get_raw_draft_history(),
            "specific_year": get_raw_draft_history(season_year="2023"),
            "future_year": get_raw_draft_history(season_year="2025")
        },
        "league_leaders": {
            "points_per_game": get_raw_league_leaders(stat_category="PTS", per_mode=PerModeDetailed.per_game),
            "assists_totals": get_raw_league_leaders(stat_category="AST", per_mode=PerModeDetailed.totals),
            "rebounds_per36": get_raw_league_leaders(stat_category="REB", per_mode=PerModeDetailed.per36),
            "invalid_stat": get_raw_league_leaders(stat_category="INVALID")
        }
    }
    
    # Run test suites
    test_standings_variations()
    test_scoreboard_variations()
    test_draft_variations()
    test_league_leaders_variations()
    
    # Save results
    save_test_results(results)

if __name__ == "__main__":
    main()