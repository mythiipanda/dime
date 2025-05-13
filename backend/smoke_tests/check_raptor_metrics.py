"""
Smoke test for RAPTOR metrics implementation.
Tests the advanced metrics system with the new RAPTOR metrics.
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np

# Add the parent directory to the path so we can import from api_tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_tools.raptor_metrics import (
    get_player_raptor_metrics,
    generate_skill_grades,
    calculate_elo_rating,
    get_historical_player_data
)
from api_tools.utils import get_player_id_from_name

def check_raptor_metrics(player_name):
    """Check RAPTOR metrics for a specific player."""
    print(f"\n{'='*50}")
    print(f"RAPTOR Metrics for {player_name}")
    print(f"{'='*50}\n")

    # Get player ID
    player_id_result = get_player_id_from_name(player_name)
    if isinstance(player_id_result, dict) and 'error' in player_id_result:
        print(f"Error: {player_id_result['error']}")
        return

    player_id = player_id_result

    # Get RAPTOR metrics
    metrics = get_player_raptor_metrics(player_id, "2023-24")

    if not metrics:
        print(f"Error: Could not fetch RAPTOR metrics for {player_name}.")
        return

    # Print player info
    print(f"Player: {metrics.get('PLAYER_NAME', player_name)}")
    print(f"Position: {metrics.get('POSITION', 'Unknown')} ({metrics.get('POSITION_CATEGORY', 'Unknown')})")
    print()

    # Print RAPTOR metrics
    print("RAPTOR Metrics:")
    print(f"RAPTOR Offense: {metrics.get('RAPTOR_OFFENSE', 'N/A')}")
    print(f"RAPTOR Defense: {metrics.get('RAPTOR_DEFENSE', 'N/A')}")
    print(f"RAPTOR Total: {metrics.get('RAPTOR_TOTAL', 'N/A')}")
    print(f"WAR (Wins Above Replacement): {metrics.get('WAR', 'N/A')}")
    print()

    # Print ELO rating
    print("ELO Rating Components:")
    print(f"ELO Rating: {metrics.get('ELO_RATING', 'N/A')}")
    print(f"Current Season: {metrics.get('ELO_CURRENT', 'N/A')}")
    print(f"Historical: {metrics.get('ELO_HISTORICAL', 'N/A')}")
    print()

    # Print traditional advanced metrics
    print("Traditional Advanced Metrics:")
    for key in ['TS_PCT', 'USG_PCT', 'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT', 'PIE']:
        if key in metrics:
            print(f"{key}: {metrics[key]}")
    print()

    # Get basic stats for skill grades
    from nba_api.stats.endpoints import leaguedashplayerstats

    def fetch_basic_stats():
        return leaguedashplayerstats.LeagueDashPlayerStats(
            season="2023-24",
            season_type_all_star='Regular Season',
            measure_type_detailed_defense='Base',
            per_mode_detailed='PerGame'
        )

    basic_stats_data = fetch_basic_stats()
    basic_stats_df = basic_stats_data.get_data_frames()[0]

    basic_stats = {}
    if not basic_stats_df.empty:
        player_stats = basic_stats_df[basic_stats_df['PLAYER_ID'] == player_id]
        if not player_stats.empty:
            basic_stats = player_stats.iloc[0].to_dict()

    # Generate skill grades
    skill_grades = generate_skill_grades(player_id, metrics, basic_stats)

    # Print skill grades
    print("Skill Grades:")
    for skill, grade in sorted(skill_grades.items()):
        print(f"{skill}: {grade}")
    print()

    # Print historical data
    historical_data = get_historical_player_data(player_id)

    print("Historical Data:")
    print(f"Years in league: {historical_data.get('years_played', 'N/A')}")
    print(f"Career achievements value: {historical_data.get('achievements_value', 'N/A')}")

    playoff_stats = historical_data.get('playoff_stats', {})
    if playoff_stats:
        print(f"Playoff games: {playoff_stats.get('games', 'N/A')}")
        print(f"Playoff PPG: {playoff_stats.get('points_per_game', 'N/A')}")

    return metrics, skill_grades

def main():
    """Main function to run the smoke test."""
    # Test with a few star players
    players = ["LeBron James", "Stephen Curry", "Nikola Jokic", "Giannis Antetokounmpo", "Luka Doncic"]

    for player in players:
        check_raptor_metrics(player)

if __name__ == "__main__":
    main()
