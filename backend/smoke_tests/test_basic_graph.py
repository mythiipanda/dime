import sys
import os
import json # For pretty printing dicts if needed

# Adjust the Python path to include the project root
_current_script_dir = os.path.dirname(os.path.abspath(__file__))
# When script is in backend/smoke_tests, project_root_dir is two levels up.
_project_root_dir = os.path.dirname(os.path.dirname(_current_script_dir)) 
if _project_root_dir not in sys.path:
    sys.path.insert(0, _project_root_dir)

from langgraph_agent.graph import app  # Import the compiled graph app
from langgraph_agent.state import AgentState # Import AgentState for type checking if needed
from langgraph.graph import END
def run_basic_graph_test():
    """Tests the basic Langgraph graph with Gemini LLM and tool calling."""
    # inputs = {"input_query": "Tell me a joke about basketball.", "chat_history": []} # Previous input
    inputs = {"input_query": "Get player info for LeBron James", "chat_history": []} # New input to trigger tool use
    
    print(f"INVOKING LANGGRAPH APP (from {__file__})...") # Use __file__ for dynamic path
    print(f"INPUT QUERY: {inputs['input_query']}")
    print("---STREAMING OUTPUT START---")
    
    final_graph_state_dict: dict = None # Store the raw dict output for inspection

    for event in app.stream(inputs, stream_mode="updates"):
        # event is a dictionary where keys are node names and values are the output state (dict) from that node
        node_name, node_output_state_dict = list(event.items())[0]
        print(f"NODE EXECUTED: {node_name}")
        
        # Print messages if present in the node's output state
        if node_output_state_dict.get('messages'):
            # messages are already BaseMessage objects, handle their representation
            try:
                # Attempt to print a more readable form of the last message
                last_msg = node_output_state_dict['messages'][-1]
                if hasattr(last_msg, 'model_dump'): # Langchain messages often have a .model_dump() method
                    print(f"  MESSAGES (from {node_name}, last one): {json.dumps(last_msg.model_dump(), indent=2)}")
                else:
                    print(f"  MESSAGES (from {node_name}, last one): {last_msg}") # Fallback to default repr
            except Exception as e:
                print(f"  MESSAGES (from {node_name}, full list): {node_output_state_dict['messages']} (Error printing last: {e})")

        # Print streaming_output if present
        if node_output_state_dict.get('streaming_output'):
            # streaming_output is a list of strings
            for stream_msg in node_output_state_dict['streaming_output']:
                print(f"  STREAM (from {node_name}): {stream_msg}")
            
        # Print final_answer if present
        if node_output_state_dict.get('final_answer') is not None:
            print(f"  FINAL_ANSWER (from {node_name}): {node_output_state_dict['final_answer']}")
        
        if node_name == END:
            print("  END node reached. Graph execution complete.")
            # The state associated with END is usually the final accumulated state of the graph.
            final_graph_state_dict = node_output_state_dict
        else:
            # Keep track of the latest state from any non-END node if END state isn't what we want
            # This might be overwritten if multiple non-END nodes update state before END is reached
            # For a sequential graph that ends, the END node state is typically the one to inspect.
            # However, for clarity in this test, we only care about the state when END is reached.
            pass
                
    print("---STREAMING OUTPUT END---")

    # If END node didn't capture the full state as expected, or for debugging, 
    # you might need to invoke and then separately get the state.
    # For now, let's assume the state from the END event is what we need.

    if final_graph_state_dict:
        print(f"\n---FINAL GRAPH STATE INSPECTION (from {__file__} - END node state)---")
        # Safely get and print common keys from AgentState
        print(f"Input Query (initial): {inputs.get('input_query')}") # Original input to the graph
        print(f"Final Answer: {final_graph_state_dict.get('final_answer')}")
        
        # Print full messages list from final state
        final_messages = final_graph_state_dict.get('messages', [])
        print("Final Messages List:")
        for i, msg in enumerate(final_messages):
            if hasattr(msg, 'model_dump'):
                print(f"  [{i}] {json.dumps(msg.model_dump(), indent=2)}")
            else:
                print(f"  [{i}] {msg}")
                
        # print(f"Streaming Output Log (final state): {final_graph_state_dict.get('streaming_output')}")
        print(f"Current Step Count (final state): {final_graph_state_dict.get('current_step')}")
    else:
        print("\nNo final graph state was captured from the END event.")

if __name__ == "__main__":
    run_basic_graph_test() 