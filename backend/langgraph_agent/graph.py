# This file will define the main Langgraph StateGraph for the NBA agent. 

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition # Import ToolNode and tools_condition
from langgraph_agent.state import AgentState
# Import node functions from the renamed node_functions module
from langgraph_agent.node_functions import entry_node, llm_service, prompt_service
from langgraph_agent.tool_manager import all_tools # Import the list of actual tools
from langgraph.pregel import RetryPolicy

# Import memory manager for checkpointer
from langgraph_agent.memory import get_memory_manager

# Import the new specialized agents
from langgraph_agent.agents.data_retrieval_agent import DataRetrievalAgent
from langgraph_agent.agents.analytics_agent import AnalyticsAgent
from langgraph_agent.agents.presentation_agent import PresentationAgent

# Define the graph
workflow = StateGraph(AgentState)

# Initialize the ToolNode with our tools
actual_tool_node = ToolNode(all_tools)

# Initialize specialized agent instances
data_retrieval_agent = DataRetrievalAgent(llm_provider=llm_service.bind_tools(all_tools))
analytics_agent = AnalyticsAgent(llm_provider=llm_service.bind_tools(all_tools))
presentation_agent = PresentationAgent(llm_provider=llm_service.bind_tools(all_tools))

# Add nodes for each agent and the tool executor
workflow.add_node("entry_node", entry_node, retry=RetryPolicy())
workflow.add_node("data_retrieval_agent", data_retrieval_agent.execute, retry=RetryPolicy())
workflow.add_node("actual_tool_node", actual_tool_node, retry=RetryPolicy())
workflow.add_node("analytics_agent", analytics_agent.execute, retry=RetryPolicy())
workflow.add_node("presentation_agent", presentation_agent.execute, retry=RetryPolicy())

# Set the entry point
workflow.set_entry_point("entry_node")

def route_after_data_retrieval(state):
    """Route after data_retrieval_agent based on tool calls and analysis needs."""
    if state.get("should_call_tool"):
        # Set which agent called the tool for proper routing back
        state["calling_agent"] = "data_retrieval_agent"
        return "tools"
    else:
        # Check if the response indicates no data retrieval needed (simple query)
        last_message = state.get("messages", [])[-1] if state.get("messages") else None
        if last_message and hasattr(last_message, 'content'):
            # If the response is conversational and doesn't mention data gathering
            content_lower = last_message.content.lower()
            if any(phrase in content_lower for phrase in ['hello', 'how are you', 'i am', 'thank you']):
                return "presentation_agent"
        return "analytics_agent"

def route_after_analytics(state):
    """Route after analytics_agent based on tool calls."""
    if state.get("should_call_tool"):
        # Set which agent called the tool for proper routing back
        state["calling_agent"] = "analytics_agent"
        return "tools"
    else:
        return "presentation_agent"

def route_after_presentation(state):
    """Route after presentation_agent based on tool calls."""
    if state.get("should_call_tool"):
        # Set which agent called the tool for proper routing back
        state["calling_agent"] = "presentation_agent"
        return "tools"
    else:
        return "__end__"

def route_after_tools(state):
    """Route after tool execution back to the agent that called the tool."""
    calling_agent = state.get("calling_agent", "analytics_agent")  # Default fallback
    
    # Clear the calling_agent to avoid confusion in subsequent calls
    if "calling_agent" in state:
        del state["calling_agent"]
    
    return calling_agent

# Define edges and conditional routing
# From entry_node, always go to data_retrieval_agent to start the process
workflow.add_edge("entry_node", "data_retrieval_agent")

# Conditional routing after data_retrieval_agent
workflow.add_conditional_edges(
    "data_retrieval_agent",
    route_after_data_retrieval,
    {
        "tools": "actual_tool_node",
        "analytics_agent": "analytics_agent",
        "presentation_agent": "presentation_agent",
    }
)

# Smart routing after tool execution back to the calling agent
workflow.add_conditional_edges(
    "actual_tool_node",
    route_after_tools,
    {
        "data_retrieval_agent": "analytics_agent",  # After data retrieval tools, go to analytics
        "analytics_agent": "analytics_agent",
        "presentation_agent": "presentation_agent",
    }
)

# Conditional routing after analytics_agent
workflow.add_conditional_edges(
    "analytics_agent",
    route_after_analytics,
    {
        "tools": "actual_tool_node",
        "presentation_agent": "presentation_agent",
    }
)

# Conditional routing after presentation_agent
workflow.add_conditional_edges(
    "presentation_agent",
    route_after_presentation,
    {
        "tools": "actual_tool_node",
        "__end__": END,
    }
)

# Get memory manager and compile graph with checkpointer for multi-turn conversations
memory_manager = get_memory_manager()
app = workflow.compile(checkpointer=memory_manager.checkpointer)

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