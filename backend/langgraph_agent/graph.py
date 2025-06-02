# This file will define the main Langgraph StateGraph for the NBA agent. 

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition # Import ToolNode and tools_condition
from langgraph_agent.state import AgentState
from langgraph_agent.nodes import entry_node, llm_node, response_node # tool_node removed from here
from langgraph_agent.tool_manager import all_tools # Import the list of actual tools
from langgraph.pregel import RetryPolicy

# Define the graph
workflow = StateGraph(AgentState)

# Initialize the ToolNode with our tools
actual_tool_node = ToolNode(all_tools)

# Add nodes
workflow.add_node("entry_node", entry_node, retry=RetryPolicy())
workflow.add_node("llm_node", llm_node, retry=RetryPolicy())             # Node to decide on action (e.g., call tool or respond)
workflow.add_node("actual_tool_node", actual_tool_node, retry=RetryPolicy()) # The prebuilt ToolNode for executing tools
workflow.add_node("response_node", response_node, retry=RetryPolicy())   # Node to formulate final response

# Set the entry point
workflow.set_entry_point("entry_node")

# Define edges and conditional routing
workflow.add_edge("entry_node", "llm_node")

# Conditional edge after llm_node:
# Use the prebuilt tools_condition. It checks the last AIMessage in state['messages']
# for tool_calls. If present, it routes to the node specified for True (our actual_tool_node).
# Otherwise, it routes to the node for False (our response_node, or eventually another LLM call).
workflow.add_conditional_edges(
    "llm_node",
    tools_condition, 
    {
        "tools": "actual_tool_node",  # Route to tool node if tools_condition returns "tools"
        "__end__": "response_node"    # Route to response node if tools_condition returns "__end__"
        # We might need to handle a "continue" case later if the LLM outputs AIMessage with no content and no tool_calls
    }
)

# Edge after actual_tool_node:
# The ToolNode adds a ToolMessage to state['messages'] with the tool's output.
# This output should then be processed by an LLM.
# So, route back to llm_node.
workflow.add_edge("actual_tool_node", "llm_node") 

# Edge after response_node (final step)
workflow.add_edge("response_node", END)

# Compile the graph
app = workflow.compile()

# Optional: For testing or direct invocation from Python
if __name__ == "__main__":
    # More complex query for testing
    inputs = {
        "input_query": "Compare Michael Jordan\'s 1990-91 season stats with LeBron James\' 2012-13 season. Who was more efficient and had a better overall impact based on PER and Win Shares?", 
        "chat_history": []
    } 
    print("INVOKING LANGGRAPH APP (from graph.py direct test with ToolNode)...")
    print("---STREAMING OUTPUT START---")
    
    final_graph_state: AgentState = None
    system_prompt_printed = False
    for event in app.stream(inputs, stream_mode="updates"):
        node_name, node_output_state = list(event.items())[0]
        print(f"NODE EXECUTED: {node_name}")
        
        # Print system prompt once when llm_node executes
        if node_name == "llm_node" and node_output_state.get("system_prompt_used") and not system_prompt_printed:
            print("\n--- SYSTEM PROMPT USED BY LLM NODE ---")
            print(node_output_state["system_prompt_used"])
            print("-------------------------------------\n")
            system_prompt_printed = True

        if node_output_state and 'messages' in node_output_state and node_output_state['messages']:
            print(f"  MESSAGES (from {node_name}, last one): {node_output_state['messages'][-1]}")

        if node_output_state and 'streaming_output' in node_output_state and node_output_state['streaming_output']:
            print(f"  STREAM (from {node_name}): {node_output_state['streaming_output'][-1]}")
            
        if node_output_state and 'final_answer' in node_output_state and node_output_state['final_answer']:
            print(f"  INTERIM/FINAL ANSWER (from {node_name}): {node_output_state['final_answer']}")
        
        if node_name == END:
            print("  END node reached. Graph execution complete.")
        
        final_graph_state = node_output_state
                
    print("---STREAMING OUTPUT END---")

    if final_graph_state:
        print("\n---FINAL GRAPH STATE INSPECTION (from graph.py direct test with ToolNode)---")
        print(f"Input Query: {final_graph_state.get('input_query')}")
        # print(f"Messages: {final_graph_state.get('messages')}")
        print(f"Final Answer: {final_graph_state.get('final_answer')}")
        print(f"Tool Outputs (from AgentState, if any manually added): {final_graph_state.get('tool_outputs')}")
        print(f"Final Step Count: {final_graph_state.get('current_step')}")
    else:
        print("\nNo final graph state was captured (from graph.py direct test with ToolNode).") 