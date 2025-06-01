# This file will implement the logic for individual nodes in the Langgraph agent. 

from langgraph_agent.state import AgentState
from langgraph_agent.tool_manager import all_tools # Import all_tools for the LLM
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI # For Gemini
from config import GEMINI_API_KEY # Import API key
import json
import datetime # Added datetime
from langgraph_agent.prompt import get_nba_analyst_prompt # Added import for the new prompt function

# Initialize Gemini LLM
# Ensure GEMINI_API_KEY is set in your .env file
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GEMINI_API_KEY, convert_system_message_to_human=True)

# Bind tools to the LLM. This allows the LLM to be aware of the tools and their schemas.
# The .bind_tools() method is standard in Langchain for models that support tool calling.
llm_with_tools = llm.bind_tools(all_tools)

# Node definitions

def entry_node(state: AgentState) -> dict:
    """Initial node. Returns the initial HumanMessage."""
    print("---ENTERING ENTRY NODE---")
    # input_query is from the initial state
    # streaming_output is handled by returning it in the dict
    user_input = state['input_query']
    return {
        "messages": [HumanMessage(content=user_input)], 
        "streaming_output": [f"User: {user_input}"],
        "current_step": 1,
        "agent_scratchpad": [],
        "tool_outputs": [] # Initialize if needed elsewhere, ToolNode uses messages for ToolMessage
    }

def llm_node(state: AgentState) -> dict:
    """
    Invokes the Gemini LLM with the current message history (prepended with a system prompt) and bound tools.
    The LLM will decide whether to call a tool or respond directly.
    Returns the AIMessage from the LLM.
    """
    print("---ENTERING LLM NODE (Using Gemini)---")
    current_messages_from_state = state['messages']
    streaming_log = []

    # --- Prepare dynamic system prompt ---
    # TODO: Make current_season dynamic (e.g., from config or a dedicated tool/input)
    current_season = "2024-25" 
    current_date_str = datetime.date.today().strftime("%Y-%m-%d")
    system_prompt_content = get_nba_analyst_prompt(current_season=current_season, current_date=current_date_str)
    system_message = SystemMessage(content=system_prompt_content)
    
    # Prepend system message to the history for this LLM call
    messages_for_llm = [system_message] + current_messages_from_state
    # --- End of system prompt preparation ---

    print(f"LLM Input Messages (with system prompt): {messages_for_llm}")
    streaming_log.append(f"LLM invoking with messages (incl. system prompt): {json.dumps([m.dict() for m in messages_for_llm], indent=2)[:300]}...")

    # Invoke the LLM with the message history and tools
    # Langchain's bind_tools and the model itself handle the tool_choice and tool_calling protocol.
    try:
        ai_response_message = llm_with_tools.invoke(messages_for_llm)
        
        # --- Start of new diagnostic logging ---
        print(f"RAW LLM Response Object: {ai_response_message!r}") # Print the repr of the object
        if hasattr(ai_response_message, 'response_metadata') and ai_response_message.response_metadata:
            print(f"LLM Response Metadata: {ai_response_message.response_metadata}")
            # Look for common error patterns in metadata (actual keys depend on Gemini API structure via Langchain)
            if ai_response_message.response_metadata.get('error'):
                print(f"ERROR in LLM Response Metadata: {ai_response_message.response_metadata['error']}")
            if ai_response_message.response_metadata.get('block_reason'):
                 print(f"CONTENT BLOCKED by Gemini. Reason: {ai_response_message.response_metadata.get('block_reason')}, Safety Ratings: {ai_response_message.response_metadata.get('safety_ratings')}")

        # --- End of new diagnostic logging ---

        # ai_response_message will be an AIMessage.
        # If the LLM decided to call a tool, ai_response_message.tool_calls will be populated.
        # If it decided to respond directly, ai_response_message.content will have the response.
        
        log_content = ai_response_message.content if ai_response_message.content else "[LLM decided to use a tool]"
        if ai_response_message.tool_calls:
            log_content += f" Tool calls: {ai_response_message.tool_calls}"
        
        print(f"LLM Output: {log_content}")
        streaming_log.append(f"LLM Output: {log_content}")

    except Exception as e:
        error_msg = f"Error invoking LLM: {e}"
        print(f"LLM NODE ERROR: {error_msg}")
        streaming_log.append(error_msg)
        # Create a fallback AIMessage indicating the error
        ai_response_message = AIMessage(content=f"Sorry, I encountered an error trying to process your request: {e}")

    return {
        "messages": [ai_response_message], # Langgraph will add this to existing messages
        "streaming_output": streaming_log,
        "agent_scratchpad": streaming_log, # For now, use streaming_log for scratchpad
        "current_step": state.get('current_step', 0) + 1,
        "system_prompt_used": system_prompt_content # Adding this for debugging/verification
    }

# My custom tool_node is no longer needed if using langgraph.prebuilt.ToolNode directly in the graph.
# The ToolNode will handle execution and add a ToolMessage to state['messages'].

def response_node(state: AgentState) -> dict:
    """
    Formulates a final response. This node is typically reached when the LLM decides not to call any more tools.
    Returns the final_answer.
    """
    print("---ENTERING RESPONSE NODE---")
    current_messages = state['messages'] # Accumulated messages
    final_answer_content = "Response Node: Default final answer."
    streaming_log = []
    
    last_ai_message = current_messages[-1] if current_messages and isinstance(current_messages[-1], AIMessage) else None
    
    if last_ai_message and not last_ai_message.tool_calls and last_ai_message.content:
        final_answer_content = last_ai_message.content
    elif state.get('error_message'):
        final_answer_content = f"Error encountered: {state['error_message']}"
        streaming_log.append(final_answer_content)
    else:
        warning_msg = f"Response Node: Could not determine a final answer from the last LLM message. Last AI message: {last_ai_message}"
        if last_ai_message and last_ai_message.tool_calls:
            warning_msg += f" (It contained tool calls: {last_ai_message.tool_calls}) - this might indicate a routing issue if response_node was reached directly."
        print(warning_msg)
        streaming_log.append(warning_msg)
        final_answer_content = last_ai_message.content if last_ai_message and last_ai_message.content else "No conclusive text response generated by LLM."

    final_log_message = f"Final Answer: {final_answer_content}"
    streaming_log.append(final_log_message)

    return {
        "final_answer": final_answer_content,
        "streaming_output": streaming_log,
        "current_step": state.get('current_step', 0) + 1
    } 