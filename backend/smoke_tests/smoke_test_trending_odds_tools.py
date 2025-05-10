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

# Import logic functions
from backend.api_tools.trending_tools import fetch_top_performers_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic
from backend.api_tools.odds_tools import fetch_odds_data_logic

from backend.config import CURRENT_SEASON
# from nba_api.stats.library.parameters import ( # Prefer string literals
#     SeasonTypeAllStar, PerMode48, StatCategoryAbbreviation, LeagueID
# )

# Define string literals for parameters based on docs/nba_endpoints/parameters.md
class ParamLiterals:
    # SeasonTypeAllStar
    SEASON_TYPE_REGULAR = "Regular Season"
    SEASON_TYPE_PLAYOFFS = "Playoffs"
    SEASON_TYPE_ALL_STAR = "All Star"
    SEASON_TYPE_PRE_SEASON = "Pre Season"

    # StatCategoryAbbreviation (for league leaders / top performers)
    STAT_CAT_PTS = "PTS"
    STAT_CAT_AST = "AST"
    STAT_CAT_REB = "REB"
    STAT_CAT_STL = "STL"
    STAT_CAT_BLK = "BLK"
    STAT_CAT_FG_PCT = "FG_PCT"
    STAT_CAT_FG3_PCT = "FG3_PCT"
    STAT_CAT_FT_PCT = "FT_PCT"
    STAT_CAT_TOV = "TOV" # Turnovers
    STAT_CAT_EFF = "EFF" # Efficiency


def run_smoke_test(tool_func, tool_name, *args, **kwargs):
    logging.info(f"--- Testing tool: {tool_name} ---")
    logging.info(f"Arguments: args={args}, kwargs={kwargs}")
    # For odds, we don't expect args/kwargs other than what the logic function itself handles (none for current odds)
    is_odds_tool = "odds" in tool_name.lower()

    try:
        if is_odds_tool: # fetch_odds_data_logic takes no arguments
             result_str = tool_func()
        else:
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
    time.sleep(0.7) # Delay for rate limiting

if __name__ == "__main__":
    logging.info("======== Starting Trending & Odds Tools Smoke Tests ========")

    # --- fetch_top_performers_logic ---
    # fetch_top_performers_logic does not take per_mode or scope directly, these are defaulted in the underlying fetch_league_leaders_logic call.
    run_smoke_test(fetch_top_performers_logic, "fetch_top_performers_logic (PTS, Current)", category=ParamLiterals.STAT_CAT_PTS, season=CURRENT_SEASON)
    run_smoke_test(fetch_top_performers_logic, "fetch_top_performers_logic (AST, 22-23, Top 3)", category=ParamLiterals.STAT_CAT_AST, season="2022-23", top_n=3)
    run_smoke_test(fetch_top_performers_logic, "fetch_top_performers_logic (BLK, Playoffs)", category=ParamLiterals.STAT_CAT_BLK, season="2023-24", season_type=ParamLiterals.SEASON_TYPE_PLAYOFFS, top_n=2)
    run_smoke_test(fetch_top_performers_logic, "fetch_top_performers_logic (STL, PreSeason)", category=ParamLiterals.STAT_CAT_STL, season=CURRENT_SEASON, season_type=ParamLiterals.SEASON_TYPE_PRE_SEASON, top_n=5)
    # run_smoke_test(fetch_top_performers_logic, "fetch_top_performers_logic (FG_PCT, AllStar)", category=ParamLiterals.STAT_CAT_FG_PCT, season="2023-24", season_type=ParamLiterals.SEASON_TYPE_ALL_STAR, top_n=1) # External API returns 500 error for this combo

    # --- fetch_top_teams_logic ---
    # fetch_top_teams_logic does not take league_id directly, it's handled by underlying standings call (currently defaults to NBA)
    run_smoke_test(fetch_top_teams_logic, "fetch_top_teams_logic (Current, Top 3)", season=CURRENT_SEASON, top_n=3)
    run_smoke_test(fetch_top_teams_logic, "fetch_top_teams_logic (22-23 Playoffs, Top 2)", season="2022-23", season_type=ParamLiterals.SEASON_TYPE_PLAYOFFS, top_n=2)
    run_smoke_test(fetch_top_teams_logic, "fetch_top_teams_logic (Current PreSeason)", season=CURRENT_SEASON, season_type=ParamLiterals.SEASON_TYPE_PRE_SEASON, top_n=4)
    # To test WNBA, fetch_league_standings_logic and fetch_top_teams_logic would need to accept league_id
    # run_smoke_test(fetch_top_teams_logic, "fetch_top_teams_logic (WNBA 2023)", season="2023", top_n=3) # league_id needed in logic

    # --- fetch_odds_data_logic ---
    # This tool fetches live odds and does not take arguments for specific dates/games in its current form.
    # It's also not cached by the tool wrapper.
    run_smoke_test(fetch_odds_data_logic, "fetch_odds_data_logic (Live NBA Odds)")
    # To test different leagues if the underlying logic supports it (it might not directly)
    # run_smoke_test(fetch_odds_data_logic, "fetch_odds_data_logic (Live WNBA Odds)", league='WNBA') # Assuming logic could handle this

    logging.info("======== Trending & Odds Tools Smoke Tests Completed ========")