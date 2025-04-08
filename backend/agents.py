import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

from .tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games
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
        find_games
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
        find_games
    ],
    add_history_to_messages=True,
    num_history_responses=3,
)
