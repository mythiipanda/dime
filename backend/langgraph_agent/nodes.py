# This file will implement the logic for individual nodes in the Langgraph agent. 

from langgraph_agent.state import AgentState
from langgraph_agent.tool_manager import all_tools # Import all_tools for the LLM
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI # For Gemini
from config import GEMINI_API_KEY # Import API key
import json
import datetime # Added datetime
from langgraph_agent.prompt import get_nba_analyst_prompt # Added import for the new prompt function
from langgraph.config import get_stream_writer

# Initialize Gemini LLM with streaming enabled
# Ensure GEMINI_API_KEY is set in your .env file
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GEMINI_API_KEY,
    convert_system_message_to_human=True,
    streaming=True  # Enable streaming for token-level updates
)

# Bind tools to the LLM. This allows the LLM to be aware of the tools and their schemas.
# The .bind_tools() method is standard in Langchain for model that support tool calling.
llm_with_tools = llm.bind_tools(all_tools)

# Node definitions

def entry_node(state: AgentState) -> dict:
    """Initial node. Handles both new conversations and multi-turn interactions."""
    print("---ENTERING ENTRY NODE---")
    
    # Get stream writer for custom streaming
    try:
        writer = get_stream_writer()
        writer({"status": "starting", "step": "entry_node", "message": "Initializing NBA Analytics Agent..."})
    except Exception:
        # Fallback if streaming not available
        pass
    
    # For multi-turn conversations, we only need to add the new user message
    # The checkpointer automatically maintains the message history
    user_input = state['input_query']
    
    # Check if this is a continuation of an existing conversation
    existing_messages = state.get('messages', [])
    is_continuation = len(existing_messages) > 0
    
    if is_continuation:
        print(f"---CONTINUING CONVERSATION with {len(existing_messages)} existing messages---")
        try:
            writer = get_stream_writer()
            writer({"status": "continuing", "step": "entry_node", "message": f"Continuing conversation with new query: {user_input[:100]}..."})
        except Exception:
            pass
    else:
        print("---STARTING NEW CONVERSATION---")
        try:
            writer = get_stream_writer()
            writer({"status": "processing", "step": "entry_node", "message": f"Processing new query: {user_input[:100]}..."})
        except Exception:
            pass
    
    # Always add the new user message to the conversation
    # LangGraph's add_messages will handle appending to existing history
    new_human_message = HumanMessage(content=user_input)
    
    return {
        "messages": [new_human_message],  # This gets added to existing messages by add_messages
        "streaming_output": [f"User: {user_input}"],
        "current_step": state.get('current_step', 0) + 1,
        "agent_scratchpad": state.get('agent_scratchpad', []),
        "tool_outputs": state.get('tool_outputs', [])
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

    # Custom streaming for preparation phase
    try:
        writer = get_stream_writer()
        writer({"status": "preparing", "step": "llm_node", "message": "Preparing system prompt and context..."})
    except Exception:
        pass

    # --- Prepare dynamic system prompt ---
    # TODO: Make current_season dynamic (e.g., from config or a dedicated tool/input)
    current_season = "2024-25"
    current_date_str = datetime.date.today().strftime("%Y-%m-%d")
    system_prompt_content = get_nba_analyst_prompt(current_season=current_season, current_date=current_date_str)
    system_message = SystemMessage(content=system_prompt_content)
    
    # Prepend system message to the history for this LLM call
    messages_for_llm = [system_message] + current_messages_from_state
    # --- End of system prompt preparation ---

    try:
        writer = get_stream_writer()
        writer({"status": "invoking", "step": "llm_node", "message": f"Invoking LLM with {len(messages_for_llm)} messages..."})
    except Exception:
        pass

    print(f"LLM Input Messages (with system prompt): {messages_for_llm}")
    streaming_log.append(f"LLM invoking with messages (incl. system prompt): {json.dumps([m.dict() for m in messages_for_llm], indent=2)[:300]}...")

    # Invoke the LLM with the message history and tools
    # Langchain's bind_tools and the model itself handle the tool_choice and tool_calling protocol.
    try:
        try:
            writer = get_stream_writer()
            writer({"status": "processing", "step": "llm_node", "message": "LLM is analyzing the request..."})
        except Exception:
            pass
        
        # Add thinking indicator for better UX
        try:
            writer = get_stream_writer()
            writer({"status": "thinking", "step": "llm_node", "message": "🤔 Thinking..."})
        except Exception:
            pass
        
        # Invoke LLM with tools
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
            try:
                writer = get_stream_writer()
                writer({"status": "tool_decision", "step": "llm_node", "message": f"🔧 LLM decided to use tools: {[tc.get('name') for tc in ai_response_message.tool_calls]}"})
            except Exception:
                pass
        else:
            try:
                writer = get_stream_writer()
                writer({"status": "response_ready", "step": "llm_node", "message": "✅ LLM generated a direct response"})
            except Exception:
                pass
        
        # Add progress updates for better UX
        try:
            writer = get_stream_writer()
            writer({"status": "processing_complete", "step": "llm_node", "message": "Processing completed, preparing response..."})
        except Exception:
            pass
        
        print(f"LLM Output: {log_content}")
        streaming_log.append(f"LLM Output: {log_content}")

    except Exception as e:
        error_msg = f"Error invoking LLM: {e}"
        print(f"LLM NODE ERROR: {error_msg}")
        streaming_log.append(error_msg)
        try:
            writer = get_stream_writer()
            writer({"status": "error", "step": "llm_node", "message": f"LLM error: {str(e)}"})
        except Exception:
            pass
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
    
    try:
        writer = get_stream_writer()
        writer({"status": "finalizing", "step": "response_node", "message": "Preparing final response..."})
    except Exception:
        pass
    
    current_messages = state['messages'] # Accumulated messages
    final_answer_content = "Response Node: Default final answer."
    streaming_log = []
    
    last_ai_message = current_messages[-1] if current_messages and isinstance(current_messages[-1], AIMessage) else None
    
    if last_ai_message and not last_ai_message.tool_calls and last_ai_message.content:
        final_answer_content = last_ai_message.content
        try:
            writer = get_stream_writer()
            writer({"status": "complete", "step": "response_node", "message": "Final answer extracted from LLM response"})
        except Exception:
            pass
    elif state.get('error_message'):
        final_answer_content = f"Error encountered: {state['error_message']}"
        streaming_log.append(final_answer_content)
        try:
            writer = get_stream_writer()
            writer({"status": "error", "step": "response_node", "message": "Error state detected"})
        except Exception:
            pass
    else:
        warning_msg = f"Response Node: Could not determine a final answer from the last LLM message. Last AI message: {last_ai_message}"
        if last_ai_message and last_ai_message.tool_calls:
            warning_msg += f" (It contained tool calls: {last_ai_message.tool_calls}) - this might indicate a routing issue if response_node was reached directly."
        print(warning_msg)
        streaming_log.append(warning_msg)
        final_answer_content = last_ai_message.content if last_ai_message and last_ai_message.content else "No conclusive text response generated by LLM."
        try:
            writer = get_stream_writer()
            writer({"status": "fallback", "step": "response_node", "message": "Using fallback response generation"})
        except Exception:
            pass

    final_log_message = f"Final Answer: {final_answer_content}"
    streaming_log.append(final_log_message)

    try:
        writer = get_stream_writer()
        writer({"status": "ready", "step": "response_node", "message": "Final response ready for delivery"})
    except Exception:
        pass

    return {
        "final_answer": final_answer_content,
        "streaming_output": streaming_log,
        "current_step": state.get('current_step', 0) + 1
    }