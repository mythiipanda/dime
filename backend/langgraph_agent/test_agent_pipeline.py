import os
import sys
import json
from typing import Dict, Any, List
import builtins
from contextlib import redirect_stdout

from langgraph_agent.graph import app
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

def run_agent_test(test_name: str, input_query: str, expected_tool_name: str = None, expected_final_answer_substring: str = None):
    """
    Runs a single test case for the Langgraph agent and prints detailed output.
    """
    print(f"\n--- Running Test: {test_name} ---")
    print(f"Input Query: {input_query}")

    inputs = {
        "input_query": input_query,
        "chat_history": []
    }

    final_graph_state: Dict[str, Any] = {}
    tool_called = False
    final_answer_received = False
    
    try:
        # Add a dummy config for the checkpointer
        config = {"configurable": {"thread_id": "test_thread", "checkpoint_ns": "test_ns"}}
        for event in app.stream(inputs, config=config, stream_mode="updates"):
            node_name, node_output_state = list(event.items())[0]
            print(f"\nNODE EXECUTED: {node_name}")
            
            if node_output_state and 'messages' in node_output_state and node_output_state['messages']:
                last_message = node_output_state['messages'][-1]
                print(f"  LAST MESSAGE: {last_message}")

                if isinstance(last_message, AIMessage) and last_message.tool_calls:
                    print(f"  TOOL CALLS DETECTED: {last_message.tool_calls}")
                    if expected_tool_name:
                        for tool_call in last_message.tool_calls:
                            if tool_call.get('name') == expected_tool_name:
                                tool_called = True
                                print(f"  SUCCESS: Expected tool '{expected_tool_name}' was called.")
                                break
                elif isinstance(last_message, ToolMessage):
                    print(f"  TOOL OUTPUT: {last_message.content}")
                
                if node_output_state.get('final_answer'):
                    print(f"  FINAL ANSWER: {node_output_state['final_answer']}")
                    final_answer_received = True
                    if expected_final_answer_substring and expected_final_answer_substring.lower() in node_output_state['final_answer'].lower():
                        print(f"  SUCCESS: Final answer contains expected substring: '{expected_final_answer_substring}'")
                    elif expected_final_answer_substring:
                        print(f"  FAILURE: Final answer does NOT contain expected substring: '{expected_final_answer_substring}'")

            final_graph_state.update(node_output_state)

    except Exception as e:
        print(f"ERROR during agent execution: {e}")
        print("--- Test FAILED due to exception ---")
        return False

    print("\n--- Test Summary ---")
    if expected_tool_name and not tool_called:
        print(f"FAILURE: Expected tool '{expected_tool_name}' was NOT called.")
        return False
    
    if expected_final_answer_substring and not final_answer_received:
        print(f"FAILURE: Expected final answer was NOT received.")
        return False
    
    print("Test completed. Check logs above for details.")
    return True

if __name__ == "__main__":
    test_results = []

    test_cases = [
        # Player Tools
        {"name": "Player Shot Chart Test", "query": "Show me LeBron James' shot chart for the 2022-23 season, regular season.", "tool": "get_player_shot_chart"},
        {"name": "Player Aggregate Stats Test", "query": "Give me aggregated stats for LeBron James for the 2023-24 season.", "tool": "get_player_aggregate_stats"},
        {"name": "Player Career By College Stats Test", "query": "Show me career stats for players from Duke.", "tool": "get_player_career_by_college_stats"},
        {"name": "Player Career By College Rollup Stats Test", "query": "Show me college rollup stats for all players.", "tool": "get_player_career_by_college_rollup_stats"},
        {"name": "Player Career Stats Test", "query": "What are Stephen Curry's career stats?", "tool": "get_player_career_stats"},
        {"name": "Player Awards Test", "query": "What awards has Michael Jordan won?", "tool": "get_player_awards"},
        {"name": "Player Clutch Stats Test", "query": "Show me LeBron James' clutch stats for the 2022-23 season.", "tool": "get_player_clutch_stats"},
        {"name": "Player Info Test", "query": "Tell me about Kevin Durant.", "tool": "get_player_info"},
        {"name": "Player Compare Stats Test", "query": "Compare LeBron James (ID 2544) and Stephen Curry (ID 201939) for the 2023-24 season.", "tool": "get_player_compare_stats"},
        {"name": "Player Dashboard By Year Over Year Test", "query": "Show me LeBron James' year over year dashboard stats for the 2023-24 season.", "tool": "get_player_dashboard_by_year_over_year"},
        {"name": "Player Dashboard Game Splits Test", "query": "What are Nikola Jokic's game splits for the 2023-24 regular season?", "tool": "get_player_dashboard_game_splits"},
        {"name": "Player Dashboard General Splits Test", "query": "Show me Giannis Antetokounmpo's general splits for the 2023-24 regular season.", "tool": "get_player_dashboard_general_splits"},
        {"name": "Player Dashboard Last N Games Test", "query": "What are Luka Doncic's stats for his last 10 games in the 2023-24 season?", "tool": "get_player_dashboard_last_n_games"},
        {"name": "Player Dashboard Shooting Splits Test", "query": "Show me Jayson Tatum's shooting splits for the 2023-24 regular season.", "tool": "get_player_dashboard_shooting_splits"},
        {"name": "Player Profile Test", "query": "Give me the profile for Joel Embiid.", "tool": "get_player_profile"},
        {"name": "Player Defense Stats Test", "query": "What are Rudy Gobert's defensive stats for the 2023-24 season?", "tool": "get_player_defense_stats"},
        {"name": "Player Hustle Stats Test", "query": "Show me hustle stats for the 2023-24 season.", "tool": "get_player_hustle_stats"},
        {"name": "Player Estimated Metrics Test", "query": "What are the estimated metrics for the 2023-24 season?", "tool": "get_player_estimated_metrics"},
        {"name": "Player Fantasy Profile Test", "query": "Show me LeBron James' fantasy profile for the 2023-24 season.", "tool": "get_player_fantasy_profile"},
        {"name": "Player Fantasy Profile Bar Graph Test", "query": "Give me LeBron James' fantasy profile bar graph data for the 2023-24 season.", "tool": "get_player_fantasy_profile_bar_graph"},
        {"name": "Player Game Logs Test", "query": "Show me game logs for Damian Lillard for the 2023-24 season.", "tool": "get_player_game_logs"},
        {"name": "Player Game Streak Finder Test", "query": "Find game streaks for Stephen Curry.", "tool": "get_player_game_streak_finder"},
        {"name": "Player Index Test", "query": "List all active players for the 2023-24 season.", "tool": "get_player_index"},
        {"name": "Player Listings Test", "query": "List all players for the 2023-24 season.", "tool": "get_player_listings"},
        {"name": "Player Passing Stats Test", "query": "Show me Nikola Jokic's passing stats for the 2023-24 season.", "tool": "get_player_passing_stats"},
        {"name": "Player Rebounding Stats Test", "query": "What are Domantas Sabonis' rebounding stats for the 2023-24 season?", "tool": "get_player_rebounding_stats"},
        {"name": "Player Shots Tracking Stats Test", "query": "Show me Kevin Durant's shots tracking stats for the 2023-24 season.", "tool": "get_player_shots_tracking_stats"},
        {"name": "Player Vs Player Stats Test", "query": "Compare LeBron James (ID 2544) and Michael Jordan (ID 893) head-to-head for the 1997-98 season.", "tool": "get_player_vs_player_stats"},

        # Team Tools
        {"name": "Team Lineups Test", "query": "What were the most effective 5-man lineups for the Golden State Warriors in the 2023-24 playoffs?", "tool": "get_team_lineups"},
        {"name": "Team Game Logs Test", "query": "Show me game logs for the Los Angeles Lakers for the 2023-24 season.", "tool": "get_team_game_logs"},
        {"name": "Team Historical Leaders Test", "query": "Who are the historical leaders for the Boston Celtics?", "tool": "get_team_historical_leaders"},
        {"name": "Team Passing Stats Test", "query": "Show me the passing stats for the Denver Nuggets for the 2023-24 season.", "tool": "get_team_passing_stats"},
        {"name": "Team Player Dashboard Test", "query": "Give me the player dashboard for the Milwaukee Bucks for the 2023-24 season.", "tool": "get_team_player_dashboard"},
        {"name": "Team Player On Off Summary Test", "query": "Summarize the on/off court stats for players on the Phoenix Suns for the 2023-24 season.", "tool": "get_team_player_on_off_summary"},
        {"name": "Team Vs Player Stats Test", "query": "How do the Golden State Warriors perform against LeBron James?", "tool": "get_team_vs_player_stats"},
        {"name": "Team Shooting Stats Test", "query": "What are the shooting stats for the Brooklyn Nets for the 2023-24 season?", "tool": "get_team_shooting_stats"},
        {"name": "Team Player On Off Details Test", "query": "Show me detailed on/off court stats for players on the Philadelphia 76ers for the 2023-24 season.", "tool": "get_team_player_on_off_details"},
        {"name": "Team Rebounding Stats Test", "query": "What are the rebounding stats for the Cleveland Cavaliers for the 2023-24 season?", "tool": "get_team_rebounding_stats"},
        {"name": "Team Info and Roster Test", "query": "Give me the roster and info for the Chicago Bulls.", "tool": "get_team_info_and_roster"},
        {"name": "Team History Test", "query": "Tell me about the history of the New York Knicks.", "tool": "get_team_history"},
        {"name": "Team General Stats Test", "query": "What are the general stats for the Dallas Mavericks for the 2023-24 season?", "tool": "get_team_general_stats"},
        {"name": "Team Estimated Metrics Test", "query": "Show me the estimated metrics for the Miami Heat for the 2023-24 season.", "tool": "get_team_estimated_metrics"},
        {"name": "Team Shooting Splits Test", "query": "What are the shooting splits for the Atlanta Hawks for the 2023-24 season?", "tool": "get_team_shooting_splits"},
        {"name": "Team Details Test", "query": "Give me the details for the Toronto Raptors.", "tool": "get_team_details"},
        {"name": "Team Shot Dashboard Test", "query": "Show me the shot dashboard for the Utah Jazz for the 2023-24 season.", "tool": "get_team_shot_dashboard"},

        # Search Tools
        {"name": "Player Search Test", "query": "Search for players named 'Jordan'.", "tool": "search_nba_players"},
        {"name": "Team Search Test", "query": "Search for teams named 'Lakers'.", "tool": "search_nba_teams"},
        {"name": "Game Search Test", "query": "Search for games on 2023-12-25.", "tool": "search_nba_games"},

        # Synergy Tools
        {"name": "Synergy Play Types Test", "query": "2024-25 PLAYERS Top 5 PRRollman by PPP (Offensive) and Top 5 Isolation Players by PPP (Offensive)?", "tool": "get_synergy_play_types"},

        # Fantasy Tools
        {"name": "Fantasy Widget Data Test", "query": "Show me fantasy widget data for the 2023-24 season.", "tool": "get_nba_fantasy_widget_data"},

        # Franchise Tools
        {"name": "Franchise History Test", "query": "Tell me about the history of the Lakers franchise.", "tool": "get_nba_franchise_history"},
        {"name": "Franchise Players Test", "query": "List all players who have played for the Celtics franchise.", "tool": "get_nba_franchise_players"},
        {"name": "Franchise Leaders Test", "query": "Who are the all-time leaders for the Bulls franchise?", "tool": "get_nba_franchise_leaders"},

        # Free Agent Tools
        {"name": "Free Agent Info Test", "query": "Give me information about free agents for the 2024-25 season.", "tool": "get_nba_free_agent_info"},
        {"name": "Team Free Agents Test", "query": "Which players are free agents for the Warriors?", "tool": "get_nba_team_free_agents"},
        {"name": "Top Free Agents Test", "query": "Who are the top free agents for the 2024-25 season?", "tool": "get_nba_top_free_agents"},
        {"name": "Search Free Agents Test", "query": "Search for free agents named 'Fred'.", "tool": "search_nba_free_agents"},

        # Contracts Tools
        {"name": "Player Contract Test", "query": "What is LeBron James' contract details?", "tool": "get_nba_player_contract"},
        {"name": "Team Payroll Test", "query": "Show me the payroll for the Los Angeles Lakers.", "tool": "get_nba_team_payroll"},
        {"name": "Highest Paid Players Test", "query": "Who are the highest paid players in the NBA?", "tool": "get_nba_highest_paid_players"},
        {"name": "Search Player Contracts Test", "query": "Search for player contracts for 'Curry'.", "tool": "search_nba_player_contracts"},

        # Draft Combine Tools
        {"name": "Draft Combine Drill Results Test", "query": "Show me the 2023 NBA Draft Combine drill results.", "tool": "get_nba_draft_combine_drill_results"},
        {"name": "Draft Combine Nonstationary Shooting Test", "query": "Show me the 2023 NBA Draft Combine nonstationary shooting results.", "tool": "get_nba_draft_combine_nonstationary_shooting"},
        {"name": "Draft Combine Player Anthropometric Test", "query": "Show me the 2023 NBA Draft Combine anthropometric measurements.", "tool": "get_nba_draft_combine_player_anthropometric"},
        {"name": "Draft Combine Stats Test", "query": "Show me the 2023 NBA Draft Combine stats.", "tool": "get_nba_draft_combine_stats"},
        {"name": "Draft Combine Spot Shooting Test", "query": "Show me the 2023 NBA Draft Combine spot shooting results.", "tool": "get_nba_draft_combine_spot_shooting"},
        {"name": "Draft Combine Drills Test", "query": "Show me the 2023 NBA Draft Combine drills.", "tool": "get_nba_draft_combine_drills"},

        # Game Tools
        {"name": "Game Boxscore Matchups Test", "query": "Give me the box score matchups for game ID 0022300001.", "tool": "get_nba_game_boxscore_matchups"},
        {"name": "Game Boxscore Traditional Test", "query": "Give me the traditional box score for game ID 0022300001.", "tool": "get_nba_boxscore_traditional"},
        {"name": "Game Boxscore Advanced Test", "query": "Give me the advanced box score for game ID 0022300001.", "tool": "get_nba_boxscore_advanced"},
        {"name": "Game Boxscore Four Factors Test", "query": "Give me the four factors box score for game ID 0022300001.", "tool": "get_nba_boxscore_four_factors"},
        {"name": "Game Boxscore Usage Test", "query": "Give me the usage box score for game ID 0022300001.", "tool": "get_nba_boxscore_usage"},
        {"name": "Game Boxscore Defensive Test", "query": "Give me the defensive box score for game ID 0022300001.", "tool": "get_nba_boxscore_defensive"},
        {"name": "Game Boxscore Summary Test", "query": "Give me the summary box score for game ID 0022300001.", "tool": "get_nba_boxscore_summary"},
        {"name": "Game Boxscore Misc Test", "query": "Give me the miscellaneous box score for game ID 0022300001.", "tool": "get_nba_boxscore_misc"},
        {"name": "Game Play By Play Test", "query": "Show me the play-by-play for game ID 0022300001.", "tool": "get_nba_play_by_play"},
        {"name": "Win Probability PBP Test", "query": "Show me the win probability for game ID 0022300001.", "tool": "get_win_probability_pbp"},
        {"name": "Game Rotation Test", "query": "Show me the game rotation for game ID 0022300001.", "tool": "get_nba_game_rotation"},
        {"name": "Hustle Stats Boxscore Test", "query": "Show me the hustle stats boxscore for game ID 0022300001.", "tool": "get_nba_hustle_stats_boxscore"},
        {"name": "Fanduel Player Infographic Test", "query": "Show me the Fanduel player infographic for LeBron James for game ID 0022300001.", "tool": "get_nba_fanduel_player_infographic"},
        {"name": "League Games Test", "query": "List all NBA games on 2023-12-25.", "tool": "get_nba_league_games"},
        {"name": "Boxscore Player Track Test", "query": "Show me the player tracking box score for game ID 0022300001.", "tool": "get_nba_boxscore_player_track"},
        {"name": "Boxscore Scoring Test", "query": "Show me the scoring box score for game ID 0022300001.", "tool": "get_nba_boxscore_scoring"},
        {"name": "Boxscore Hustle Test", "query": "Show me the hustle box score for game ID 0022300001.", "tool": "get_nba_boxscore_hustle"},
        {"name": "Scoreboard Data Test", "query": "Show me the scoreboard data for 2023-12-25.", "tool": "get_nba_scoreboard_data"},

        # League Tools
        {"name": "All Time NBA Leaders Test", "query": "Who are the all-time NBA leaders in points?", "tool": "get_all_time_nba_leaders"},
        {"name": "League Wide Shot Chart Test", "query": "Show me the league wide shot chart for the 2023-24 season.", "tool": "get_league_wide_shot_chart"},
        {"name": "Homepage Leaders Test", "query": "Show me the NBA homepage leaders.", "tool": "get_nba_homepage_leaders"},
        {"name": "Homepage V2 Data Test", "query": "Show me the NBA homepage v2 data.", "tool": "get_nba_homepage_v2_data"},
        {"name": "IST Standings Test", "query": "What are the current NBA in-season tournament standings?", "tool": "get_nba_ist_standings"},
        {"name": "Leaders Tiles Test", "query": "Show me the NBA leaders tiles.", "tool": "get_nba_leaders_tiles"},
        {"name": "Assist Leaders Test", "query": "Who are the NBA assist leaders for the 2023-24 season?", "tool": "get_nba_assist_leaders"},
        {"name": "League Player Bio Stats Test", "query": "Show me league player bio stats for the 2023-24 season.", "tool": "get_nba_league_player_bio_stats"},
        {"name": "League Player Tracking Shot Stats Test", "query": "Show me league player tracking shot stats for the 2023-24 season.", "tool": "get_nba_league_player_tracking_shot_stats"},
        {"name": "League Player Clutch Stats Test", "query": "Show me league player clutch stats for the 2023-24 season.", "tool": "get_nba_league_player_clutch_stats"},
        {"name": "League Game Log Test", "query": "Show me the league game log for the 2023-24 season.", "tool": "get_nba_league_game_log"},
        {"name": "League Hustle Stats Team Test", "query": "Show me league hustle stats for teams for the 2023-24 season.", "tool": "get_league_hustle_stats_team"},
        {"name": "League Lineups Test", "query": "Show me league lineups for the 2023-24 season.", "tool": "get_nba_league_lineups"},
        {"name": "League Standings Test", "query": "What are the current NBA standings for the 2024-25 season?", "tool": "get_nba_league_standings"},
        {"name": "Odds Data Test", "query": "Show me NBA odds data.", "tool": "get_nba_odds_data"},
        {"name": "League Season Matchups Test", "query": "Show me league season matchups for the 2023-24 season.", "tool": "get_nba_league_season_matchups"},
        {"name": "Matchups Rollup Test", "query": "Show me matchups rollup data for the 2023-24 season.", "tool": "get_nba_matchups_rollup"},
        {"name": "Live Scoreboard Test", "query": "Show me the live NBA scoreboard.", "tool": "get_nba_live_scoreboard"},
        {"name": "League Lineup Visualization Test", "query": "Show me league lineup visualization for the 2023-24 season.", "tool": "get_league_lineup_visualization"},
        {"name": "League Player Stats Test", "query": "Show me league player stats for the 2023-24 season.", "tool": "get_nba_league_player_stats"},
        {"name": "League Player Shot Locations Test", "query": "Show me league player shot locations for the 2023-24 season.", "tool": "get_league_player_shot_locations"},
        {"name": "Schedule League V2 Int Test", "query": "Show me the NBA schedule for the 2023-24 season.", "tool": "get_nba_schedule_league_v2_int"},
        {"name": "League Wide Shot Chart Test", "query": "Show me the league wide shot chart for the 2023-24 season.", "tool": "get_nba_league_wide_shot_chart"},
        {"name": "Playoff Picture Test", "query": "Show me the NBA playoff picture for the 2023-24 season.", "tool": "get_nba_playoff_picture"},
        {"name": "Common Playoff Series Test", "query": "Show me the playoff series for the 2023-24 season.", "tool": "get_common_playoff_series"},
    ]

    output_file = "test_results.txt"
    with open(output_file, "w", encoding="utf-8") as f, redirect_stdout(f):
        # Also print to console
        class Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, obj):
                for file in self.files:
                    file.write(obj)
                    file.flush()
            def flush(self):
                for file in self.files:
                    file.flush()
        tee = Tee(f, sys.__stdout__)
        with redirect_stdout(tee):
            for case in test_cases:
                test_results.append(run_agent_test(
                    case["name"],
                    case["query"],
                    expected_tool_name=case["tool"]
                ))

            # Test Case for Direct Answer (no tool needed)
            test_results.append(run_agent_test(
                "Direct Answer Test",
                "Hello, how are you today?",
                expected_tool_name=None,
                expected_final_answer_substring="Hello! I'm functioning as an AI assistant"
            ))

            print("\n--- Overall Test Results ---")
            if all(test_results):
                print("All tests PASSED!")
            else:
                print("Some tests FAILED. Review the logs above for details.")