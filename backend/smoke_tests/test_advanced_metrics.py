"""
Smoke test for the advanced metrics API.
"""

import json
import os
import sys

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from api_tools.advanced_metrics import fetch_player_advanced_analysis_logic

def test_advanced_metrics():
    """Test the advanced metrics API with a known player."""
    player_name = "LeBron James"

    print(f"Testing advanced metrics for {player_name}...")

    # Call the API
    result_json = fetch_player_advanced_analysis_logic(player_name)

    # Parse the result
    result = json.loads(result_json)

    # Check if there's an error
    if 'error' in result:
        print(f"Error: {result['error']}")
        return

    # Print basic info
    print(f"Player: {result['player_name']} (ID: {result['player_id']})")

    # Print advanced metrics
    print("\nAdvanced Metrics:")
    for metric, value in result['advanced_metrics'].items():
        print(f"{metric}: {value}")

    # Print skill grades
    print("\nSkill Grades:")
    for skill, grade in result['skill_grades'].items():
        print(f"{skill}: {grade}")

    # Print similar players
    print("\nSimilar Players:")
    for player in result['similar_players']:
        print(f"{player['player_name']} (ID: {player['player_id']}): {player['similarity_score'] * 100:.1f}% similarity")

if __name__ == "__main__":
    test_advanced_metrics()
