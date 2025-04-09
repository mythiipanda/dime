import time
import json
import logging
from typing import List, Dict, Any
from teams import nba_analysis_team
import random

logger = logging.getLogger(__name__)

all_results: List[Dict[str, Any]] = []

def run_team_prompt(prompt: str, max_retries: int = 3, initial_delay: float = 1.0):
    logger.info(f"Running NBA Analysis Team with prompt: '{prompt}'")
    start_time = time.time()
    final_result_data = None
    error_info = None
    raw_final_message = None
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            if retry_count > 0:
                delay = initial_delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
                logger.info(f"Retry {retry_count}/{max_retries} after {delay:.2f}s delay")
                time.sleep(delay)
            
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
            
            # If we got here without raising an exception, break the retry loop
            if not "429 Too Many Requests" in str(error_info):
                break

        except Exception as e:
            error_str = str(e)
            if "429 Too Many Requests" in error_str and retry_count < max_retries:
                logger.warning(f"Rate limit hit, will retry ({retry_count + 1}/{max_retries})")
                retry_count += 1
                continue
            logger.exception(f"Error running team prompt: '{prompt}'")
            error_info = {"error": f"Exception during team run: {error_str}"}
            final_result_data = None
            break

        retry_count += 1

    end_time = time.time()
    run_duration = end_time - start_time

    result_entry = {
        "prompt": prompt,
        "duration_seconds": round(run_duration, 2),
        "success": error_info is None,
        "result_data": final_result_data,
        "error_info": error_info,
        "retries": retry_count
    }
    all_results.append(result_entry)

    logger.info(f"Finished run for prompt: '{prompt}'. Success: {result_entry['success']}. Duration: {run_duration:.2f}s")
    return result_entry

def print_summary():
    """Print a summary of all test results in a clean format."""
    print("\nTest Results Summary")
    print("=" * 80)
    
    total_tests = len(all_results)
    successful_tests = sum(1 for r in all_results if r['success'])
    failed_tests = total_tests - successful_tests
    total_duration = sum(r['duration_seconds'] for r in all_results)
    total_retries = sum(r.get('retries', 0) for r in all_results)
    
    print(f"\nOverall Statistics:")
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Total Retries: {total_retries}")
    print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    print("-" * 80)
    for i, result in enumerate(all_results, 1):
        status = "✓" if result['success'] else "✗"
        retries = result.get('retries', 0)
        duration = result['duration_seconds']
        print(f"{i:2d}. [{status}] {result['prompt'][:60]}{'...' if len(result['prompt']) > 60 else ''}")
        print(f"    Duration: {duration:.2f}s, Retries: {retries}")
        if not result['success']:
            error = result['error_info']['error'] if result['error_info'] else "Unknown error"
            print(f"    Error: {error}")
    
    print("\n" + "=" * 80)