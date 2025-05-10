import json
import logging
from textwrap import dedent
import sys
import os
import time # Added for rate limiting

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import logic functions for team tools
from backend.api_tools.team_tools import (
    fetch_team_info_and_roster_logic,
    fetch_team_stats_logic
)
from backend.api_tools.team_tracking import (
    fetch_team_passing_stats_logic,
    fetch_team_shooting_stats_logic,
    fetch_team_rebounding_stats_logic
)
# from backend.api_tools.team_tools import fetch_team_lineups_logic # Not currently used by agent

from backend.config import CURRENT_SEASON
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID,
    ConferenceNullable, DivisionNullable, LocationNullable, OutcomeNullable,
    SeasonSegmentNullable, GameSegmentNullable, Month # Added more specific params
)

def run_smoke_test(tool_func, tool_name, *args, **kwargs):
    logging.info(f"--- Testing tool: {tool_name} ---")
    logging.info(f"Arguments: args={args}, kwargs={kwargs}")
    try:
        result_str = tool_func(*args, **kwargs)
        logging.info(f"Raw result string (first 500 chars): {result_str[:500]}")
        
        try:
            result_json = json.loads(result_str)
            if isinstance(result_json, dict) and "error" in result_json:
                logging.error(f"Tool '{tool_name}' returned an error: {result_json['error']}")
            elif not result_json and not (isinstance(result_json, dict) and "error" in result_json):
                 logging.warning(f"Tool '{tool_name}' returned an empty but valid JSON response.")
            else:
                logging.info(f"Tool '{tool_name}' executed successfully. Parsed JSON type: {type(result_json)}")
        except json.JSONDecodeError as e:
            logging.error(f"Tool '{tool_name}' did not return valid JSON. Error: {e}. Result: {result_str[:500]}")
        
    except Exception as e:
        logging.error(f"Exception during tool '{tool_name}' execution: {e}", exc_info=True)
    logging.info(f"--- Finished testing tool: {tool_name} ---\n")
    time.sleep(0.7) # Delay to help avoid rate limiting

if __name__ == "__main__":
    logging.info("======== Starting Team Tools Smoke Tests (with problematic tests commented) ========") # Updated title

    # --- fetch_team_info_and_roster_logic ---
    run_smoke_test(fetch_team_info_and_roster_logic, "fetch_team_info_and_roster_logic (LAL)", team_identifier="LAL", season=CURRENT_SEASON)
    run_smoke_test(fetch_team_info_and_roster_logic, "fetch_team_info_and_roster_logic (Boston Celtics)", team_identifier="Boston Celtics", season="2022-23")
    run_smoke_test(fetch_team_info_and_roster_logic, "fetch_team_info_and_roster_logic (Invalid Team)", team_identifier="InvalidTeamXYZ", season=CURRENT_SEASON) # Expected error

    # --- fetch_team_stats_logic ---
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (GSW Base)", team_identifier="GSW", season=CURRENT_SEASON, measure_type="Base")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (DEN Advanced)", team_identifier="DEN", season="2022-23", measure_type="Advanced")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (MIA Opponent, Totals)", team_identifier="MIA", season="2023-24", per_mode="Totals", measure_type="Opponent")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (BOS Scoring)", team_identifier="BOS", season="2023-24", measure_type="Scoring")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (PHI Usage)", team_identifier="PHI", season="2023-24", measure_type="Usage") # Re-enabled
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (MIL Four Factors)", team_identifier="MIL", season="2023-24", measure_type="Four Factors")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (DAL Misc)", team_identifier="DAL", season="2023-24", measure_type="Misc") # Re-enabled
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (LAL Playoffs)", team_identifier="LAL", season="2022-23", season_type="Playoffs")
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (SAS Date Range)", team_identifier="SAS", season="2023-24", date_from="2023-12-01", date_to="2023-12-31")
    # Removed (Location Home) test as fetch_team_stats_logic does not take location directly
    # Removed (Outcome W) test as fetch_team_stats_logic does not take outcome directly
    run_smoke_test(fetch_team_stats_logic, "fetch_team_stats_logic (Vs Opponent)", team_identifier="GSW", season="2023-24", opponent_team_id=1610612747) # GSW vs LAL

    # --- fetch_team_passing_stats_logic ---
    run_smoke_test(fetch_team_passing_stats_logic, "fetch_team_passing_stats_logic (DEN PerGame)", team_identifier="DEN", season=CURRENT_SEASON, per_mode="PerGame")
    run_smoke_test(fetch_team_passing_stats_logic, "fetch_team_passing_stats_logic (SAC Totals)", team_identifier="SAC", season="2022-23", per_mode="Totals")
    run_smoke_test(fetch_team_passing_stats_logic, "fetch_team_passing_stats_logic (Invalid PerMode)", team_identifier="MIA", season="2023-24", per_mode="Per36") # Should default or error
    run_smoke_test(fetch_team_passing_stats_logic, "fetch_team_passing_stats_logic (Playoffs)", team_identifier="PHI", season="2022-23", season_type="Playoffs")

    # --- fetch_team_shooting_stats_logic ---
    run_smoke_test(fetch_team_shooting_stats_logic, "fetch_team_shooting_stats_logic (GSW)", team_identifier="GSW", season=CURRENT_SEASON)
    run_smoke_test(fetch_team_shooting_stats_logic, "fetch_team_shooting_stats_logic (PHX Playoffs)", team_identifier="PHX", season="2022-23", season_type="Playoffs")
    run_smoke_test(fetch_team_shooting_stats_logic, "fetch_team_shooting_stats_logic (Invalid PerMode)", team_identifier="DAL", season="2023-24", per_mode="Per36") # Should default or error
    run_smoke_test(fetch_team_shooting_stats_logic, "fetch_team_shooting_stats_logic (PreSeason)", team_identifier="OKC", season=CURRENT_SEASON, season_type="Pre Season")

    # --- fetch_team_rebounding_stats_logic ---
    run_smoke_test(fetch_team_rebounding_stats_logic, "fetch_team_rebounding_stats_logic (BOS)", team_identifier="BOS", season=CURRENT_SEASON)
    run_smoke_test(fetch_team_rebounding_stats_logic, "fetch_team_rebounding_stats_logic (MEM PerGame)", team_identifier="MEM", season="2023-24", per_mode="PerGame")
    run_smoke_test(fetch_team_rebounding_stats_logic, "fetch_team_rebounding_stats_logic (Invalid PerMode)", team_identifier="NYK", season="2022-23", per_mode="Per36") # Should return custom error
    # Removed (All Star) test for team rebounding as "EAST" is not a valid team_identifier for this context.
    
    logging.info("======== Team Tools Smoke Tests Completed ========")