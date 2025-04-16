import logging
import json
from typing import Dict, List, Optional, Any
from datetime import date, timedelta
from nba_api.live.nba.endpoints import ScoreBoard
from backend.utils.cache import cache_data, get_cached_data
from backend.api_tools.utils import format_response, validate_date_format
from backend.api_tools.league_tools import fetch_scoreboard_logic

logger = logging.getLogger(__name__)

def fetch_scoreboard_data_logic(game_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches NBA scoreboard data for a specific date (YYYY-MM-DD).
    Uses the live endpoint for today's date and the static ScoreboardV2 for past/future dates.

    Args:
        game_date (Optional[str]): The date for the scoreboard (YYYY-MM-DD). 
                                   Defaults to today if None.

    Returns:
        Dict[str, Any]: A dictionary containing scoreboard data or an error.
    """
    today_str = date.today().strftime('%Y-%m-%d')
    target_date_str = game_date

    # Default to today if no date provided
    if target_date_str is None:
        target_date_str = today_str
        logger.debug("No game date provided, defaulting to today: %s", target_date_str)
    
    # Validate date format if provided
    if game_date and not validate_date_format(target_date_str):
         logger.error("Invalid date format provided: %s. Use YYYY-MM-DD.", target_date_str)
         return {"error": f"Invalid date format: {target_date_str}. Use YYYY-MM-DD."}

    # Determine cache key based on date
    cache_key = f"scoreboard_{target_date_str}"
    # Use shorter TTL for today's live data
    ttl = 60 if target_date_str == today_str else 3600 * 24 # Cache non-today dates for 24h

    cached_result = get_cached_data(cache_key)
    if cached_result:
        logger.debug(f"Returning cached scoreboard data for {target_date_str}.")
        try:
            return json.loads(cached_result)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode cached scoreboard data for {target_date_str}.")
            # Fall through

    logger.debug(f"Fetching fresh scoreboard data for {target_date_str}.")
    
    try:
        result_data: Optional[Dict[str, Any]] = None

        if target_date_str == today_str:
            logger.info("Fetching live scoreboard data for today.")
            scoreboard_endpoint = ScoreBoard()
            data = scoreboard_endpoint.get_dict()
            if 'scoreboard' in data and 'games' in data['scoreboard']:
                result_data = {
                    "gameDate": data['scoreboard'].get('gameDate', target_date_str),
                    "games": data['scoreboard'].get('games', []) # Default to empty list
                }
            else:
                 logger.warning("Live scoreboard data format unexpected for today.")
                 return {"error": "Live scoreboard data format unexpected."}
        else:
            # Use static endpoint logic for past/future dates
            logger.info(f"Fetching static scoreboard data for {target_date_str} using ScoreboardV2 logic.")
            scoreboard_json = fetch_scoreboard_logic(game_date=target_date_str)
            try:
                raw_data = json.loads(scoreboard_json)
                if "error" in raw_data:
                    logger.error(f"Error received from fetch_scoreboard_logic for {target_date_str}: {raw_data['error']}")
                    return raw_data
                
                games = []
                # Check if necessary data keys exist
                if "GameHeader" in raw_data and "LineScore" in raw_data:
                    game_headers = {g['GAME_ID']: g for g in raw_data.get("GameHeader", [])}
                    line_scores_by_game = {}

                    # Group line scores by game_id and team (home/away)
                    for ls in raw_data.get("LineScore", []):
                        game_id = ls.get('GAME_ID')
                        team_id = ls.get('TEAM_ID')
                        header = game_headers.get(game_id)
                        
                        if not game_id or not team_id or not header: continue # Skip if essential IDs missing

                        if game_id not in line_scores_by_game:
                            line_scores_by_game[game_id] = {}
                        
                        # Determine if home or away based on header
                        team_key = 'homeTeam' if team_id == header.get('HOME_TEAM_ID') else 'awayTeam'
                        
                        # Parse wins/losses safely
                        wins, losses = None, None
                        wl_record = ls.get('TEAM_WINS_LOSSES')
                        if wl_record and '-' in wl_record:
                            try:
                                parts = wl_record.split('-')
                                wins = int(parts[0])
                                losses = int(parts[1])
                            except (ValueError, IndexError):
                                logger.warning(f"Could not parse W/L record '{wl_record}' for team {team_id} game {game_id}")
                        
                        line_scores_by_game[game_id][team_key] = {
                             "teamId": team_id,
                             "teamTricode": ls.get('TEAM_ABBREVIATION'),
                             "score": ls.get('PTS'),
                             "wins": wins,
                             "losses": losses
                        }

                    # Construct the final game list
                    for game_id, header in game_headers.items():
                        game_line_scores = line_scores_by_game.get(game_id, {})
                        home_team_data = game_line_scores.get('homeTeam')
                        away_team_data = game_line_scores.get('awayTeam')
                        
                        # Only add game if both teams have line score data
                        if home_team_data and away_team_data:
                            game_info = {
                                "gameId": game_id,
                                "gameStatus": header.get('GAME_STATUS_ID'), 
                                "gameStatusText": header.get('GAME_STATUS_TEXT'),
                                "period": header.get('LIVE_PERIOD'), # May be null for past/future
                                "gameClock": header.get('LIVE_PC_TIME'), # May be null for past/future
                                "homeTeam": home_team_data,
                                "awayTeam": away_team_data,
                                # Use GAME_DATE_EST which should always be present in V2 header
                                "gameEt": header.get('GAME_DATE_EST') 
                            }
                            games.append(game_info)
                        else:
                            logger.warning(f"Missing home/away team line score data for game {game_id} in ScoreboardV2 response. Skipping game.")
                    
                    logger.info(f"Successfully processed {len(games)} games from ScoreboardV2 data for {target_date_str}.")
                else:
                    logger.warning(f"Missing 'GameHeader' or 'LineScore' in ScoreboardV2 response for {target_date_str}. Cannot process games.")

                result_data = {
                     "gameDate": target_date_str,
                     "games": games
                }
                
            except json.JSONDecodeError:
                 logger.error(f"Failed to decode scoreboard response for {target_date_str}.")
                 return {"error": "Failed to parse scoreboard data from backend."}
            except Exception as parse_err:
                 logger.exception(f"Error processing ScoreboardV2 data for {target_date_str}: {parse_err}", exc_info=True)
                 return {"error": f"Error processing scoreboard data: {str(parse_err)}"}
        
        # If we got data, cache and return it
        if result_data is not None:
            cache_data(cache_key, json.dumps(result_data), ttl=ttl)
            logger.info(f"Successfully fetched and processed scoreboard for {target_date_str}.")
            return result_data
        else:
             # Should have returned earlier if specific error occurred
             return {"error": "Unknown error fetching scoreboard data."}

    except Exception as e:
        logger.exception(f"Error fetching scoreboard data for {target_date_str}: {e}", exc_info=True)
        return {"error": f"Failed to fetch scoreboard data: {str(e)}"}

# Keep the old function name for now if it's imported elsewhere directly,
# but ideally refactor imports to use the new name.
fetch_live_scoreboard_logic = fetch_scoreboard_data_logic 

# Example of how format_response might be used if needed elsewhere, 
# but the logic function itself returns a dict here.
# def fetch_live_scoreboard_logic_formatted() -> str:
#     result_dict = fetch_live_scoreboard_logic()
#     return format_response(data=result_dict) # format_response handles error key and JSON conversion 