"""
Script to check raw NBA API data for advanced metrics and skill grades.
This will help us verify the accuracy of our ELO ratings and skill grades.
"""

import sys
import os
import pandas as pd
import json
import time

# Add the parent directory to the path so we can import from api_tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nba_api.stats.endpoints import leaguedashplayerstats
from api_tools.utils import retry_on_timeout
from api_tools.advanced_metrics import (
    fetch_player_advanced_analysis_logic,
    generate_skill_grades_legacy,
    calculate_percentile,
    get_league_stats_for_percentiles
)

# Import RAPTOR metrics if available
try:
    from api_tools.raptor_metrics import (
        get_player_raptor_metrics,
        generate_skill_grades,
        get_league_stats_for_percentiles as raptor_get_league_stats
    )
    RAPTOR_AVAILABLE = True
except ImportError:
    RAPTOR_AVAILABLE = False

def check_league_stats_percentiles():
    """Fetch league-wide stats and calculate percentiles for key metrics."""
    print(f"\n{'='*50}")
    print(f"League-Wide Stats Percentiles")
    print(f"{'='*50}\n")

    # Get league stats for percentiles
    league_stats = get_league_stats_for_percentiles()

    if not league_stats:
        print("Error: Could not fetch league stats for percentiles.")
        return

    # Print the number of players in each stat distribution
    print(f"Number of players in dataset:")
    for stat, values in league_stats.items():
        print(f"{stat}: {len(values)} players")

    # Print percentiles for key metrics
    key_metrics = ['PTS', 'AST', 'REB', 'STL', 'BLK', 'TS_PCT', 'PIE', 'ORTG', 'DRTG']

    print("\nPercentile values for key metrics:")
    for metric in key_metrics:
        if metric in league_stats:
            values = sorted(league_stats[metric])
            percentiles = {
                '10th': values[int(len(values) * 0.1)] if len(values) > 10 else None,
                '25th': values[int(len(values) * 0.25)] if len(values) > 4 else None,
                '50th': values[int(len(values) * 0.5)] if len(values) > 2 else None,
                '75th': values[int(len(values) * 0.75)] if len(values) > 4 else None,
                '90th': values[int(len(values) * 0.9)] if len(values) > 10 else None,
                '95th': values[int(len(values) * 0.95)] if len(values) > 20 else None
            }
            print(f"{metric}: {percentiles}")

def check_player_skill_grades(player_id, player_name):
    """Check skill grades for a specific player."""
    print(f"\n{'='*50}")
    print(f"Skill Grades for {player_name} (ID: {player_id})")
    print(f"{'='*50}\n")

    # Use RAPTOR metrics if available
    if RAPTOR_AVAILABLE:
        try:
            # Get RAPTOR metrics
            raptor_metrics = get_player_raptor_metrics(player_id, "2023-24")

            if not raptor_metrics:
                print("Error: Could not fetch RAPTOR metrics. Falling back to standard metrics.")
            else:
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

                # Print key metrics from RAPTOR
                print("Key metrics from RAPTOR:")
                key_metrics = ['RAPTOR_OFFENSE', 'RAPTOR_DEFENSE', 'RAPTOR_TOTAL', 'WAR',
                              'TS_PCT', 'USG_PCT', 'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT', 'PIE']

                for metric in key_metrics:
                    if metric in raptor_metrics:
                        print(f"{metric}: {raptor_metrics[metric]}")

                # Print key metrics from basic stats
                print("\nKey metrics from basic stats:")
                basic_key_metrics = ['PTS', 'AST', 'REB', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT']

                for metric in basic_key_metrics:
                    if metric in basic_stats:
                        print(f"{metric}: {basic_stats[metric]}")

                # Generate skill grades using RAPTOR
                skill_grades = generate_skill_grades(player_id, raptor_metrics, basic_stats)

                print("\nRAPTOR Skill Grades:")
                for skill, grade in sorted(skill_grades.items()):
                    print(f"{skill}: {grade}")

                # Print ELO rating components
                print("\nELO Rating Components:")
                elo_components = ['ELO_RATING', 'ELO_CURRENT', 'ELO_HISTORICAL']

                for component in elo_components:
                    if component in raptor_metrics:
                        print(f"{component}: {raptor_metrics[component]}")

                # We've used RAPTOR metrics, so return early
                return
        except Exception as e:
            print(f"Error using RAPTOR metrics: {str(e)}. Falling back to standard metrics.")

    # Fallback to standard metrics
    result_json = fetch_player_advanced_analysis_logic(player_name, "2023-24")
    result_data = json.loads(result_json)

    if 'error' in result_data:
        print(f"Error: {result_data['error']}")
        return

    metrics = result_data.get('advanced_metrics', {})

    if not metrics:
        print("Error: Could not fetch advanced metrics.")
        return

    # Print key metrics used for skill grades
    print("Key metrics used for skill grades:")
    key_metrics = ['PTS', 'AST', 'REB', 'STL', 'BLK', 'TS_PCT', 'FG_PCT', 'FG3_PCT',
                  'AST_PCT', 'REB_PCT', 'OREB_PCT', 'DREB_PCT', 'ORTG', 'DRTG', 'PIE']

    for metric in key_metrics:
        if metric in metrics:
            print(f"{metric}: {metrics[metric]}")

    # Get league stats for percentiles
    league_stats = get_league_stats_for_percentiles()

    if not league_stats:
        print("\nError: Could not fetch league stats for percentiles.")
        return

    # Calculate and print percentiles for key metrics
    print("\nPercentiles for key metrics:")
    for metric in key_metrics:
        if metric in metrics and metric in league_stats:
            percentile = calculate_percentile(metrics[metric], league_stats[metric])
            print(f"{metric}: {percentile:.2f} ({percentile*100:.1f}%)")

    # Generate and print skill grades
    grades = generate_skill_grades(metrics)

    if not grades:
        print("\nError: Could not generate skill grades.")
        return

    print("\nSkill Grades:")
    for skill, grade in sorted(grades.items()):
        print(f"{skill}: {grade}")

def check_player_elo_rating(player_id, player_name):
    """Check ELO rating components for a specific player."""
    print(f"\n{'='*50}")
    print(f"ELO Rating for {player_name} (ID: {player_id})")
    print(f"{'='*50}\n")

    # Use RAPTOR metrics if available
    if RAPTOR_AVAILABLE:
        try:
            # Get RAPTOR metrics
            raptor_metrics = get_player_raptor_metrics(player_id, "2023-24")

            if not raptor_metrics:
                print("Error: Could not fetch RAPTOR metrics. Falling back to standard metrics.")
            else:
                # Print ELO rating components
                print("RAPTOR ELO Rating Components:")
                elo_components = ['ELO_RATING', 'ELO_CURRENT', 'ELO_HISTORICAL']

                for component in elo_components:
                    if component in raptor_metrics:
                        print(f"{component}: {raptor_metrics[component]}")

                # Print key metrics used for ELO calculation
                print("\nKey metrics used for RAPTOR ELO calculation:")
                key_metrics = ['RAPTOR_TOTAL', 'WAR', 'PIE', 'ORTG', 'DRTG']

                for metric in key_metrics:
                    if metric in raptor_metrics:
                        print(f"{metric}: {raptor_metrics[metric]}")

                # Print historical data
                print("\nHistorical data used for ELO calculation:")
                historical_data = raptor_metrics.get('historical_data', {})
                if historical_data:
                    print(f"Years in league: {historical_data.get('years_played', 'N/A')}")
                    print(f"Career achievements value: {historical_data.get('achievements_value', 'N/A')}")

                    playoff_stats = historical_data.get('playoff_stats', {})
                    if playoff_stats:
                        print(f"Playoff games: {playoff_stats.get('games', 'N/A')}")
                        print(f"Playoff PPG: {playoff_stats.get('points_per_game', 'N/A')}")

                # We've used RAPTOR metrics, so return early
                return
        except Exception as e:
            print(f"Error using RAPTOR metrics: {str(e)}. Falling back to standard metrics.")

    # Fallback to standard metrics
    result_json = fetch_player_advanced_analysis_logic(player_name, "2023-24")
    result_data = json.loads(result_json)

    if 'error' in result_data:
        print(f"Error: {result_data['error']}")
        return

    metrics = result_data.get('advanced_metrics', {})

    if not metrics:
        print("Error: Could not fetch advanced metrics.")
        return

    # Print ELO rating components
    print("ELO Rating Components:")
    elo_components = ['ELO_RATING', 'ELO_CURRENT', 'ELO_HISTORICAL']

    for component in elo_components:
        if component in metrics:
            print(f"{component}: {metrics[component]}")

    # Print key metrics used for ELO calculation
    print("\nKey metrics used for ELO calculation:")
    key_metrics = ['PIE', 'ORTG', 'DRTG', 'NBA_PLUS', 'NBA_PLUS_OFF', 'NBA_PLUS_DEF']

    for metric in key_metrics:
        if metric in metrics:
            print(f"{metric}: {metrics[metric]}")

if __name__ == "__main__":
    # Check league-wide stats percentiles
    check_league_stats_percentiles()

    # Check skill grades for LeBron James
    check_player_skill_grades(2544, "LeBron James")

    # Check skill grades for Stephen Curry
    check_player_skill_grades(201939, "Stephen Curry")

    # Check skill grades for Nikola Jokic
    check_player_skill_grades(203999, "Nikola Jokic")

    # Check ELO ratings
    check_player_elo_rating(2544, "LeBron James")
    check_player_elo_rating(201939, "Stephen Curry")
    check_player_elo_rating(203999, "Nikola Jokic")
