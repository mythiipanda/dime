import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import json
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import (
    teaminfocommon,
    commonteamroster,
    teamdashboardbygeneralsplits,
    teamdashptpass,
    teamyearbyyearstats
)
from nba_api.stats.library.parameters import LeagueID, SeasonTypeAllStar
from backend.config import CURRENT_SEASON

# Example Team ID (Los Angeles Lakers)
EXAMPLE_TEAM_ID = 1610612747

def test_team_info_common():
    """Test the team info common endpoint"""
    print("\n=== Testing team info common ===\n")
    
    try:
        endpoint = teaminfocommon.TeamInfoCommon(
            team_id=EXAMPLE_TEAM_ID,
            season_nullable=CURRENT_SEASON,
            league_id=LeagueID.nba
        )
        
        print("Endpoint: teaminfocommon")
        
        print("\nteam_info_common Structure:")
        df = endpoint.team_info_common.get_data_frame()
        if not df.empty:
            print("Columns:", json.dumps(list(df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(df.iloc[0].to_dict(), indent=2))
            
        print("\nteam_season_ranks Structure:")
        df_ranks = endpoint.team_season_ranks.get_data_frame()
        if not df_ranks.empty:
            print("Columns:", json.dumps(list(df_ranks.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(df_ranks.iloc[0].to_dict(), indent=2))

    except Exception as e:
        print(f"Error testing team info common: {str(e)}")

def test_common_team_roster():
    """Test the common team roster endpoint"""
    print("\n=== Testing common team roster ===\n")
    
    try:
        endpoint = commonteamroster.CommonTeamRoster(
            team_id=EXAMPLE_TEAM_ID,
            season=CURRENT_SEASON
        )
        
        print("Endpoint: commonteamroster")
        
        print("\ncommon_team_roster Structure:")
        df_roster = endpoint.common_team_roster.get_data_frame()
        if not df_roster.empty:
            print("Columns:", json.dumps(list(df_roster.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(df_roster.iloc[0].to_dict(), indent=2))
            
        print("\ncoaches Structure:")
        df_coaches = endpoint.coaches.get_data_frame()
        if not df_coaches.empty:
            print("Columns:", json.dumps(list(df_coaches.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(df_coaches.iloc[0].to_dict(), indent=2))

    except Exception as e:
        print(f"Error testing common team roster: {str(e)}")

def test_team_dashboard_general_splits():
    """Test the team dashboard general splits endpoint"""
    print("\n=== Testing team dashboard general splits ===\n")
    
    try:
        endpoint = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=EXAMPLE_TEAM_ID,
            season=CURRENT_SEASON,
            season_type_all_star=SeasonTypeAllStar.regular
        )
        
        print("Endpoint: teamdashboardbygeneralsplits")
        
        available_tables = [attr for attr in dir(endpoint) 
                          if not attr.startswith('_') and 
                          hasattr(getattr(endpoint, attr), 'get_data_frame')]
        
        for table in available_tables:
            try:
                df = getattr(endpoint, table).get_data_frame()
                if isinstance(df, pd.DataFrame) and not df.empty:
                    print(f"\n{table} Structure:")
                    print("Columns:", json.dumps(list(df.columns), indent=2))
            except Exception as table_e:
                print(f"  Error processing table {table}: {table_e}")

    except Exception as e:
        print(f"Error testing team dashboard general splits: {str(e)}")

def test_team_dash_pt_pass():
    """Test the team dash pt pass endpoint"""
    print("\n=== Testing team dash pt pass ===\n")
    
    try:
        endpoint = teamdashptpass.TeamDashPtPass(
            team_id=EXAMPLE_TEAM_ID,
            season=CURRENT_SEASON,
            season_type_all_star=SeasonTypeAllStar.regular
        )
        
        print("Endpoint: teamdashptpass")
        
        print("\npasses_made Structure:")
        df_made = endpoint.passes_made.get_data_frame()
        if not df_made.empty:
            print("Columns:", json.dumps(list(df_made.columns), indent=2))
            
        print("\npasses_received Structure:")
        df_received = endpoint.passes_received.get_data_frame()
        if not df_received.empty:
            print("Columns:", json.dumps(list(df_received.columns), indent=2))

    except Exception as e:
        print(f"Error testing team dash pt pass: {str(e)}")

def test_team_year_by_year_stats():
    """Test the team year by year stats endpoint"""
    print("\n=== Testing team year by year stats ===\n")
    
    try:
        endpoint = teamyearbyyearstats.TeamYearByYearStats(
            team_id=EXAMPLE_TEAM_ID,
            league_id=LeagueID.nba,
            season_type_all_star=SeasonTypeAllStar.regular # Correct parameter name
        )
        
        print("Endpoint: teamyearbyyearstats")
        
        print("\nteam_stats Structure:")
        df = endpoint.team_stats.get_data_frame()
        if not df.empty:
            print("Columns:", json.dumps(list(df.columns), indent=2))
            print("\nExample Row:")
            print(json.dumps(df.iloc[0].to_dict(), indent=2))

    except Exception as e:
        print(f"Error testing team year by year stats: {str(e)}")


if __name__ == "__main__":
    print("Testing Team Tools endpoints...")
    
    test_team_info_common()
    test_common_team_roster()
    test_team_dashboard_general_splits()
    test_team_dash_pt_pass()
    test_team_year_by_year_stats()
    
    # Note: Saving full raw output for team tools might be very large.
    # Consider saving individual endpoint outputs if needed.
    print("\nRaw testing complete for team tools.")