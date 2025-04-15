from fastapi import APIRouter, HTTPException
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic

router = APIRouter()

@router.get("/scoreboard")
async def get_live_scoreboard():
    """
    Get live NBA scoreboard data including game scores, status, and game leaders.
    
    Returns:
        JSON containing:
        - game_date: Date of the games
        - games: List of game information including:
            - game_id: Unique identifier for the game
            - status: Current game status
            - period: Current period
            - game_clock: Current game clock
            - home_team: Home team information and score
            - away_team: Away team information and score
            - game_leaders: Statistical leaders for both teams
    """
    try:
        return fetch_league_scoreboard_logic()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching live scoreboard data: {str(e)}"
        )