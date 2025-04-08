import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

# Import the new tools
from .tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games, get_player_awards, get_boxscore_traditional, get_league_standings, get_scoreboard, get_playbyplay, get_draft_history, get_league_leaders
from .config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE


# Initialize agents
model = Gemini(id=AGENT_MODEL_ID)

data_aggregator_agent = Agent(
    name="DataAggregator",
    model=model,
    tools=[
        get_player_info,
        get_player_gamelog,
        get_team_info_and_roster,
        get_player_career_stats,
        find_games,
        get_player_awards,
        get_boxscore_traditional,
        get_league_standings,
        get_scoreboard,
        get_playbyplay,
        get_draft_history,
        get_league_leaders # Add new tool here
    ],
    add_history_to_messages=True,
    num_history_responses=3,
)

analysis_agent = Agent(
    name="Analyst",
    model=model,
    tools=[
        get_player_info,
        get_player_gamelog,
        get_team_info_and_roster,
        get_player_career_stats,
        find_games,
        get_player_awards,
        get_boxscore_traditional,
        get_league_standings,
        get_scoreboard,
        get_playbyplay,
        get_draft_history,
        get_league_leaders # Add new tool here
    ],
    add_history_to_messages=True,
    num_history_responses=3,
)
