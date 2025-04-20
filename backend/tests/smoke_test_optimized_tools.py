import sys
import os
import json
from datetime import datetime, timedelta

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.api_tools.league_tools import fetch_league_standings_logic, fetch_scoreboard_logic
from backend.api_tools.search import search_games_logic
from backend.config import CURRENT_SEASON
from backend.api_tools.player_tools import fetch_player_gamelog_logic, fetch_player_career_stats_logic, fetch_player_shotchart_logic, fetch_player_hustle_stats_logic, fetch_player_profile_logic
from backend.api_tools.game_tools import fetch_boxscore_traditional_logic, fetch_playbyplay_logic, fetch_shotchart_logic as fetch_game_shotchart_logic, fetch_league_games_logic, fetch_boxscore_advanced_logic, fetch_boxscore_usage_logic, fetch_boxscore_defensive_logic # Renamed shotchart to avoid conflict

from backend.api_tools.team_tracking import fetch_team_passing_stats_logic, fetch_team_rebounding_stats_logic, fetch_team_shooting_stats_logic
from backend.api_tools.player_tracking import fetch_player_rebounding_stats_logic, fetch_player_passing_stats_logic, fetch_player_shots_tracking_logic, fetch_player_clutch_stats_logic
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from backend.api_tools.odds_tools import fetch_odds_data_logic # Import the odds function
from backend.api_tools.trending_tools import fetch_top_performers_logic
def run_smoke_test():
    print("Running smoke test for optimized tools...")

    # # Test fetch_league_standings_logic
    # print("\n--- Testing fetch_league_standings_logic ---")
    # try:
    #     standings_output = fetch_league_standings_logic(season=CURRENT_SEASON)
    #     print("Standings Output (first 500 characters):")
    #     print(standings_output[:500])
    #     print("\nFull Standings Output Length:", len(standings_output))
    #     # Optional: Parse JSON and print keys to verify structure
    #     # standings_data = json.loads(standings_output)
    #     # if standings_data and "standings" in standings_data and standings_data["standings"]:
    #     #     print("Sample Standings Record Keys:", standings_data["standings"][0].keys())

    # except Exception as e:
    #     print(f"Error testing fetch_league_standings_logic: {e}")

    # # Test fetch_scoreboard_logic
    # print("\n--- Testing fetch_scoreboard_logic ---")
    # try:
    #     # Use a recent date with games if possible, otherwise today
    #     test_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    #     scoreboard_output = fetch_scoreboard_logic(game_date=test_date)
    #     print(f"Scoreboard Output for {test_date} (first 500 characters):")
    #     print(scoreboard_output[:500])
    #     print("\nFull Scoreboard Output Length:", len(scoreboard_output))
    #     # Optional: Parse JSON and print keys to verify structure
    #     # scoreboard_data = json.loads(scoreboard_output)
    #     # if scoreboard_data and "game_header" in scoreboard_data and scoreboard_data["game_header"]:
    #     #      print("Sample Game Header Keys:", scoreboard_data["game_header"][0].keys())
    #     # if scoreboard_data and "line_score" in scoreboard_data and scoreboard_data["line_score"]:
    #     #      print("Sample Line Score Keys:", scoreboard_data["line_score"][0].keys())

    # except Exception as e:
    #     print(f"Error testing fetch_scoreboard_logic: {e}")

    # # Test search_games_logic
    # print("\n--- Testing search_games_logic ---")
    # try:
    #     search_query = "Lakers vs Celtics"
    #     search_season = "2023-24" # Use a season with known matchups
    #     game_search_output = search_games_logic(query=search_query, season=search_season)
    #     print(f"Game Search Output for '{search_query}' in {search_season} (first 500 characters):")
    #     print(game_search_output[:500])
    #     print("\nFull Game Search Output Length:", len(game_search_output))
    #     # Optional: Parse JSON and print keys to verify structure
    #     # game_search_data = json.loads(game_search_output)
    #     # if game_search_data and "games" in game_search_data and game_search_data["games"]:
    #     #     print("Sample Game Search Record Keys:", game_search_data["games"][0].keys())

    # except Exception as e:
    #     print(f"Error testing search_games_logic: {e}")

    # # Test fetch_player_gamelog_logic
    # print("\n--- Testing fetch_player_gamelog_logic ---")
    # try:
    #     player_name_gamelog = "LeBron James" # Use a known player
    #     season_gamelog = "2023-24" # Use a season with games
    #     gamelog_output = fetch_player_gamelog_logic(player_name=player_name_gamelog, season=season_gamelog)
    #     print(f"Gamelog Output for '{player_name_gamelog}' in {season_gamelog} (first 500 characters):")
    #     print(gamelog_output[:500])
    #     print("\nFull Gamelog Output Length:", len(gamelog_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_gamelog_logic: {e}")

    # # Test fetch_player_career_stats_logic
    # print("\n--- Testing fetch_player_career_stats_logic ---")
    # try:
    #     player_name_career = "LeBron James" # Use a known player
    #     career_stats_output = fetch_player_career_stats_logic(player_name=player_name_career)
    #     print(f"Career Stats Output for '{player_name_career}' (first 500 characters):")
    #     print(career_stats_output[:500])
    #     print("\nFull Career Stats Output Length:", len(career_stats_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_career_stats_logic: {e}")

    # # Test fetch_player_shotchart_logic
    # print("\n--- Testing fetch_player_shotchart_logic ---")
    # try:
    #     player_name_shotchart = "Stephen Curry" # Use a known player
    #     season_shotchart = "2023-24" # Use a season with shots
    #     shotchart_output = fetch_player_shotchart_logic(player_name=player_name_shotchart, season=season_shotchart)
    #     print(f"Shot Chart Output for '{player_name_shotchart}' in {season_shotchart} (first 500 characters):")
    #     print(shotchart_output[:500])
    #     print("\nFull Shot Chart Output Length:", len(shotchart_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_shotchart_logic: {e}")

    # # Test fetch_player_hustle_stats_logic (player)
    # print("\n--- Testing fetch_player_hustle_stats_logic (player) ---")
    # try:
    #     player_name_hustle = "LeBron James" # Use a known player
    #     season_hustle = "2023-24" # Use a season with hustle stats
    #     hustle_player_output = fetch_player_hustle_stats_logic(player_name=player_name_hustle, season=season_hustle)
    #     print(f"Hustle Stats Output for '{player_name_hustle}' in {season_hustle} (first 500 characters):")
    #     print(hustle_player_output[:500])
    #     print("\nFull Hustle Stats Output Length:", len(hustle_player_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_hustle_stats_logic (player): {e}")

    # # Test fetch_player_hustle_stats_logic (league-wide, limited)
    # print("\n--- Testing fetch_player_hustle_stats_logic (league-wide) ---")
    # try:
    #     season_hustle_league = "2023-24" # Use a season
    #     hustle_league_output = fetch_player_hustle_stats_logic(season=season_hustle_league) # No player_name or team_id
    #     print(f"Hustle Stats Output for league-wide in {season_hustle_league} (first 500 characters):")
    #     print(hustle_league_output[:500])
    #     print("\nFull Hustle Stats Output Length:", len(hustle_league_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_hustle_stats_logic (league-wide): {e}")

    # # Test fetch_player_profile_logic
    # print("\n--- Testing fetch_player_profile_logic ---")
    # try:
    #     player_name_profile = "LeBron James" # Use a known player
    #     profile_output = fetch_player_profile_logic(player_name=player_name_profile)
    #     print(f"Player Profile Output for '{player_name_profile}' (first 500 characters):")
    #     print(profile_output[:500])
    #     print("\nFull Player Profile Output Length:", len(profile_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_profile_logic: {e}")


    # # Test fetch_player_rebounding_stats_logic
    # print("\n--- Testing fetch_player_rebounding_stats_logic ---")
    # try:
    #     player_name_reb = "LeBron James" # Use a known player
    #     season_reb = "2023-24" # Use a season
    #     rebounding_output = fetch_player_rebounding_stats_logic(player_name=player_name_reb, season=season_reb)
    #     print(f"Rebounding Stats Output for '{player_name_reb}' in {season_reb} (first 500 characters):")
    #     print(rebounding_output[:500])
    #     print("\nFull Rebounding Stats Output Length:", len(rebounding_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_rebounding_stats_logic: {e}")

    # # Test fetch_player_passing_stats_logic
    # print("\n--- Testing fetch_player_passing_stats_logic ---")
    # try:
    #     player_name_pass = "LeBron James" # Use a known player
    #     season_pass = "2023-24" # Use a season
    #     passing_output = fetch_player_passing_stats_logic(player_name=player_name_pass, season=season_pass)
    #     print(f"Passing Stats Output for '{player_name_pass}' in {season_pass} (first 500 characters):")
    #     print(passing_output[:500])
    #     print("\nFull Passing Stats Output Length:", len(passing_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_passing_stats_logic: {e}")

    # # Test fetch_player_shots_tracking_logic
    # print("\n--- Testing fetch_player_shots_tracking_logic ---")
    # try:
    #     player_id_shots = "2544" # LeBron James ID
    #     season_shots = "2023-24" # Use a season
    #     shots_tracking_output = fetch_player_shots_tracking_logic(player_id=player_id_shots, season=season_shots)
    #     print(f"Shots Tracking Output for player ID {player_id_shots} in {season_shots} (first 500 characters):")
    #     print(shots_tracking_output[:500])
    #     print("\nFull Shots Tracking Output Length:", len(shots_tracking_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_shots_tracking_logic: {e}")

    # # Test fetch_player_clutch_stats_logic
    # print("\n--- Testing fetch_player_clutch_stats_logic ---")
    # try:
    #     player_name_clutch = "LeBron James" # Use a known player
    #     season_clutch = "2023-24" # Use a season
    #     clutch_stats_output = fetch_player_clutch_stats_logic(player_name=player_name_clutch, season=season_clutch)
    #     print(f"Clutch Stats Output for '{player_name_clutch}' in {season_clutch} (first 500 characters):")
    #     print(clutch_stats_output[:500])
    #     print("\nFull Clutch Stats Output Length:", len(clutch_stats_output))
    # except Exception as e:
    #     print(f"Error testing fetch_player_clutch_stats_logic: {e}")

    # Test fetch_team_passing_stats_logic
    print("\n--- Testing fetch_team_passing_stats_logic ---")
    try:
        team_identifier_pass = "Lakers" # Use a known team
        season_pass = "2023-24" # Use a season
        team_passing_output = fetch_team_passing_stats_logic(team_identifier=team_identifier_pass, season=season_pass)
        print(f"Team Passing Stats Output for '{team_identifier_pass}' in {season_pass} (first 500 characters):")
        print(team_passing_output[:500])
        print("\nFull Team Passing Stats Output Length:", len(team_passing_output))
    except Exception as e:
        print(f"Error testing fetch_team_passing_stats_logic: {e}")

    # Test fetch_team_rebounding_stats_logic
    print("\n--- Testing fetch_team_rebounding_stats_logic ---")
    try:
        team_identifier_reb = "Lakers" # Use a known team
        season_reb = "2023-24" # Use a season
        team_rebounding_output = fetch_team_rebounding_stats_logic(team_identifier=team_identifier_reb, season=season_reb)
        print(f"Team Rebounding Stats Output for '{team_identifier_reb}' in {season_reb} (first 500 characters):")
        print(team_rebounding_output[:500])
        print("\nFull Team Rebounding Stats Output Length:", len(team_rebounding_output))
    except Exception as e:
        print(f"Error testing fetch_team_rebounding_stats_logic: {e}")

    # Test fetch_team_shooting_stats_logic
    print("\n--- Testing fetch_team_shooting_stats_logic ---")
    try:
        team_identifier_shoot = "Lakers" # Use a known team
        season_shoot = "2023-24" # Use a season
        team_shooting_output = fetch_team_shooting_stats_logic(team_identifier=team_identifier_shoot, season=season_shoot)
        print(f"Team Shooting Stats Output for '{team_identifier_shoot}' in {season_shoot} (first 500 characters):")
        print(team_shooting_output[:500])
        print("\nFull Team Shooting Stats Output Length:", len(team_shooting_output))
    except Exception as e:
        print(f"Error testing fetch_team_shooting_stats_logic: {e}")

    # Test fetch_synergy_play_types_logic (Team)
    print("\n--- Testing fetch_synergy_play_types_logic (Team) ---")
    try:
        team_synergy_season = "2023-24" # Use a recent season
        # Test with default 'T' for player_or_team and specific type_grouping
        team_synergy_output = fetch_synergy_play_types_logic(
            season=team_synergy_season,
            player_or_team='T',  # Explicitly set to team
            type_grouping='offensive',  # Specify type grouping
            play_type='Isolation'  # Specify play type
        )
        print(f"Team Synergy Play Types Output for season {team_synergy_season} (first 500 characters):")
        print(team_synergy_output[:500])
        print("\nFull Team Synergy Output Length:", len(team_synergy_output))
    except Exception as e:
        print(f"Error testing fetch_synergy_play_types_logic (Team): {e}")

    # Test fetch_synergy_play_types_logic (Player)
    print("\n--- Testing fetch_synergy_play_types_logic (Player) ---")
    try:
        player_synergy_season = "2023-24" # Use a recent season
        # Test with 'P' for player_or_team and specific type_grouping
        player_synergy_output = fetch_synergy_play_types_logic(
            season=player_synergy_season,
            player_or_team='P',  # Set to player
            type_grouping='offensive',  # Specify type grouping
            play_type='Postup'  # Specify play type
        )
        print(f"Player Synergy Play Types Output for season {player_synergy_season} (first 500 characters):")
        print(player_synergy_output[:500])
        print("\nFull Player Synergy Output Length:", len(player_synergy_output))
    except Exception as e:
        print(f"Error testing fetch_synergy_play_types_logic (Player): {e}")

    # # Test fetch_boxscore_traditional_logic
    # print("\n--- Testing fetch_boxscore_traditional_logic ---")
    # try:
    #     game_id_boxscore = "0022300001" # Use a known game ID
    #     boxscore_traditional_output = fetch_boxscore_traditional_logic(game_id=game_id_boxscore)
    #     print(f"Traditional Box Score Output for game {game_id_boxscore} (first 500 characters):")
    #     print(boxscore_traditional_output[:500])
    #     print("\nFull Traditional Box Score Output Length:", len(boxscore_traditional_output))
    # except Exception as e:
    #     print(f"Error testing fetch_boxscore_traditional_logic: {e}")

    # # Test fetch_playbyplay_logic
    # print("\n--- Testing fetch_playbyplay_logic ---")
    # try:
    #     game_id_pbp = "0022300001" # Use a known game ID
    #     pbp_output = fetch_playbyplay_logic(game_id=game_id_pbp)
    #     print(f"Play-by-Play Output for game {game_id_pbp} (first 500 characters):")
    #     print(pbp_output[:500])
    #     print("\nFull Play-by-Play Output Length:", len(pbp_output))
    # except Exception as e:
    #     print(f"Error testing fetch_playbyplay_logic: {e}")

    # # Test fetch_game_shotchart_logic
    # print("\n--- Testing fetch_game_shotchart_logic ---")
    # try:
    #     game_id_game_shotchart = "0022300001" # Use a known game ID
    #     game_shotchart_output = fetch_game_shotchart_logic(game_id=game_id_game_shotchart)
    #     print(f"Game Shot Chart Output for game {game_id_game_shotchart} (first 500 characters):")
    #     print(game_shotchart_output[:500])
    #     print("\nFull Game Shot Chart Output Length:", len(game_shotchart_output))
    # except Exception as e:
    #     print(f"Error testing fetch_game_shotchart_logic: {e}")

    # # Test fetch_league_games_logic
    # print("\n--- Testing fetch_league_games_logic ---")
    # try:
    #     season_league_games = "2023-24" # Use a season
    #     league_games_output = fetch_league_games_logic(season_nullable=season_league_games)
    #     print(f"League Games Output for season {season_league_games} (first 500 characters):")
    #     print(league_games_output[:500])
    #     print("\nFull League Games Output Length:", len(league_games_output))
    # except Exception as e:
    #     print(f"Error testing fetch_league_games_logic: {e}")

    # # Test fetch_league_games_logic (league-wide, limited)
    # print("\n--- Testing fetch_league_games_logic (league-wide) ---")
    # try:
    #     league_games_limited_output = fetch_league_games_logic() # No parameters
    #     print(f"League Games Output for league-wide (first 500 characters):")
    #     print(league_games_limited_output[:500])
    #     print("\nFull League Games Output Length:", len(league_games_limited_output))
    # except Exception as e:
    #     print(f"Error testing fetch_league_games_logic (league-wide): {e}")

    # # Test fetch_league_games_logic (league-wide, limited)
    # print("\n--- Testing fetch_league_games_logic (league-wide) ---")
    # try:
    #     league_games_limited_output = fetch_league_games_logic() # No parameters
    #     print(f"League Games Output for league-wide (first 500 characters):")
    #     print(league_games_limited_output[:500])
    #     print("\nFull League Games Output Length:", len(league_games_limited_output))
    # except Exception as e:
    #     print(f"Error testing fetch_league_games_logic (league-wide): {e}")

    # # Test fetch_boxscore_advanced_logic
    # print("\n--- Testing fetch_boxscore_advanced_logic ---")
    # try:
    #     game_id_advanced_boxscore = "0022300001" # Use a known game ID
    #     boxscore_advanced_output = fetch_boxscore_advanced_logic(game_id=game_id_advanced_boxscore)
    #     print(f"Advanced Box Score Output for game {game_id_advanced_boxscore} (first 500 characters):")
    #     print(boxscore_advanced_output[:500])
    #     print("\nFull Advanced Box Score Output Length:", len(boxscore_advanced_output))
    # except Exception as e:
    #     print(f"Error testing fetch_boxscore_advanced_logic: {e}")

    # # Test fetch_boxscore_usage_logic
    # print("\n--- Testing fetch_boxscore_usage_logic ---")
    # try:
    #     game_id_usage_boxscore = "0022300001" # Use a known game ID
    #     boxscore_usage_output = fetch_boxscore_usage_logic(game_id=game_id_usage_boxscore)
    #     print(f"Usage Box Score Output for game {game_id_usage_boxscore} (first 500 characters):")
    #     print(boxscore_usage_output[:500])
    #     print("\nFull Usage Box Score Output Length:", len(boxscore_usage_output))
    # except Exception as e:
    #     print(f"Error testing fetch_boxscore_usage_logic: {e}")

    # # Test fetch_boxscore_defensive_logic
    # print("\n--- Testing fetch_boxscore_defensive_logic ---")
    # try:
    #     game_id_defensive_boxscore = "0022300001" # Use a known game ID
    #     boxscore_defensive_output = fetch_boxscore_defensive_logic(game_id=game_id_defensive_boxscore)
    #     print(f"Defensive Box Score Output for game {game_id_defensive_boxscore} (first 500 characters):")
    #     print(boxscore_defensive_output[:500])
    #     print("\nFull Defensive Box Score Output Length:", len(boxscore_defensive_output))
    # except Exception as e:
    #     print(f"Error testing fetch_boxscore_defensive_logic: {e}")
    # Test fetch_odds_data_logic
    print("\n--- Testing fetch_odds_data_logic ---")
    try:
        odds_output = fetch_odds_data_logic()
        print("Odds Data Output:")
        # Print the dictionary directly, or a formatted version
        print(json.dumps(odds_output, indent=2)[:500] + "...") # Print formatted JSON, truncated
        # Note: Calculating length of dictionary output is not directly comparable to string length
        # print("\nFull Odds Data Output Length:", len(json.dumps(odds_output))) # Optional: print length of JSON string
    except Exception as e:
        print(f"Error testing fetch_odds_data_logic: {e}")

    # Test fetch_top_performers_logic
    print("\n--- Testing fetch_top_performers_logic ---")
    try:
        top_performers_output = fetch_top_performers_logic(category="PTS", season=CURRENT_SEASON, top_n=5)
        print(f"Top Performers Output (PTS, {CURRENT_SEASON}, top 5):")
        print(top_performers_output[:500])
        print("\nFull Top Performers Output Length:", len(top_performers_output))
    except Exception as e:
        print(f"Error testing fetch_top_performers_logic: {e}")

if __name__ == "__main__":
    run_smoke_test()