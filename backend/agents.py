import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage

from .tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games
from .config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE

# Load environment variables
load_dotenv()

storage = SqliteAgentStorage(table_name="agent_sessions", db_file=STORAGE_DB_FILE)

analysis_agent = Agent(
    name="NBA Analyst Agent",
    model=Gemini(id=AGENT_MODEL_ID),
    description="An AI agent specialized in analyzing NBA data and providing insights.",
    instructions=[
        "You receive structured NBA data, potentially as a JSON string.",
        "If the input data is wrapped (e.g., {'result': '<escaped_json>'}), parse the outer structure, extract the inner JSON string, then parse that.",
        "If the input data is direct JSON, parse it directly.",
        "Analyze the data based on the user's request.",
        "Provide insights clearly, using markdown formatting.",
        "Do not fetch external data unless explicitly given a tool.",
        "If asked to predict, base it strictly on provided data and state limitations.",
        "If the data is an error message or invalid, state that analysis cannot be performed."
    ],
    tools=[get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games],
    storage=storage,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
    debug_mode=AGENT_DEBUG_MODE,
)

data_aggregator_agent = Agent(
    name="NBA Data Aggregator Agent",
    model=Gemini(id=AGENT_MODEL_ID),
    description="Fetches NBA data from APIs based on requests.",
    instructions=[
        "Receive requests for NBA data.",
        "Determine the correct tool to use.",
        "Extract parameters for the tool.",
        "Execute the tool and return ONLY the raw JSON string.",
        "If parameters are missing or invalid, return an error message."
    ],
    tools=[get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games],
    storage=storage,
    add_history_to_messages=True,
    num_history_responses=5,
    debug_mode=AGENT_DEBUG_MODE,
)
