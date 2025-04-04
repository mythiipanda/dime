import json
import time
import logging
import sys
from typing import List, Dict, Any

# Import the TEAM agent directly
from teams import NBAnalysisTeam
# Import the JSON extraction helper (still potentially needed for final team output)
from main import extract_json_string
# Import constants if needed for constructing test calls
from nba_api.stats.library.parameters import PerMode36

# --- Configure Logging ---
LOG_FILE = 'app_test_output.log'
with open(LOG_FILE, 'w') as f: f.write("") # Clear log file

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers(): logger.handlers.clear()
logger.addHandler(file_handler)
# logger.addHandler(console_handler) # Keep console clean for final summary

# --- Helper Function ---
def log_and_print(message, level=logging.INFO):
    """Logs message to file and prints to console."""
    print(message)
    if level == logging.INFO: logger.info(message)
    elif level == logging.DEBUG: logger.debug(message)
    elif level == logging.WARNING: logger.warning(message)
    elif level == logging.ERROR: logger.error(message)
    elif level == logging.CRITICAL: logger.critical(message)

# --- Test Execution ---
all_results: List[Dict[str, Any]] = [] # List to store results

def run_team_prompt(prompt: str):
    """Runs a prompt directly against the NBAnalysisTeam and stores results."""
    log_and_print(f"Running TEAM with prompt: '{prompt}'") # Use helper function
    logger.info(f"Running TEAM with prompt: '{prompt}'") # Log separately for file
    start_time = time.time()
    final_result_data = None
    error_info = None
    raw_final_message = None

    try:
        # Use the Team agent now
        result = NBAnalysisTeam.run(prompt) # Using sync run
        logger.debug(f"Team raw result object type: {type(result)}")
        logger.debug(f"Team raw result object attributes: {dir(result) if result else 'None'}")

        # Attempt to get the final response from the lead agent's history
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            logger.debug(f"Team last message role: {last_message.role}, type={type(last_message.content)}")
            if last_message.role == 'assistant' and isinstance(last_message.content, str):
                 raw_final_message = last_message.content
                 logger.info("Using last assistant message content as final result.")
                 # Assume the lead agent provides the final formatted answer, not raw JSON
                 final_result_data = {"analysis_summary": raw_final_message}
            else:
                 logger.warning("Last message in team history was not assistant content.")
                 raw_final_message = str(last_message.content) # Store for error reporting
                 error_info = {"error": "Team did not end with an assistant message.", "last_message": raw_final_message}
        else:
            logger.error("Team result object has no 'messages' attribute or messages list is empty.")
            raw_final_message = getattr(result, 'response', None) # Fallback
            error_info = {"error": "Team failed to produce message history.", "response_attr": str(raw_final_message)}

        # If we didn't get a clean final message, mark as error
        if error_info:
             final_result_data = None # Ensure no data is marked on error
        elif final_result_data is None: # Should have been set if history was good
             error_info = {"error": "Failed to extract final response from agent history.", "last_raw": raw_final_message}


    except Exception as e:
        logger.exception(f"Error running team prompt: '{prompt}'")
        error_info = {"error": f"Exception during team run: {str(e)}"}
        final_result_data = None

    end_time = time.time()
    run_duration = end_time - start_time

    result_entry = {
        "prompt": prompt,
        "duration_seconds": round(run_duration, 2),
        "success": error_info is None,
        "result_data": final_result_data, # Store the final analysis or None
        "error_info": error_info
    }
    all_results.append(result_entry)
    logger.info(f"Finished run for prompt: '{prompt}'. Success: {result_entry['success']}. Duration: {run_duration:.2f}s")
    print(f"Finished: '{prompt}' ({run_duration:.2f}s) - {'OK' if result_entry['success'] else 'FAIL'}")


if __name__ == "__main__":
    log_and_print("--- Running NBA Analysis Team Directly ---")

    # --- Test Team with various prompts ---
    # Prompts should now focus on analysis, letting the team handle data fetching
    run_team_prompt(prompt="Give me a summary of Stephen Curry's basic info and headline stats.")
    run_team_prompt(prompt="Analyze LeBron James' game log for the 2023-24 regular season.")
    run_team_prompt(prompt="Compare Kevin Durant's per-game career stats to his totals.")
    run_team_prompt(prompt="Provide an overview of the Lakers 2023-24 season based on their roster and common info.")
    run_team_prompt(prompt="Find the games played by the Lakers this season and summarize their record.") # Relies on find_games -> analysis
    run_team_prompt(prompt="Can you get info for Player XYZ?") # Should fail gracefully
    run_team_prompt(prompt="What is the weather like in Los Angeles?") # Should fail gracefully

    # --- Print Summary ---
    log_and_print("\n--- Agent Team Test Summary ---")
    successful_runs = 0
    failed_runs = 0
    for i, res in enumerate(all_results):
        status = "SUCCESS" if res["success"] else "FAILED"
        summary = f"Test {i+1}: [{status}] Prompt: '{res['prompt']}' ({res['duration_seconds']}s)"
        log_and_print(summary)
        if not res["success"]:
            error_details = json.dumps(res['error_info'], indent=2, default=str)
            log_and_print(f"  Error: {error_details}", level=logging.ERROR)
            failed_runs += 1
        else:
            # Log summary of successful data
            log_and_print(f"  Result Summary: {res['result_data'].get('analysis_summary', 'N/A')[:150]}...") # Print start of analysis
            successful_runs += 1

    log_and_print(f"\nTotal Runs: {len(all_results)}, Successful: {successful_runs}, Failed: {failed_runs}")
    log_and_print(f"Full output logged to: {LOG_FILE}")
    log_and_print("--- Agent Script Finished ---")