"""Routes for the NBA agent backend."""

from .analyze import analyze_player_stats
from .game import get_game_boxscore, get_game_playbyplay, get_game_shotchart
from .player import fetch_player_stats, fetch_player_info
from .team import fetch_team_stats, fetch_team_info
from .player_tracking import fetch_player_tracking_stats
from .team_tracking import fetch_team_tracking_stats
from .sse import ask_agent_keepalive_sse, test_agent_stream
from .fetch import fetch_data 