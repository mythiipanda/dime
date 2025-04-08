import time
import json
import logging
from typing import List, Dict, Any
from teams import nba_analysis_team

logger = logging.getLogger(__name__)

all_results: List[Dict[str, Any]] = []

def run_team_prompt(prompt: str):
    logger.info(f"Running NBA Analysis Team with prompt: '{prompt}'")
    start_time = time.time()
    final_result_data = None
    error_info = None
    raw_final_message = None

    try:
        result = nba_analysis_team.run(prompt)
        if hasattr(result, 'messages') and result.messages:
            last_message = result.messages[-1]
            if last_message.role == 'assistant' and isinstance(last_message.content, str):
                raw_final_message = last_message.content
                final_result_data = {"analysis_summary": raw_final_message}
            else:
                raw_final_message = str(last_message.content)
                error_info = {"error": "Team did not end with an assistant message.", "last_message": raw_final_message}
        else:
            raw_final_message = getattr(result, 'response', None)
            error_info = {"error": "Team failed to produce message history.", "response_attr": str(raw_final_message)}

        if error_info:
            final_result_data = None
        elif final_result_data is None:
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
        "result_data": final_result_data,
        "error_info": error_info
    }
    all_results.append(result_entry)
    logger.info(f"Finished run for prompt: '{prompt}'. Success: {result_entry['success']}. Duration: {run_duration:.2f}s")
    print(f"Finished: '{prompt}' ({run_duration:.2f}s) - {'OK' if result_entry['success'] else 'FAIL'}")

def print_summary():
    successful_runs = 0
    failed_runs = 0
    for i, res in enumerate(all_results):
        status = "SUCCESS" if res["success"] else "FAILED"
        summary = f"Test {i+1}: [{status}] Prompt: '{res['prompt']}' ({res['duration_seconds']}s)"
        print(summary)
        if not res["success"]:
            error_details = json.dumps(res['error_info'], indent=2, default=str)
            print(f"  Error: {error_details}")
            failed_runs += 1
        else:
            print(f"  Result Summary: {res['result_data'].get('analysis_summary', 'N/A')[:150]}...")
            successful_runs += 1

    print(f"\nTotal Runs: {len(all_results)}, Successful: {successful_runs}, Failed: {failed_runs}")