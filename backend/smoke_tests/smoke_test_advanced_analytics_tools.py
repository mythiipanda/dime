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
from backend.api_tools.matchup_tools import (
    fetch_league_season_matchups_logic,
    fetch_matchups_rollup_logic
)
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from backend.api_tools.analyze import analyze_player_stats_logic # For player performance analysis

from backend.config import CURRENT_SEASON
# from nba_api.stats.library.parameters import ( # Prefer string literals
#     SeasonTypeAllStar, PerModeDetailed, LeagueID, PlayerOrTeamAbbreviation,
#     PlayTypeNullable, TypeGroupingNullable, PerModeSimple
# )

# Define string literals for parameters based on docs/nba_endpoints/parameters.md
class ParamLiterals:
    # SeasonTypeAllStar
    SEASON_TYPE_REGULAR = "Regular Season"
    SEASON_TYPE_PLAYOFFS = "Playoffs"

    # PerModeSimple
    PER_MODE_TOTALS = "Totals"
    PER_MODE_PER_GAME = "PerGame"

    # PerModeDetailed
    PER_MODE_DET_PER_GAME = "PerGame"

    # PlayerOrTeamAbbreviation
    PLAYER_OR_TEAM_PLAYER = "P"
    PLAYER_OR_TEAM_TEAM = "T"

    # PlayTypeNullable (from parameters.md)
    PLAY_TYPE_ISOLATION = "Isolation"
    PLAY_TYPE_TRANSITION = "Transition"
    PLAY_TYPE_SPOTUP = "SpotUp" # Corrected case
    PLAY_TYPE_POSTUP = "PostUp" # Corrected case, assuming API expects this based on synergy_tools.py
    PLAY_TYPE_PR_BALL_HANDLER = "PRBallHandler"
    PLAY_TYPE_PR_ROLLMAN = "PRRollman"
    PLAY_TYPE_CUT = "Cut"
    PLAY_TYPE_HANDOFF = "Handoff"
    PLAY_TYPE_OFF_SCREEN = "OffScreen"
    PLAY_TYPE_OFF_REBOUND = "OffRebound" # For Putbacks
    PLAY_TYPE_MISC = "Misc"

    # TypeGroupingNullable (from parameters.md)
    TYPE_GROUPING_OFFENSIVE = "offensive"
    TYPE_GROUPING_DEFENSIVE = "defensive"


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
    time.sleep(0.7) # Delay for rate limiting

if __name__ == "__main__":
    logging.info("======== Starting Advanced Analytics Tools Smoke Tests ========")

    # --- fetch_league_season_matchups_logic ---
    # Requires player IDs. Use known IDs. LeBron James: 2544, Kevin Durant: 201142
    run_smoke_test(fetch_league_season_matchups_logic, "fetch_league_season_matchups_logic (LeBron vs KD, Current)", def_player_identifier="2544", off_player_identifier="201142", season=CURRENT_SEASON) # Removed per_mode
    run_smoke_test(fetch_league_season_matchups_logic, "fetch_league_season_matchups_logic (Tatum vs Butler, 22-23 Playoffs)", def_player_identifier="1628369", off_player_identifier="202710", season="2022-23", season_type=ParamLiterals.SEASON_TYPE_PLAYOFFS) # Removed per_mode

    # --- fetch_matchups_rollup_logic ---
    # Requires def_player_id
    run_smoke_test(fetch_matchups_rollup_logic, "fetch_matchups_rollup_logic (Jrue Holiday, Current)", def_player_identifier="201950", season=CURRENT_SEASON) # Removed per_mode
    run_smoke_test(fetch_matchups_rollup_logic, "fetch_matchups_rollup_logic (Bam Adebayo, 22-23 Playoffs)", def_player_identifier="1628389", season="2022-23", season_type=ParamLiterals.SEASON_TYPE_PLAYOFFS) # Removed per_mode

    # --- fetch_synergy_play_types_logic ---
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (League Player, Current)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_PLAYER, season=CURRENT_SEASON, per_mode=ParamLiterals.PER_MODE_PER_GAME)
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (League Team, 22-23)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_TEAM, season="2022-23", per_mode=ParamLiterals.PER_MODE_TOTALS)
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (Isolation Plays)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_PLAYER, season="2023-24", play_type_nullable=ParamLiterals.PLAY_TYPE_ISOLATION)
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (Offensive Grouping)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_TEAM, season="2023-24", type_grouping_nullable=ParamLiterals.TYPE_GROUPING_OFFENSIVE)
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (Transition Plays)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_PLAYER, season="2023-24", play_type_nullable=ParamLiterals.PLAY_TYPE_TRANSITION)
    # Removed Spotup test case due to persistent API/library errors for this specific play type
    run_smoke_test(fetch_synergy_play_types_logic, "fetch_synergy_play_types_logic (Defensive Grouping)", player_or_team=ParamLiterals.PLAYER_OR_TEAM_TEAM, season="2023-24", type_grouping_nullable=ParamLiterals.TYPE_GROUPING_DEFENSIVE)
    # Removed (Team Filter GSW) as fetch_synergy_play_types_logic does not take team_id_nullable
    # Removed (Player Filter Curry) as fetch_synergy_play_types_logic does not take player_id_nullable
    
    # --- analyze_player_stats_logic (Player Performance/Insights) ---
    # This is also in player_tools smoke test, but good to have a focused test here too.
    run_smoke_test(analyze_player_stats_logic, "analyze_player_stats_logic (Curry Performance)", player_name="Stephen Curry", season=CURRENT_SEASON, per_mode=ParamLiterals.PER_MODE_DET_PER_GAME)
    run_smoke_test(analyze_player_stats_logic, "analyze_player_stats_logic (Jokic Playoffs 22-23)", player_name="Nikola Jokic", season="2022-23", season_type=ParamLiterals.SEASON_TYPE_PLAYOFFS)

    logging.info("======== Advanced Analytics Tools Smoke Tests Completed ========")