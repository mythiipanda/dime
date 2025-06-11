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
        print(f"  ERROR: An exception occurred during test execution: {e}")
    
    print("Test completed. Check logs above for details.")
    return True

if __name__ == "__main__":
    test_results = []

    test_cases = [
        # Player Tools
        {"name": "Player Shot Chart Test", "query": "Show me LeBron James' shot chart for the 2022-23 season, regular season.", "tool": "get_player_shot_chart"},
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
                expected_final_answer_substring="How can I assist you with NBA-related information or analysis today?"
            ))

            print("\n--- Overall Test Results ---")
            if all(test_results):
                print("All tests PASSED!")
            else:
                print("Some tests FAILED. Review the logs above for details.")