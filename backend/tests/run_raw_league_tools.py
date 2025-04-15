import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
from datetime import datetime
from nba_api.stats.endpoints import leaguestandingsv3, scoreboardv2, drafthistory, leagueleaders, leaguedashlineups, leaguehustlestatsplayer
from nba_api.stats.library.parameters import LeagueID, SeasonType, PerMode48, Scope, StatCategoryAbbreviation, SeasonTypeAllStar
from backend.config import CURRENT_SEASON

def test_league_standings():
    """Test the league standings endpoint"""
    print("\n=== Testing league standings ===\n")
    
    try:
        standings = leaguestandingsv3.LeagueStandingsV3(
            season=CURRENT_SEASON,
            season_type=SeasonTypeAllStar.regular
        )
        
        print("Endpoint: leaguestandingsv3")
        print("\nStandings Data Structure:")
        standings_df = standings.standings.get_data_frame()
        if not standings_df.empty:
            print("Columns:", json.dumps(list(standings_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(standings_df.iloc[0].to_dict(), indent=2))
    except Exception as e:
        print(f"Error testing league standings: {str(e)}")

def test_league_scoreboard():
    """Test the league scoreboard endpoint"""
    print("\n=== Testing league scoreboard ===\n")
    
    try:
        board = scoreboardv2.ScoreboardV2(
            game_date=datetime.today().strftime('%Y-%m-%d'),
            league_id=LeagueID.nba,
            day_offset=0
        )
        
        print("Endpoint: scoreboardv2")
        
        print("\nGame Header Structure:")
        game_header_df = board.game_header.get_data_frame()
        if not game_header_df.empty:
            print("Columns:", json.dumps(list(game_header_df.columns), indent=2))
        
        print("\nLine Score Structure:")
        line_score_df = board.line_score.get_data_frame()
        if not line_score_df.empty:
            print("Columns:", json.dumps(list(line_score_df.columns), indent=2))
    except Exception as e:
        print(f"Error testing league scoreboard: {str(e)}")

def test_draft_history():
    """Test the draft history endpoint"""
    print("\n=== Testing draft history ===\n")
    
    try:
        draft = drafthistory.DraftHistory(
            league_id=LeagueID.nba
        )
        
        print("Endpoint: drafthistory")
        print("\nDraft History Structure:")
        draft_df = draft.draft_history.get_data_frame()
        if not draft_df.empty:
            print("Columns:", json.dumps(list(draft_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(draft_df.iloc[0].to_dict(), indent=2))
    except Exception as e:
        print(f"Error testing draft history: {str(e)}")

def test_league_leaders():
    """Test the league leaders endpoint"""
    print("\n=== Testing league leaders ===\n")
    
    try:
        leaders = leagueleaders.LeagueLeaders(
            season=CURRENT_SEASON,
            stat_category_abbreviation="PTS",
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode48=PerMode48.per_game
        )
        
        print("Endpoint: leagueleaders")
        print("\nLeague Leaders Structure:")
        leaders_df = leaders.league_leaders.get_data_frame()
        if not leaders_df.empty:
            print("Columns:", json.dumps(list(leaders_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(leaders_df.iloc[0].to_dict(), indent=2))
    except Exception as e:
        print(f"Error testing league leaders: {str(e)}")

def test_league_lineups():
    """Test the league lineups endpoint"""
    print("\n=== Testing league lineups ===\n")
    
    try:
        lineups = leaguedashlineups.LeagueDashLineups(
            season=CURRENT_SEASON,
            season_type_all_star=SeasonTypeAllStar.regular
        )
        
        print("Endpoint: leaguedashlineups")
        print("\nLineups Structure:")
        lineups_df = lineups.lineups.get_data_frame()
        if not lineups_df.empty:
            print("Columns:", json.dumps(list(lineups_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(lineups_df.iloc[0].to_dict(), indent=2))
    except Exception as e:
        print(f"Error testing league lineups: {str(e)}")

def test_league_hustle_stats():
    """Test the league hustle stats endpoint"""
    print("\n=== Testing league hustle stats ===\n")
    
    try:
        hustle = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=CURRENT_SEASON,
            season_type_all_star=SeasonTypeAllStar.regular
        )
        
        print("Endpoint: leaguehustlestatsplayer")
        print("\nHustle Stats Structure:")
        hustle_df = hustle.hustle_stats_player.get_data_frame()
        if not hustle_df.empty:
            print("Columns:", json.dumps(list(hustle_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(hustle_df.iloc[0].to_dict(), indent=2))
    except Exception as e:
        print(f"Error testing league hustle stats: {str(e)}")

def save_raw_output(data, endpoint):
    """Helper function to save raw output to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"league_tools_{endpoint}_raw_output_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nFull raw output saved to {filename}")

if __name__ == "__main__":
    print("Testing League Tools endpoints...")
    
    test_league_standings()
    test_league_scoreboard()
    test_draft_history()
    test_league_leaders()
    test_league_lineups()
    test_league_hustle_stats()