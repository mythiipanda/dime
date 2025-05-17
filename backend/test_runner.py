"""
Test runner script for executing prompts against the NBA analysis agent.
This script runs a series of prompts, handles retries for rate limiting,
collects results, and prints a summary of the test run.

It is intended to be run as a standalone script for testing agent responses.
"""
import time
import json
import logging
import random
from typing import List, Dict, Any, Iterator, Optional

from agno.utils.pprint import pprint_run_response
from agno.agent import RunResponse

from backend.agents import nba_agent
from backend.logging_config import setup_logging
from backend.config import settings

# Setup logging for this script if not already configured by an entry point
if not logging.getLogger().hasHandlers(): # Check if root logger has handlers
    log_level_str = "DEBUG" if settings.AGENT_DEBUG_MODE else settings.LOG_LEVEL
    setup_logging(log_level_override=log_level_str)

logger = logging.getLogger(__name__)

# Module-level list to accumulate results from all run_team_prompt calls
all_results: List[Dict[str, Any]] = []

def run_team_prompt(prompt: str, max_retries: int = 3, initial_delay: float = 1.0) -> Dict[str, Any]:
    """
    Runs a given prompt against the `nba_agent`, handles retries on rate limits,
    and records the outcome.

    Args:
        prompt (str): The prompt string to send to the agent.
        max_retries (int, optional): Maximum number of retries for rate limit errors. Defaults to 3.
        initial_delay (float, optional): Initial delay in seconds before the first retry. Defaults to 1.0.

    Returns:
        Dict[str, Any]: A dictionary containing the test result, including prompt, duration,
                        success status, result data or error info, and retry count.
    """
    logger.info(f"Running agent with prompt: '{prompt}'")
    start_time = time.time()
    final_result_data: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None
    raw_final_message: Optional[str] = None
    current_retry_count = 0 # Renamed from retry_count to avoid confusion with result key
    
    while current_retry_count <= max_retries:
        try:
            if current_retry_count > 0:
                # Exponential backoff with jitter
                delay = (initial_delay * (2 ** (current_retry_count - 1))) + random.uniform(0, initial_delay / 2)
                logger.info(f"Retry {current_retry_count}/{max_retries} for prompt '{prompt}' after {delay:.2f}s delay.")
                time.sleep(delay)
            
            result_iterator: Iterator[RunResponse] = nba_agent.run(prompt, stream=True)
            
            final_response_object: Optional[RunResponse] = None
            for response_chunk in result_iterator:
                pprint_run_response([response_chunk], markdown=True) # Pretty print each chunk
                final_response_object = response_chunk # Keep track of the last response object
            
            # Process the final response object
            if final_response_object and final_response_object.messages:
                last_message = final_response_object.messages[-1]
                if last_message.role == 'assistant' and isinstance(last_message.content, str):
                    raw_final_message = last_message.content
                    # Attempt to parse if it's JSON, otherwise store as string
                    try:
                        # This assumes the agent's final output might be structured JSON
                        # If it's always plain text, this try-except is not strictly needed for final_result_data
                        parsed_content = json.loads(raw_final_message)
                        final_result_data = {"analysis_summary": parsed_content}
                    except json.JSONDecodeError:
                        final_result_data = {"analysis_summary": raw_final_message} # Store as raw string if not JSON
                else: # Last message not from assistant or not string content
                    raw_final_message = str(last_message.content if last_message else "No content in last message")
                    error_info = {"error": "Agent did not end with a valid assistant message.", "last_message_content": raw_final_message}
            else: # No messages in the final response object
                raw_final_message = "No response messages received from agent."
                error_info = {"error": "Agent failed to produce any message history.", "details": raw_final_message}

            if error_info: # If error_info was set due to message processing issues
                final_result_data = None # Ensure no result data if there was an error
            elif final_result_data is None and raw_final_message: # If no specific error, but no data extracted
                 error_info = {"error": "Failed to extract final structured data from agent response.", "last_raw_message": raw_final_message}
            
            # If a non-retryable error occurred or successful, break
            # Check specifically if error_info is not None before accessing .get()
            current_error_message = error_info.get("error", "") if error_info else ""
            if error_info and "429 Too Many Requests" not in current_error_message:
                break 
            if not error_info: # Successful run (no error_info set)
                break

        except Exception as e:
            error_str = str(e)
            logger.exception(f"Exception during agent run for prompt: '{prompt}'") # Log full exception
            if "429 Too Many Requests" in error_str and current_retry_count < max_retries:
                logger.warning(f"Rate limit error for prompt '{prompt}'. Retry {current_retry_count + 1}/{max_retries}.")
                # error_info will be set in the next iteration if retries fail or handled if success
            else: # Non-retryable error or max retries exceeded
                error_info = {"error": f"Unhandled exception: {error_str}", "details": "Check logs for full traceback."}
                final_result_data = None
                break # Exit loop on non-retryable error or max retries
        finally:
            # This block ensures that if max_retries is hit due to 429, it's properly recorded.
            current_error_message_finally = error_info.get("error", "") if error_info else ""
            if current_retry_count == max_retries and "429 Too Many Requests" in current_error_message_finally:
                 error_info = {"error": f"Max retries ({max_retries}) exceeded due to rate limiting for prompt '{prompt}'."}
                 final_result_data = None

        current_retry_count += 1 # Increment retry_count only if we continue the loop

    end_time = time.time()
    run_duration = end_time - start_time

    result_entry = {
        "prompt": prompt,
        "duration_seconds": round(run_duration, 2),
        "success": error_info is None and final_result_data is not None, # Success means no error AND data
        "result_data": final_result_data,
        "error_info": error_info,
        "retries_attempted": current_retry_count # Use the loop counter
    }
    all_results.append(result_entry)

    logger.info(f"Finished run for prompt: '{prompt}'. Success: {result_entry['success']}. Duration: {run_duration:.2f}s. Retries: {result_entry['retries_attempted']}")
    return result_entry

def print_summary() -> None:
    """
    Prints a formatted summary of all test results accumulated in `all_results`.
    Includes overall statistics and detailed results for each prompt.
    """
    print("\n" + "=" * 80)
    print("Test Run Summary")
    print("=" * 80)
    
    if not all_results:
        print("No test results to summarize.")
        print("=" * 80)
        return

    total_tests = len(all_results)
    successful_tests = sum(1 for r in all_results if r['success'])
    failed_tests = total_tests - successful_tests
    total_duration = sum(r['duration_seconds'] for r in all_results)
    total_retries_attempted = sum(r.get('retries_attempted', 0) for r in all_results)
    
    print(f"\nOverall Statistics:")
    print(f"  Total Tests Run: {total_tests}")
    print(f"  Successful Tests: {successful_tests}")
    print(f"  Failed Tests: {failed_tests}")
    print(f"  Total Duration: {total_duration:.2f}s")
    print(f"  Total Retries Attempted: {total_retries_attempted}")
    success_rate_str = f"{(successful_tests/total_tests)*100:.1f}%" if total_tests > 0 else "N/A"
    print(f"  Success Rate: {success_rate_str}")
    
    print("\nDetailed Results:")
    print("-" * 80)
    for i, result in enumerate(all_results, 1):
        status_char = "✓" if result['success'] else "✗"
        retries_info = result.get('retries_attempted', 0)
        duration_info = result['duration_seconds']
        # Ensure prompt is a string before slicing
        prompt_str = str(result.get('prompt', 'N/A'))
        prompt_display = prompt_str[:70] + ('...' if len(prompt_str) > 70 else '')
        
        print(f"{i:3d}. [{status_char}] Prompt: \"{prompt_display}\"")
        print(f"       Duration: {duration_info:.2f}s, Retries: {retries_info}")
        if not result['success'] and result.get('error_info'):
            error_message = result['error_info'].get('error', "Unknown error")
            error_details = result['error_info'].get('details', '')
            print(f"       Error: {error_message}" + (f" ({error_details})" if error_details else ""))
        elif not result['success']: # Fallback if error_info is missing but success is False
            print(f"       Error: Unknown failure (no error_info provided).")
        # Add a small separator for readability if not the last item, or just a newline
        if i < total_tests:
            print("-" * 80)
        else:
            print() # Just a newline after the last item's details
    
    print("=" * 80)

# Example usage (can be uncommented to run tests directly)
# if __name__ == "__main__":
#     test_prompts = [
#         "What were LeBron James' stats in the 2020 NBA Finals?",
#         "Compare Michael Jordan's 1990-91 season stats with Kobe Bryant's 2005-06 season.",
#         "Which team had the best offensive rating in the 2022-23 season?",
#         "Get the box score for the Lakers vs Celtics game on Christmas Day 2023.",
#         "Non existent player query for testing failure", # Expected to fail gracefully
#         "What are the current live odds for today's games?",
#         "Give me a detailed shot chart analysis for Stephen Curry's last game."
#     ]
#     for p in test_prompts:
#         run_team_prompt(p)
#     print_summary()