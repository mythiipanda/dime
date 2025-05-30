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

    print("\n--- Overall Test Results ---")
    if all(test_results):
        print("All tests PASSED!")
    else:
        print("Some tests FAILED. Review the logs above for details.")