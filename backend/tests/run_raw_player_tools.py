import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import (
    playerdashboardbyclutch,
    playerdashboardbygamesplits,
    playerdashboardbygeneralsplits,
    playerdashboardbylastngames,
    playerdashboardbyshootingsplits,
    playerdashboardbyteamperformance,
    playerdashboardbyyearoveryear,
    playercareerstats,
    commonplayerinfo
)
from nba_api.stats.library.parameters import SeasonAll
from backend.config import CURRENT_SEASON

# Example player ID (LeBron James)
EXAMPLE_PLAYER_ID = 2544

def test_player_info():
    """Test the common player info endpoint"""
    print("\n=== Testing common player info ===\n")
    
    try:
        info = commonplayerinfo.CommonPlayerInfo(
            player_id=EXAMPLE_PLAYER_ID
        )
        
        print("Endpoint: commonplayerinfo")
        print("\nCommon Player Info Structure:")
        info_df = info.common_player_info.get_data_frame()
        if not info_df.empty:
            print("Columns:", json.dumps(list(info_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(info_df.iloc[0].to_dict(), indent=2))

        print("\nPlayer Headline Stats Structure:")
        headline_df = info.player_headline_stats.get_data_frame()
        if not headline_df.empty:
            print("Columns:", json.dumps(list(headline_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(headline_df.iloc[0].to_dict(), indent=2))

    except Exception as e:
        print(f"Error testing player info: {str(e)}")

def test_player_career_stats():
    """Test the player career stats endpoint"""
    print("\n=== Testing player career stats ===\n")
    
    try:
        career = playercareerstats.PlayerCareerStats(
            player_id=EXAMPLE_PLAYER_ID,
            per_mode36="PerGame"
        )
        
        print("Endpoint: playercareerstats")
        print("\nCareer Totals Regular Season Structure:")
        career_df = career.career_totals_regular_season.get_data_frame()
        if not career_df.empty:
            print("Columns:", json.dumps(list(career_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(career_df.iloc[0].to_dict(), indent=2))

        print("\nCareer Regular Season Structure:")
        season_df = career.season_totals_regular_season.get_data_frame()
        if not season_df.empty:
            print("Columns:", json.dumps(list(season_df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(season_df.iloc[0].to_dict(), indent=2))

    except Exception as e:
        print(f"Error testing career stats: {str(e)}")

def test_player_dashboard_splits():
    """Test various player dashboard split endpoints"""
    print("\n=== Testing player dashboard splits ===\n")
    
    splits = [
        ("Clutch", playerdashboardbyclutch.PlayerDashboardByClutch),
        ("Game Splits", playerdashboardbygamesplits.PlayerDashboardByGameSplits),
        ("General Splits", playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits),
        ("Last N Games", playerdashboardbylastngames.PlayerDashboardByLastNGames),
        ("Shooting Splits", playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits),
        ("Team Performance", playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance),
        ("Year Over Year", playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear)
    ]

    for split_name, endpoint in splits:
        print(f"\n=== Testing {split_name} Dashboard ===")
        
        try:
            print(f"\nEndpoint: {endpoint.__name__}")
            dashboard = endpoint(
                player_id=EXAMPLE_PLAYER_ID,
                season=CURRENT_SEASON
            )

            available_tables = [attr for attr in dir(dashboard)
                              if not attr.startswith('_') and
                              hasattr(getattr(dashboard, attr), 'get_data_frame')]
            
            for table in available_tables:
                try:
                    df = getattr(dashboard, table).get_data_frame()
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        print(f"\n{table} Structure:")
                        print("Columns:", json.dumps(list(df.columns), indent=2))
                except Exception:
                    continue

        except Exception as e:
            print(f"Error testing {split_name} dashboard: {str(e)}")

def save_raw_output(data, endpoint):
    """Helper function to save raw output to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"player_tools_{endpoint}_raw_output_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nFull raw output saved to {filename}")

if __name__ == "__main__":
    print("Testing Player Tools endpoints...")
    
    test_player_info()
    test_player_career_stats()
    test_player_dashboard_splits()