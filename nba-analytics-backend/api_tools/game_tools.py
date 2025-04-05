import logging
import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.library.parameters import LeagueID, SeasonTypeNullable, SeasonNullable
# import json # No longer needed
# import re # Unused
# Import helpers carefully - avoid circular imports if moving later
from .player_tools import _find_player_id
from .team_tools import _find_team_id
from .utils import _process_dataframe # Corrected import
from ..config import DEFAULT_TIMEOUT # Import from config

logger = logging.getLogger(__name__)

# DEFAULT_TIMEOUT moved to config.py
MAX_GAMES_TO_RETURN = 20 # Limit results further to prevent token errors

def fetch_league_games_logic(
    player_or_team_abbreviation: str = 'T',
    player_id_nullable: int | None = None,
    team_id_nullable: int | None = None,
    season_nullable: SeasonNullable = None,
    season_type_nullable: SeasonTypeNullable = SeasonTypeNullable.regular,
    league_id_nullable: LeagueID = LeagueID.nba,
    date_from_nullable: str | None = None,
    date_to_nullable: str | None = None
) -> dict:
    """
    Core logic to fetch games using LeagueGameFinder based on various criteria.
    NOTE: Filtering by vs_player/vs_team during init is not supported by the current library version used.
    Returns dictionary containing a list of games (limited by MAX_GAMES_TO_RETURN).
    """
    logger.info(f"Executing fetch_league_games_logic with params: player/team={player_or_team_abbreviation}, player_id={player_id_nullable}, team_id={team_id_nullable}, season={season_nullable}, type={season_type_nullable}, league={league_id_nullable}, date_from={date_from_nullable}, date_to={date_to_nullable}")

    # Basic validation
    if player_or_team_abbreviation not in ['P', 'T']:
        return {"error": "Invalid player_or_team_abbreviation. Use 'P' for Player or 'T' for Team."}
    if player_or_team_abbreviation == 'P' and player_id_nullable is None:
         return {"error": "player_id_nullable is required when searching by player ('P')."}
    if player_or_team_abbreviation == 'T' and team_id_nullable is None:
         return {"error": "team_id_nullable is required when searching by team ('T')."}

    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            player_or_team_abbreviation=player_or_team_abbreviation,
            player_id_nullable=player_id_nullable,
            team_id_nullable=team_id_nullable,
            season_nullable=season_nullable,
            season_type_nullable=season_type_nullable,
            league_id_nullable=league_id_nullable,
            date_from_nullable=date_from_nullable,
            date_to_nullable=date_to_nullable,
            timeout=DEFAULT_TIMEOUT
        )
        logger.debug("LeagueGameFinder API call successful.")

        # Process the dataframe but limit the results
        games_df = game_finder.league_game_finder_results.get_data_frame()
        total_games_found = len(games_df) if games_df is not None else 0

        if games_df is None or games_df.empty:
             games_list = []
        else:
             # Sort by date descending (most recent first) and take the top N
             games_df_sorted = games_df.sort_values(by='GAME_DATE', ascending=False)
             games_df_limited = games_df_sorted.head(MAX_GAMES_TO_RETURN)
             games_list = _process_dataframe(games_df_limited, single_row=False)

        if games_list is None: # Check if _process_dataframe failed
            logger.error("DataFrame processing failed for LeagueGameFinder results.")
            return {"error": "Failed to process game finder data from API."}

        result = {
            "total_games_found": total_games_found,
            "games_returned": len(games_list),
            "games": games_list # Return the limited list
        }
        logger.info(f"fetch_league_games_logic completed. Found {total_games_found} games, returning {len(games_list)}.")
        return result

    except Exception as e:
        logger.critical(f"Unexpected error in fetch_league_games_logic: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred processing the game finder request: {str(e)}"}

# Example Usage Block
if __name__ == "__main__":
    try:
        from player_tools import _find_player_id
        from team_tools import _find_team_id
    except ImportError:
        logger.warning("Could not import helpers directly, direct execution tests might fail.")
        _find_player_id = lambda x: (None, None)
        _find_team_id = lambda x: None

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("\n--- Running Game Tool Logic Examples ---")

    # Find LeBron's games (limited)
    lebron_id_test, _ = _find_player_id("LeBron James")
    if lebron_id_test:
        print("\n[Test Case: LeBron Games (Limited)]")
        games_str = fetch_league_games_logic(player_id_nullable=lebron_id_test, player_or_team_abbreviation='P')
        games_data = json.loads(games_str)
        if 'games' in games_data:
            print(f"Found {games_data.get('total_games_found', 'N/A')} games, returned {games_data.get('games_returned', 'N/A')}.")
        else:
            print(games_data)
        assert 'error' not in games_data
    else:
         print("Skipping LeBron games test - could not find player ID.")


    # Find Lakers games (limited)
    lakers_id_test = _find_team_id("LAL")
    if lakers_id_test:
        print("\n[Test Case: Lakers Games (Limited)]")
        games_str = fetch_league_games_logic(team_id_nullable=lakers_id_test, player_or_team_abbreviation='T')
        games_data = json.loads(games_str)
        if 'games' in games_data:
             print(f"Found {games_data.get('total_games_found', 'N/A')} games, returned {games_data.get('games_returned', 'N/A')}.")
        else:
            print(games_data)
        assert 'error' not in games_data
    else:
        print("Skipping Lakers games test - could not find team ID.")

    print("\n--- Game Tool Examples Complete ---")