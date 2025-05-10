import asyncio
import json
import logging
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.agents import nba_agent # The conversational agent
from backend.routes.sse import recursive_asdict, format_message_data # To process chunks like the SSE route

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_agent_and_print_sse_simulation(prompt: str):
    logger.info(f"--- Starting Agent SSE Stream Simulation for prompt: '{prompt}' ---")
    
    full_response_content = ""
    try:
        run_stream = await nba_agent.arun(prompt, stream=True, stream_intermediate_steps=True)
        
        async for chunk in run_stream:
            try:
                chunk_dict = recursive_asdict(chunk)
                # Simulate the processing done in the actual SSE route's format_message_data
                processed_message_for_sse = format_message_data(chunk_dict)
                
                print(f"RAW CHUNK (type: {chunk_dict.get('event')}):")
                # print(json.dumps(chunk_dict, indent=2, default=str)) # Can be very verbose
                # print("-" * 30)
                print(f"PROCESSED SSE MESSAGE DATA (event: {processed_message_for_sse.get('event')}):")
                print(json.dumps(processed_message_for_sse, indent=2, default=str))
                print("=" * 50)

                if processed_message_for_sse.get("event") == "RunResponse" and isinstance(processed_message_for_sse.get("content"), str):
                    full_response_content += processed_message_for_sse.get("content", "")
                elif processed_message_for_sse.get("dataType") and processed_message_for_sse.get("dataPayload"):
                    # If it's a structured data payload, we might want to log its presence
                    # The content itself is in dataPayload
                    logger.info(f"Detected structured data: {processed_message_for_sse.get('dataType')}")
                    # Potentially add this structured payload to a list for later inspection if needed
                    pass


                if processed_message_for_sse.get("event") == "RunCompleted":
                    logger.info("Agent run completed.")
                    # The final content is usually accumulated or is in the last RunResponse
                    # For this test, we'll just note completion.
                    # The 'content' in the RunCompleted message_data might be the final synthesized response.
                    if "content" in processed_message_for_sse:
                        full_response_content = processed_message_for_sse["content"]
            except AttributeError as ae:
                logger.error(f"AttributeError while processing a chunk: {ae}. Chunk was: {chunk}")
                # Potentially break or continue depending on how fatal this is for the test
                if "NoneType" in str(ae) and "role" in str(ae):
                    logger.warning("Likely the agno.models.google.gemini.py AttributeError. Stopping stream processing for this test.")
                    break
                # else: continue or raise
            except Exception as chunk_e:
                logger.error(f"Generic error while processing a chunk: {chunk_e}. Chunk was: {chunk}")


    except Exception as e:
        logger.error(f"Error during agent run simulation: {e}", exc_info=False) # Set exc_info to False to reduce noise if it's the known agno error
    
    logger.info(f"--- Agent SSE Stream Simulation Ended ---")
    logger.info(f"\n--- Accumulated/Final Content from Agent ---\n{full_response_content}\n------------------------------------")


if __name__ == "__main__":
    # sample_prompt = "What were LeBron James' stats in the 2020 NBA finals? Show key stats like PPG, RPG, APG."
    sample_prompt_for_table_and_reasoning = "Compare LeBron James and Michael Jordan's career playoff PPG, RPG, and APG. Show the comparison in a table."
    # prompt_explicit_json_table = "Compare the career playoff stats (PPG, RPG, APG) for LeBron James and Michael Jordan. Please present this comparison using the TABLE_DATA_JSON format."

    asyncio.run(run_agent_and_print_sse_simulation(sample_prompt_for_table_and_reasoning))