import os
import sys
import json
from typing import Dict, Any, List
import builtins
from contextlib import redirect_stdout

from langgraph_agent.graph import app
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

def run_agent_test(test_name: str, input_query: str, expected_node_sequence: List[str] = None, expected_final_answer_substring: str = None):
    """
    Runs a single test case for the Langgraph agent and prints detailed output.
    Verifies node execution sequence and final answer content.
    """
    print(f"\n--- Running Test: {test_name} ---")
    print(f"Input Query: {input_query}")

    inputs = {
        "input_query": input_query,
        "chat_history": []
    }

    final_graph_state: Dict[str, Any] = {}
    executed_nodes = []
    
    try:
        config = {"configurable": {"thread_id": f"test_thread_{test_name.replace(' ', '_')}", "checkpoint_ns": "test_ns"}}
        for event in app.stream(inputs, config=config, stream_mode="updates"):
            node_name, node_output_state = list(event.items())[0]
            executed_nodes.append(node_name)
            print(f"\nNODE EXECUTED: {node_name}")
            
            if node_output_state and 'messages' in node_output_state and node_output_state['messages']:
                last_message = node_output_state['messages'][-1]
                print(f"  LAST MESSAGE: {last_message}")

                if isinstance(last_message, AIMessage) and last_message.tool_calls:
                    print(f"  TOOL CALLS DETECTED: {last_message.tool_calls}")
                elif isinstance(last_message, ToolMessage):
                    print(f"  TOOL OUTPUT: {last_message.content}")
                
                if node_output_state.get('final_answer'):
                    print(f"  FINAL ANSWER: {node_output_state['final_answer']}")
                    if expected_final_answer_substring and expected_final_answer_substring.lower() in node_output_state['final_answer'].lower():
                        print(f"  SUCCESS: Final answer contains expected substring: '{expected_final_answer_substring}'")
                    elif expected_final_answer_substring:
                        print(f"  FAILURE: Final answer does NOT contain expected substring: '{expected_final_answer_substring}'")

            final_graph_state.update(node_output_state)
    except Exception as e:
        print(f"  ERROR: An exception occurred during test execution: {e}")
        return False # Indicate test failure on exception
    
    # Verify node sequence
    if expected_node_sequence:
        sequence_match = True
        for i, expected_node in enumerate(expected_node_sequence):
            if i >= len(executed_nodes) or executed_nodes[i] != expected_node:
                print(f"  FAILURE: Expected node sequence mismatch at index {i}.")
                print(f"    Expected: {expected_node}, Got: {executed_nodes[i] if i < len(executed_nodes) else 'N/A'}")
                sequence_match = False
                break
        if sequence_match and len(executed_nodes) >= len(expected_node_sequence):
            print(f"  SUCCESS: Expected node sequence matched: {expected_node_sequence}")
        else:
            print(f"  FAILURE: Expected node sequence not fully matched or too short. Expected: {expected_node_sequence}, Actual: {executed_nodes}")
            return False # Indicate test failure on sequence mismatch

    print("Test completed. Check logs above for details.")
    return True

if __name__ == "__main__":
    test_results = []

    test_cases = [
        # Test Case 1: Data Retrieval -> Analytics -> Presentation (Tool Call in Data Retrieval)
        {
            "name": "Complex Player Analysis with Visualization",
            "query": "Compare LeBron James' 2022-23 season stats with Michael Jordan's 1997-98 season stats, focusing on points, assists, and rebounds. Then visualize their per-game averages for these stats.",
            "expected_node_sequence": ["entry_node", "data_retrieval_agent", "actual_tool_node", "analytics_agent", "actual_tool_node", "presentation_agent", "actual_tool_node", "presentation_agent", "END"],
            "expected_final_answer_substring": "comparison and visualization" # Expecting a final answer after visualization
        },
        # Test Case 2: Direct Answer (no tools needed, should go straight to presentation)
        {
            "name": "Direct Answer Test",
            "query": "Hello, how are you today?",
            "expected_node_sequence": ["entry_node", "data_retrieval_agent", "presentation_agent", "END"],
            "expected_final_answer_substring": "How can I assist you with NBA-related information or analysis today?"
        }
    ]

    output_file = "test_results.txt"
    with open(output_file, "w", encoding="utf-8") as f, redirect_stdout(f):
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
                    expected_node_sequence=case.get("expected_node_sequence"),
                    expected_final_answer_substring=case.get("expected_final_answer_substring")
                ))

            print("\n--- Overall Test Results ---")
            if all(test_results):
                print("All tests PASSED!")
            else:
                print("Some tests FAILED. Review the logs above for details.")