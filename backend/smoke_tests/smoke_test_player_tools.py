import json
import logging
from textwrap import dedent
import sys
import os
import time 

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from backend.api_tools.player_tools import (
    fetch_player_info_logic,
    fetch_player_gamelog_logic,
    fetch_player_career_stats_logic,
    fetch_player_profile_logic,
    fetch_player_shotchart_logic,
    fetch_player_defense_logic,
    fetch_player_hustle_stats_logic,
    fetch_player_awards_logic
)
from backend.api_tools.player_tracking import (
    fetch_player_clutch_stats_logic,
    fetch_player_passing_stats_logic,
    fetch_player_rebounding_stats_logic,
    fetch_player_shots_tracking_logic
)
from backend.api_tools.analyze import analyze_player_stats_logic 

from backend.config import CURRENT_SEASON
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerMode48, PerModeDetailed, MeasureTypeDetailedDefense, LeagueID, Scope,
    StatCategoryAbbreviation, ClutchTime, AheadBehind, MeasureTypeDetailed # Corrected import
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
            elif not result_json and not (isinstance(result_json, dict) and "error" in result_json) : 
                logging.warning(f"Tool '{tool_name}' returned an empty but valid JSON response (e.g. no data found).")
            else:
                logging.info(f"Tool '{tool_name}' executed successfully. Parsed JSON type: {type(result_json)}")
        except json.JSONDecodeError as e:
            logging.error(f"Tool '{tool_name}' did not return valid JSON. Error: {e}. Result: {result_str[:500]}")
        
    except Exception as e:
        logging.error(f"Exception during tool '{tool_name}' execution: {e}", exc_info=True)
    logging.info(f"--- Finished testing tool: {tool_name} ---\n")
    time.sleep(0.7) 

if __name__ == "__main__":
    logging.info("======== Starting Player Tools Smoke Tests ========")

    run_smoke_test(fetch_player_info_logic, "fetch_player_info_logic", player_name="LeBron James")
    run_smoke_test(fetch_player_info_logic, "fetch_player_info_logic", player_name="NonExistent PlayerXYZ123")

    run_smoke_test(fetch_player_gamelog_logic, "fetch_player_gamelog_logic", player_name="Jayson Tatum", season=CURRENT_SEASON, season_type="Regular Season")
    run_smoke_test(fetch_player_gamelog_logic, "fetch_player_gamelog_logic", player_name="Nikola Jokic", season="2022-23", season_type="Playoffs")
    run_smoke_test(fetch_player_gamelog_logic, "fetch_player_gamelog_logic", player_name="Stephen Curry", season="2023-24", season_type="All Star")
    run_smoke_test(fetch_player_gamelog_logic, "fetch_player_gamelog_logic (PreSeason)", player_name="Victor Wembanyama", season=CURRENT_SEASON, season_type="Pre Season")
    run_smoke_test(fetch_player_gamelog_logic, "fetch_player_gamelog_logic (Invalid SeasonType)", player_name="LeBron James", season=CURRENT_SEASON, season_type="InvalidSeasonType")

    run_smoke_test(fetch_player_career_stats_logic, "fetch_player_career_stats_logic", player_name="Kevin Durant", per_mode="Totals")
    run_smoke_test(fetch_player_career_stats_logic, "fetch_player_career_stats_logic", player_name="Luka Doncic", per_mode="PerGame")
    run_smoke_test(fetch_player_career_stats_logic, "fetch_player_career_stats_logic", player_name="Zion Williamson", per_mode="Per36")
    run_smoke_test(fetch_player_career_stats_logic, "fetch_player_career_stats_logic (Per48)", player_name="Nikola Jokic", per_mode="Per48") 

    run_smoke_test(fetch_player_profile_logic, "fetch_player_profile_logic", player_name="Giannis Antetokounmpo", per_mode="PerGame")
    run_smoke_test(fetch_player_profile_logic, "fetch_player_profile_logic", player_name="Ja Morant", per_mode="Totals")
    run_smoke_test(fetch_player_profile_logic, "fetch_player_profile_logic (Per36)", player_name="Anthony Edwards", per_mode="Per36")
    run_smoke_test(fetch_player_profile_logic, "fetch_player_profile_logic (Per48)", player_name="Joel Embiid", per_mode="Per48")
    run_smoke_test(fetch_player_profile_logic, "fetch_player_profile_logic (Nikola Jokic - Default PerMode)", player_name="Nikola Jokic") # Test default per_mode

    run_smoke_test(fetch_player_shotchart_logic, "fetch_player_shotchart_logic", player_name="Damian Lillard", season=CURRENT_SEASON, season_type="Regular Season")
    run_smoke_test(fetch_player_shotchart_logic, "fetch_player_shotchart_logic", player_name="Jayson Tatum", season="2022-23", season_type="Playoffs")
    run_smoke_test(fetch_player_shotchart_logic, "fetch_player_shotchart_logic (No Data)", player_name="Ben Simmons", season="2021-22", season_type="Regular Season") 

    run_smoke_test(fetch_player_defense_logic, "fetch_player_defense_logic (Overall, PerGame)", player_name="Marcus Smart", season="2022-23", season_type="Regular Season", per_mode="PerGame")
    run_smoke_test(fetch_player_defense_logic, "fetch_player_defense_logic (3 Pointers, Totals)", player_name="Draymond Green", season="2023-24", per_mode="Totals") 
    run_smoke_test(fetch_player_defense_logic, "fetch_player_defense_logic (Less Than 6Ft, Per100Poss)", player_name="Rudy Gobert", season="2022-23", per_mode="Per100Possessions")

    run_smoke_test(fetch_player_hustle_stats_logic, "fetch_player_hustle_stats_logic (PerMinute)", player_name="Alex Caruso", season="2023-24", per_mode="PerMinute")
    run_smoke_test(fetch_player_hustle_stats_logic, "fetch_player_hustle_stats_logic (PerGame)", player_name="Jose Alvarado", season="2022-23", per_mode="PerGame")
    run_smoke_test(fetch_player_hustle_stats_logic, "fetch_player_hustle_stats_logic (Totals)", player_name="Marcus Smart", season="2021-22", per_mode="Totals")
    run_smoke_test(fetch_player_hustle_stats_logic, "fetch_player_hustle_stats_logic (League Wide)", season="2023-24") 
    run_smoke_test(fetch_player_hustle_stats_logic, "fetch_player_hustle_stats_logic (Team Filter)", team_id=1610612747, season="2022-23") 

    run_smoke_test(fetch_player_awards_logic, "fetch_player_awards_logic", player_name="Michael Jordan")
    run_smoke_test(fetch_player_awards_logic, "fetch_player_awards_logic (Few Awards)", player_name="Victor Wembanyama") 

    run_smoke_test(fetch_player_clutch_stats_logic, "fetch_player_clutch_stats_logic (Base, Totals)", player_name="DeMar DeRozan", season="2023-24", season_type="Regular Season", measure_type=MeasureTypeDetailed.base, per_mode=PerModeDetailed.totals)
    run_smoke_test(fetch_player_clutch_stats_logic, "fetch_player_clutch_stats_logic (Advanced, PerGame)", player_name="Jimmy Butler", season="2022-23", season_type="Playoffs", measure_type=MeasureTypeDetailed.advanced, per_mode=PerModeDetailed.per_game)
    run_smoke_test(fetch_player_clutch_stats_logic, "fetch_player_clutch_stats_logic (Scoring, PlusMinus Y)", player_name="Damian Lillard", season="2023-24", measure_type=MeasureTypeDetailed.scoring, plus_minus="Y")
    run_smoke_test(fetch_player_clutch_stats_logic, "fetch_player_clutch_stats_logic (Usage, Location Home)", player_name="Jayson Tatum", season="2023-24", measure_type=MeasureTypeDetailed.usage, location_nullable="Home")
    run_smoke_test(fetch_player_clutch_stats_logic, "fetch_player_clutch_stats_logic (Date Range)", player_name="Kevin Durant", season="2023-24", date_from_nullable="2024-03-01", date_to_nullable="2024-03-31")

    run_smoke_test(fetch_player_passing_stats_logic, "fetch_player_passing_stats_logic (Default PerMode)", player_name="Nikola Jokic", season=CURRENT_SEASON, season_type="Regular Season")
    run_smoke_test(fetch_player_passing_stats_logic, "fetch_player_passing_stats_logic (Totals)", player_name="Tyrese Haliburton", season="2023-24", per_mode="Totals")
    run_smoke_test(fetch_player_passing_stats_logic, "fetch_player_passing_stats_logic (Invalid PerMode)", player_name="Chris Paul", season="2022-23", per_mode="Per36") 
    run_smoke_test(fetch_player_passing_stats_logic, "fetch_player_passing_stats_logic (Playoffs)", player_name="Jamal Murray", season="2022-23", season_type="Playoffs")

    run_smoke_test(fetch_player_rebounding_stats_logic, "fetch_player_rebounding_stats_logic (Default PerMode)", player_name="Domantas Sabonis", season="2023-24")
    run_smoke_test(fetch_player_rebounding_stats_logic, "fetch_player_rebounding_stats_logic (Totals)", player_name="Anthony Davis", season="2022-23", per_mode="Totals")
    run_smoke_test(fetch_player_rebounding_stats_logic, "fetch_player_rebounding_stats_logic (Invalid PerMode)", player_name="Rudy Gobert", season="2023-24", per_mode="Per36")
    run_smoke_test(fetch_player_rebounding_stats_logic, "fetch_player_rebounding_stats_logic (Playoffs)", player_name="Kevon Looney", season="2022-23", season_type="Playoffs")

    run_smoke_test(fetch_player_shots_tracking_logic, "fetch_player_shots_tracking_logic (Default)", player_name="LeBron James")
    run_smoke_test(fetch_player_shots_tracking_logic, "fetch_player_shots_tracking_logic (Season, Type)", player_name="Devin Booker", season="2022-23", season_type="Playoffs")
    run_smoke_test(fetch_player_shots_tracking_logic, "fetch_player_shots_tracking_logic (Opponent)", player_name="Kawhi Leonard", season="2023-24", opponent_team_id=1610612747) 
    run_smoke_test(fetch_player_shots_tracking_logic, "fetch_player_shots_tracking_logic (Date Range)", player_name="Shai Gilgeous-Alexander", season="2023-24", date_from="2024-02-01", date_to="2024-02-29")

    run_smoke_test(analyze_player_stats_logic, "analyze_player_stats_logic (Default)", player_name="Trae Young", season=CURRENT_SEASON, per_mode="PerGame")
    run_smoke_test(analyze_player_stats_logic, "analyze_player_stats_logic (Different Player/Season/PerMode)", player_name="Nikola Jokic", season="2022-23", per_mode="Totals")

    logging.info("======== Player Tools Smoke Tests Completed ========")