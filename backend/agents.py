import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

# Import the new tools
from .tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games, get_player_awards, get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors, get_league_standings, get_scoreboard, get_playbyplay, get_draft_history, get_league_leaders # Added get_boxscore_fourfactors
from .config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE


# Initialize agents
model = Gemini(id=AGENT_MODEL_ID)

# Define a single system message for the combined agent
NBA_AGENT_SYSTEM_MESSAGE = """You are an expert NBA data analyst and retrieval specialist. Your goal is to accurately answer user questions about NBA statistics.
- Use the available tools to fetch the necessary data.
- If analysis, comparison, or summarization is requested, perform it based *only* on the retrieved data.
- Clearly state the data source(s) used.
- If a request requires data not available through the tools, state that clearly.
- Prioritize using tools to find information like game IDs before asking the user."""

# Define the single agent
nba_agent = Agent(
    name="NBAAgent",
    system_message=NBA_AGENT_SYSTEM_MESSAGE,
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
        get_league_leaders,
        get_boxscore_advanced,
        get_boxscore_fourfactors # Added new tool
    ],
    add_history_to_messages=True,
    num_history_responses=5, # Increase history slightly for better context
)

# Remove old agent definitions (or comment out)
# data_aggregator_agent = ...
# analysis_agent = ...
