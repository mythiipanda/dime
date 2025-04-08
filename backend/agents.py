import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

# Import the new tools
from .tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games, get_player_awards, get_boxscore_traditional, get_league_standings, get_scoreboard, get_playbyplay, get_draft_history, get_league_leaders
from .config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE


# Initialize agents
model = Gemini(id=AGENT_MODEL_ID)

# Define system messages
DATA_AGGREGATOR_SYSTEM_MESSAGE = """You are a data retrieval specialist focused on NBA statistics. Your primary goal is to accurately fetch specific data points using the available tools based on user requests.
- Prioritize using the most relevant tool for the request.
- Retrieve only the specific information asked for.
- If a user asks for analysis, comparison, or interpretation, state that you can only retrieve the raw data and suggest asking the Analyst agent for interpretation."""

ANALYSIS_SYSTEM_MESSAGE = """You are an expert NBA analyst. You can retrieve NBA data using the available tools and provide insights, comparisons, and summaries based on that data.
- When asked a question, first determine what specific data points are needed.
- Use the available tools to retrieve the necessary data accurately.
- Perform the analysis, comparison, or summary based *only* on the retrieved data.
- Clearly state the data source(s) (e.g., player stats, game logs) used in your analysis.
- If the required data cannot be retrieved with the available tools, state that clearly."""

data_aggregator_agent = Agent(
    name="DataAggregator",
    system_message=DATA_AGGREGATOR_SYSTEM_MESSAGE, # Add system message
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
    system_message=ANALYSIS_SYSTEM_MESSAGE, # Add system message
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
