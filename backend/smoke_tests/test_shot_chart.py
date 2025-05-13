"""
Smoke test for the shot chart API.
"""

import json
import os
import sys

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from api_tools.shot_charts import fetch_player_shot_chart

def test_shot_chart():
    """Test the shot chart API with a known player."""
    player_name = "LeBron James"

    print(f"Testing shot chart for {player_name}...")

    # Call the API
    result_json = fetch_player_shot_chart(player_name)

    # Parse the result
    result = json.loads(result_json)

    # Check if there's an error
    if 'error' in result:
        print(f"Error: {result['error']}")
        return

    # Print some basic stats
    print(f"Player: {result['player_name']} (ID: {result['player_id']})")
    print(f"Team: {result['team_name']} (ID: {result['team_id']})")
    print(f"Season: {result['season']}, Type: {result['season_type']}")
    print(f"Total shots: {len(result['shots'])}")

    # Count made and missed shots
    made_shots = sum(1 for shot in result['shots'] if shot['made'])
    missed_shots = len(result['shots']) - made_shots

    print(f"Made shots: {made_shots} ({made_shots / len(result['shots']) * 100:.1f}%)")
    print(f"Missed shots: {missed_shots} ({missed_shots / len(result['shots']) * 100:.1f}%)")

    # Print zone stats
    print("\nZone Analysis:")
    for zone in result['zones']:
        print(f"{zone['zone']}: {zone['made']}/{zone['attempts']} ({zone['percentage'] * 100:.1f}%), " +
              f"League: {zone['leaguePercentage'] * 100:.1f}%, " +
              f"Diff: {zone['relativePercentage'] * 100:+.1f}%")

if __name__ == "__main__":
    test_shot_chart()
