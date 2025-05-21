"""
Simple test script to test the LeagueDashPtTeamDefend endpoint with playoff data.
"""
import os
import sys
import json

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from backend.api_tools.league_dash_pt_team_defend import fetch_league_dash_pt_team_defend_logic
from nba_api.stats.library.parameters import SeasonTypeAllStar

def test_playoff_data():
    """Test the LeagueDashPtTeamDefend endpoint with playoff data."""
    print("Testing LeagueDashPtTeamDefend with playoff data...")

    # Call the API with playoff data and po_round_nullable parameter
    response = fetch_league_dash_pt_team_defend_logic(
        '2022-23',
        SeasonTypeAllStar.playoffs,
        po_round_nullable='1'  # First round of playoffs
    )

    # Parse the response
    data = json.loads(response)

    # Print the parameters
    print("Playoff Parameters:", data.get('parameters', {}))

    # Print the number of teams returned
    if 'pt_team_defend' in data:
        teams = data['pt_team_defend']
        print(f"Playoff Teams returned: {len(teams)}")
    else:
        print("No playoff team data returned")

    print("\nTesting LeagueDashPtTeamDefend with regular season data and po_round_nullable...")

    # Call the API with regular season data and po_round_nullable parameter
    response = fetch_league_dash_pt_team_defend_logic(
        '2022-23',
        SeasonTypeAllStar.regular,
        po_round_nullable='1'  # First round of playoffs with regular season data
    )

    # Parse the response
    data = json.loads(response)

    # Print the parameters
    print("Parameters:", data.get('parameters', {}))

    # Print the number of teams returned
    if 'pt_team_defend' in data:
        teams = data['pt_team_defend']
        print(f"Teams returned: {len(teams)}")

        # Print the first team if available
        if teams:
            print("First team:", teams[0])
    else:
        print("No team data returned")

if __name__ == "__main__":
    test_playoff_data()
