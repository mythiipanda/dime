"""
Script to check raw NBA API data for a player.
This will help us verify the accuracy of our ELO ratings, skill grades, and advanced metrics.
"""

import sys
import os
import pandas as pd
import json

# Add the parent directory to the path so we can import from api_tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nba_api.stats.endpoints import playercareerstats, commonplayerinfo, playerestimatedmetrics
from nba_api.stats.endpoints import leaguedashplayerstats
from api_tools.utils import retry_on_timeout

def check_player_raw_data(player_id, player_name):
    """Fetch and display raw NBA API data for a player."""
    print(f"\n{'='*50}")
    print(f"Raw NBA API Data for {player_name} (ID: {player_id})")
    print(f"{'='*50}\n")
    
    # 1. Fetch basic player info
    print("1. Basic Player Info:")
    try:
        player_info = retry_on_timeout(lambda: commonplayerinfo.CommonPlayerInfo(player_id=player_id))
        player_info_df = player_info.get_data_frames()[0]
        print(player_info_df.iloc[0].to_dict())
    except Exception as e:
        print(f"Error fetching player info: {str(e)}")
    
    # 2. Fetch current season advanced stats
    print("\n2. Current Season Advanced Stats:")
    try:
        def fetch_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                player_id=player_id,
                season="2023-24",
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame'
            )
        
        advanced_stats = retry_on_timeout(fetch_advanced_stats)
        advanced_df = advanced_stats.get_data_frames()[0]
        
        if not advanced_df.empty:
            print(advanced_df.iloc[0].to_dict())
        else:
            print("No advanced stats found for current season")
    except Exception as e:
        print(f"Error fetching advanced stats: {str(e)}")
    
    # 3. Fetch current season basic stats
    print("\n3. Current Season Basic Stats:")
    try:
        def fetch_basic_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                player_id=player_id,
                season="2023-24",
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Base',
                per_mode_detailed='PerGame'
            )
        
        basic_stats = retry_on_timeout(fetch_basic_stats)
        basic_df = basic_stats.get_data_frames()[0]
        
        if not basic_df.empty:
            print(basic_df.iloc[0].to_dict())
        else:
            print("No basic stats found for current season")
    except Exception as e:
        print(f"Error fetching basic stats: {str(e)}")
    
    # 4. Fetch career stats
    print("\n4. Career Stats:")
    try:
        career_stats = retry_on_timeout(lambda: playercareerstats.PlayerCareerStats(player_id=player_id))
        career_totals_df = career_stats.get_data_frames()[1]  # Career totals
        
        if not career_totals_df.empty:
            print(career_totals_df.iloc[0].to_dict())
        else:
            print("No career stats found")
    except Exception as e:
        print(f"Error fetching career stats: {str(e)}")
    
    # 5. Fetch league-wide stats for percentile calculations
    print("\n5. League-Wide Stats Summary (for percentiles):")
    try:
        def fetch_league_advanced_stats():
            return leaguedashplayerstats.LeagueDashPlayerStats(
                season="2023-24",
                season_type_all_star='Regular Season',
                measure_type_detailed_defense='Advanced',
                per_mode_detailed='PerGame'
            )
        
        league_advanced = retry_on_timeout(fetch_league_advanced_stats)
        league_advanced_df = league_advanced.get_data_frames()[0]
        
        # Print summary statistics for key metrics
        key_metrics = ['PIE', 'TS_PCT', 'USG_PCT', 'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT', 'ORTG', 'DRTG']
        
        print("League-wide percentiles for key metrics:")
        for metric in key_metrics:
            if metric in league_advanced_df.columns:
                values = league_advanced_df[metric].dropna()
                percentiles = {
                    '10th': values.quantile(0.1),
                    '25th': values.quantile(0.25),
                    '50th': values.quantile(0.5),
                    '75th': values.quantile(0.75),
                    '90th': values.quantile(0.9),
                    '95th': values.quantile(0.95)
                }
                print(f"{metric}: {percentiles}")
    except Exception as e:
        print(f"Error fetching league-wide stats: {str(e)}")

if __name__ == "__main__":
    # Check data for LeBron James
    check_player_raw_data(2544, "LeBron James")
    
    # Check data for another player (e.g., Nikola Jokic)
    check_player_raw_data(203999, "Nikola Jokic")
