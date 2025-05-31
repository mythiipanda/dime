import os
import sys
import json
from typing import Dict, Any, List

# Add project root to sys.path for imports
_current_script_path = os.path.abspath(__file__)
_langgraph_agent_dir = os.path.dirname(_current_script_path)
_backend_dir = os.path.dirname(_langgraph_agent_dir)
_project_root_dir = os.path.dirname(_backend_dir)

if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

from backend.langgraph_agent.graph import app
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
        for event in app.stream(inputs, stream_mode="updates"):
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

    # Test Case 1: Player Shot Chart
    test_results.append(run_agent_test(
        "Player Shot Chart Test",
        "Show me LeBron James' shot chart for the 2022-23 season, regular season.",
        expected_tool_name="get_player_shot_chart"
    ))

    # Test Case 2: Team Lineups
    test_results.append(run_agent_test(
        "Team Lineups Test",
        "What were the most effective 5-man lineups for the Golden State Warriors in the 2023-24 playoffs?",
        expected_tool_name="get_team_lineups"
    ))

    # Test Case 3: Search Players
    test_results.append(run_agent_test(
        "Player Search Test",
        "Search for players named 'Jordan'.",
        expected_tool_name="search_nba_players"
    ))

    # Test Case 4: Synergy Play Types
    test_results.append(run_agent_test(
        "Synergy Play Types Test",
        "What are the top 5 isolation play types for Stephen Curry in the 2023-24 season?",
        expected_tool_name="get_synergy_play_types"
    ))

    # Test Case 5: Player Contract
    test_results.append(run_agent_test(
        "Player Contract Test",
        "What is LeBron James' contract details?",
        expected_tool_name="get_nba_player_contract"
    ))

    # Test Case 6: Draft Combine Stats
    test_results.append(run_agent_test(
        "Draft Combine Stats Test",
        "Show me the 2023 NBA Draft Combine stats.",
        expected_tool_name="get_nba_draft_combine_stats"
    ))

    # Test Case 7: Game Boxscore Traditional
    test_results.append(run_agent_test(
        "Game Boxscore Traditional Test",
        "Give me the traditional box score for game ID 0022300001.",
        expected_tool_name="get_nba_boxscore_traditional"
    ))

    # Test Case 8: League Standings
    test_results.append(run_agent_test(
        "League Standings Test",
        "What are the current NBA standings for the 2024-25 season?",
        expected_tool_name="get_nba_league_standings"
    ))

    # Test Case 9: Direct Answer (no tool needed)
    test_results.append(run_agent_test(
        "Direct Answer Test",
        "Hello, how are you today?",
        expected_tool_name=None,
        expected_final_answer_substring="Hello! I'm functioning as an AI assistant"
    ))

    # New Test Cases for Player Tools
    test_results.append(run_agent_test(
        "Player Aggregate Stats Test",
        "Give me aggregated stats for LeBron James for the 2023-24 season.",
        expected_tool_name="get_player_aggregate_stats"
    ))
    test_results.append(run_agent_test(
        "Player Career By College Stats Test",
        "Show me career stats for players from Duke.",
        expected_tool_name="get_player_career_by_college_stats"
    ))
    test_results.append(run_agent_test(
        "Player Career By College Rollup Stats Test",
        "Show me college rollup stats for all players.",
        expected_tool_name="get_player_career_by_college_rollup_stats"
    ))
    test_results.append(run_agent_test(
        "Player Career Stats Test",
        "What are Stephen Curry's career stats?",
        expected_tool_name="get_player_career_stats"
    ))
    test_results.append(run_agent_test(
        "Player Awards Test",
        "What awards has Michael Jordan won?",
        expected_tool_name="get_player_awards"
    ))
    test_results.append(run_agent_test(
        "Player Clutch Stats Test",
        "Show me LeBron James' clutch stats for the 2022-23 season.",
        expected_tool_name="get_player_clutch_stats"
    ))
    test_results.append(run_agent_test(
        "Player Info Test",
        "Tell me about Kevin Durant.",
        expected_tool_name="get_player_info"
    ))
    test_results.append(run_agent_test(
        "Player Compare Stats Test",
        "Compare LeBron James (ID 2544) and Stephen Curry (ID 201939) for the 2023-24 season.",
        expected_tool_name="get_player_compare_stats"
    ))
    test_results.append(run_agent_test(
        "Player Dashboard By Year Over Year Test",
        "Show me LeBron James' year over year dashboard stats for the 2023-24 season.",
        expected_tool_name="get_player_dashboard_by_year_over_year"
    ))
    test_results.append(run_agent_test(
        "Player Dashboard Game Splits Test",
        "What are Nikola Jokic's game splits for the 2023-24 regular season?",
        expected_tool_name="get_player_dashboard_game_splits"
    ))
    test_results.append(run_agent_test(
        "Player Dashboard General Splits Test",
        "Show me Giannis Antetokounmpo's general splits for the 2023-24 regular season.",
        expected_tool_name="get_player_dashboard_general_splits"
    ))
    test_results.append(run_agent_test(
        "Player Dashboard Last N Games Test",
        "What are Luka Doncic's stats for his last 10 games in the 2023-24 season?",
        expected_tool_name="get_player_dashboard_last_n_games"
    ))
    test_results.append(run_agent_test(
        "Player Dashboard Shooting Splits Test",
        "Show me Jayson Tatum's shooting splits for the 2023-24 regular season.",
        expected_tool_name="get_player_dashboard_shooting_splits"
    ))
    test_results.append(run_agent_test(
        "Player Profile Test",
        "Give me the profile for Joel Embiid.",
        expected_tool_name="get_player_profile"
    ))
    test_results.append(run_agent_test(
        "Player Defense Stats Test",
        "What are Rudy Gobert's defensive stats for the 2023-24 season?",
        expected_tool_name="get_player_defense_stats"
    ))
    test_results.append(run_agent_test(
        "Player Hustle Stats Test",
        "Show me hustle stats for the 2023-24 season.",
        expected_tool_name="get_player_hustle_stats"
    ))
    test_results.append(run_agent_test(
        "Player Estimated Metrics Test",
        "What are the estimated metrics for the 2023-24 season?",
        expected_tool_name="get_player_estimated_metrics"
    ))
    test_results.append(run_agent_test(
        "Player Fantasy Profile Test",
        "Show me LeBron James' fantasy profile for the 2023-24 season.",
        expected_tool_name="get_player_fantasy_profile"
    ))
    test_results.append(run_agent_test(
        "Player Fantasy Profile Bar Graph Test",
        "Give me LeBron James' fantasy profile bar graph data for the 2023-24 season.",
        expected_tool_name="get_player_fantasy_profile_bar_graph"
    ))
    test_results.append(run_agent_test(
        "Player Game Logs Test",
        "Show me game logs for Damian Lillard for the 2023-24 season.",
        expected_tool_name="get_player_game_logs"
    ))
    test_results.append(run_agent_test(
        "Player Game Streak Finder Test",
        "Find game streaks for Stephen Curry.",
        expected_tool_name="get_player_game_streak_finder"
    ))
    test_results.append(run_agent_test(
        "Player Index Test",
        "List all active players for the 2023-24 season.",
        expected_tool_name="get_player_index"
    ))
    test_results.append(run_agent_test(
        "Player Listings Test",
        "List all players for the 2023-24 season.",
        expected_tool_name="get_player_listings"
    ))
    test_results.append(run_agent_test(
        "Player Passing Stats Test",
        "Show me Nikola Jokic's passing stats for the 2023-24 season.",
        expected_tool_name="get_player_passing_stats"
    ))
    test_results.append(run_agent_test(
        "Player Rebounding Stats Test",
        "What are Domantas Sabonis' rebounding stats for the 2023-24 season?",
        expected_tool_name="get_player_rebounding_stats"
    ))
    test_results.append(run_agent_test(
        "Player Shots Tracking Stats Test",
        "Show me Kevin Durant's shots tracking stats for the 2023-24 season.",
        expected_tool_name="get_player_shots_tracking_stats"
    ))
    test_results.append(run_agent_test(
        "Player Vs Player Stats Test",
        "Compare LeBron James (ID 2544) and Michael Jordan (ID 893) head-to-head for the 1997-98 season.",
        expected_tool_name="get_player_vs_player_stats"
    ))

    # New Test Cases for League Tools
    test_results.append(run_agent_test(
        "Common Playoff Series Test",
        "Show me the playoff series for the 2023-24 season.",
        expected_tool_name="get_common_playoff_series"
    ))

    print("\n--- Overall Test Results ---")
    if all(test_results):
        print("All tests PASSED!")
    else:
        print("Some tests FAILED. Review the logs above for details.")