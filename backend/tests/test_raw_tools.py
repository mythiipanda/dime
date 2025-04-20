import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Import logic functions from the specific backend.api_tools modules
from backend.api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_awards_logic,
    fetch_player_shotchart_logic,
    fetch_player_defense_logic,
    fetch_player_hustle_stats_logic,
    fetch_player_profile_logic,
    fetch_player_stats_logic # Assuming this exists and is the logic for get_player_aggregate_stats
)
from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    fetch_team_lineups_logic,
    fetch_team_stats_logic,
)
from backend.api_tools.game_tools import (
    fetch_boxscore_traditional_logic,
    fetch_playbyplay_logic,
    fetch_league_games_logic,
    fetch_shotchart_logic, # Game shotchart logic
    fetch_boxscore_advanced_logic,
    fetch_boxscore_four_factors_logic,
    fetch_boxscore_usage_logic,
    fetch_boxscore_defensive_logic,
    fetch_win_probability_logic
)
from backend.api_tools.league_tools import (
    fetch_league_standings_logic,
    fetch_scoreboard_logic,
    fetch_draft_history_logic,
    fetch_league_leaders_logic
)
from backend.api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_passing_stats_logic,
    fetch_player_shots_tracking_logic,
    fetch_player_rebounding_stats_logic
)
from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic
)
# Assuming scoreboard_tools has a logic function, if not, use fetch_scoreboard_logic
# from backend.api_tools.scoreboard.scoreboard_tools import fetch_scoreboard_data_logic 
from backend.api_tools.odds_tools import fetch_odds_data_logic
from backend.api_tools.analyze import analyze_player_stats_logic # Assuming this is the logic for get_player_analysis
from backend.api_tools.trending_tools import fetch_top_performers_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic, fetch_matchups_rollup_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic

from backend.config import CURRENT_SEASON
# print(fetch_league_leaders_logic(stat_category="PTS",season=CURRENT_SEASON))
def run_tool_tests():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"logic_raw_output_{timestamp}.txt" # Changed filename to reflect logic calls

    with open(output_file, "w", encoding="utf-8") as f:
        def write_test_output(name, result):
            f.write(f"\n{'='*80}\n")
            f.write(f"Testing {name}\n")
            f.write(f"{'='*80}\n")
            f.write(f"First 500 characters of output:\n")
            # Ensure result is a string before slicing
            f.write(str(result)[:500])
            f.write("\n")

        try:
            # # Player Tools Logic
            # write_test_output("fetch_player_info_logic",
            #     fetch_player_info_logic("LeBron James"))

            # write_test_output("fetch_player_gamelog_logic",
            #     fetch_player_gamelog_logic("LeBron James", CURRENT_SEASON))

            # write_test_output("fetch_player_career_stats_logic",
            #     fetch_player_career_stats_logic("LeBron James"))

            # write_test_output("fetch_player_awards_logic",
            #     fetch_player_awards_logic("LeBron James"))

            # write_test_output("fetch_player_shotchart_logic",
            #     fetch_player_shotchart_logic("Stephen Curry", CURRENT_SEASON))

            # write_test_output("fetch_player_defense_logic",
            #     fetch_player_defense_logic("Joel Embiid", CURRENT_SEASON))

            # write_test_output("fetch_player_hustle_stats_logic",
            #     fetch_player_hustle_stats_logic(player_name="Jimmy Butler", season=CURRENT_SEASON))

            # write_test_output("fetch_player_profile_logic",
            #     fetch_player_profile_logic("Kevin Durant"))

            # write_test_output("fetch_player_stats_logic (Aggregate)", # Renamed to reflect underlying logic
            #     fetch_player_stats_logic("Giannis Antetokounmpo", CURRENT_SEASON)) # Using Giannis as in tools.py

            # write_test_output("fetch_player_clutch_stats_logic",
            #     fetch_player_clutch_stats_logic("Damian Lillard", CURRENT_SEASON))

            # write_test_output("fetch_player_passing_stats_logic",
            #     fetch_player_passing_stats_logic("Luka Doncic", CURRENT_SEASON))

            # write_test_output("fetch_player_rebounding_stats_logic",
            #     fetch_player_rebounding_stats_logic("Nikola Jokic", CURRENT_SEASON))

            # write_test_output("fetch_player_shots_tracking_logic",
            #     fetch_player_shots_tracking_logic("2544")) # LeBron's ID

            # # Team Tools Logic
            # write_test_output("fetch_team_info_and_roster_logic",
            #     fetch_team_info_and_roster_logic("Lakers"))

            # write_test_output("fetch_team_stats_logic",
            #     fetch_team_stats_logic("Celtics", CURRENT_SEASON))

            # write_test_output("fetch_team_passing_stats_logic",
            #     fetch_team_passing_stats_logic("Warriors", CURRENT_SEASON))

            # write_test_output("fetch_team_shooting_stats_logic",
            #     fetch_team_shooting_stats_logic("Nuggets", CURRENT_SEASON))

            write_test_output("fetch_team_lineups_logic",
                fetch_team_lineups_logic(team_id=1610612747)) # Lakers ID

            # write_test_output("fetch_team_rebounding_stats_logic",
            #     fetch_team_rebounding_stats_logic("Bucks", CURRENT_SEASON))

            # # Game/League Tools Logic
            # write_test_output("fetch_league_games_logic",
            #     fetch_league_games_logic(player_or_team_abbreviation='T', team_id_nullable=1610612747, season_nullable=CURRENT_SEASON)) # Using team_id as in find_games tool

            # write_test_output("fetch_boxscore_traditional_logic",
            #     fetch_boxscore_traditional_logic("0022300001"))

            # write_test_output("fetch_league_standings_logic",
            #     fetch_league_standings_logic(CURRENT_SEASON))

            # write_test_output("fetch_scoreboard_logic",
            #     fetch_scoreboard_logic()) # Uses default date

            # write_test_output("fetch_playbyplay_logic",
            #     fetch_playbyplay_logic("0022300001"))

            write_test_output("fetch_draft_history_logic",
                fetch_draft_history_logic("2023"))
            # fetch_league_leaders_logic(season=CURRENT_SEASON)
            # write_test_output("fetch_league_leaders_logic",
            #     fetch_league_leaders_logic(stat_category="PTS", season=CURRENT_SEASON))

            # write_test_output("fetch_top_performers_logic", # Trending tools logic
            #     fetch_top_performers_logic("PTS", CURRENT_SEASON))

            # write_test_output("fetch_top_teams_logic", # Trending team tools logic
            #     fetch_top_teams_logic(CURRENT_SEASON))

            # write_test_output("analyze_player_stats_logic", # Analyze logic
            #     analyze_player_stats_logic("Giannis Antetokounmpo", CURRENT_SEASON)) # Using Giannis as in tools.py

            # write_test_output("fetch_odds_data_logic",
            #     fetch_odds_data_logic())

            # write_test_output("fetch_shotchart_logic (Game)", # Game shotchart logic
            #     fetch_shotchart_logic("0022300001"))

            # write_test_output("fetch_boxscore_advanced_logic",
            #     fetch_boxscore_advanced_logic("0022300001"))

            write_test_output("fetch_boxscore_four_factors_logic",
                fetch_boxscore_four_factors_logic("0022300001"))

            write_test_output("fetch_boxscore_usage_logic",
                fetch_boxscore_usage_logic("0022300001"))

            write_test_output("fetch_boxscore_defensive_logic",
                fetch_boxscore_defensive_logic("0022300001"))

            write_test_output("fetch_win_probability_logic",
                fetch_win_probability_logic("0022300001"))

            # Matchup Tools Logic
            write_test_output("fetch_league_season_matchups_logic",
                fetch_league_season_matchups_logic('2544', '201939', CURRENT_SEASON, 'Regular Season')) # Using example IDs from test_smoke_tools

            write_test_output("fetch_matchups_rollup_logic",
                fetch_matchups_rollup_logic('2544', CURRENT_SEASON, 'Regular Season')) # Using example ID from test_smoke_tools

            # Synergy Tools Logic
            write_test_output("fetch_synergy_play_types_logic",
                fetch_synergy_play_types_logic(
                    season=CURRENT_SEASON,  # Use the current season
                    player_or_team='T',  # Explicitly set to team
                    type_grouping='offensive',  # Specify type grouping
                    play_type='Isolation'  # Specify play type
                )
            )

        except Exception as e:
            f.write(f"\nError during testing: {str(e)}\n")
            import traceback
            f.write(traceback.format_exc()) # Write full traceback for debugging

if __name__ == "__main__":
    run_tool_tests()
