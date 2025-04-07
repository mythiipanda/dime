# Placeholder for Agno Agent definitions
# This file will contain the definitions for agents like:
# - DataAggregatorAgent
# - DataNormalizerAgent
# - AnalysisAgent (using Gemini)
# - Potentially a Team or Workflow orchestrating these agents

import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openrouter import OpenRouter # Changed import
from tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games # Import find_games
# from agno.tools. ... import ... # Import necessary tools later
# from agno.knowledge. ... import ... # Import knowledge bases later
from agno.storage.agent.sqlite import SqliteAgentStorage # Using SQLite for initial dev
from config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE # Re-added AGENT_MODEL_ID import

# Load environment variables from .env file
load_dotenv()


storage = SqliteAgentStorage(table_name="agent_sessions", db_file=STORAGE_DB_FILE) # Use config value
storage = SqliteAgentStorage(table_name="agent_sessions", db_file="agno_storage.db") # Simple local storage for now

analysis_agent = Agent(
    name="NBA Analyst Agent",
    model=OpenRouter(id=AGENT_MODEL_ID, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3), # Add max_retries
    description="An AI agent specialized in analyzing NBA data (like stats, trends, comparisons) and providing clear, concise insights.",
    instructions=[
        "You receive structured NBA data, potentially as a JSON string.",
        # NOTE: When receiving data from DataAggregatorAgent via the NBAnalysisTeam coordinator,
        #       the data might be implicitly wrapped by the Agno framework (e.g., in a {'result': '<escaped_json>'} structure),
        #       even if the DataAggregatorAgent was instructed to return only the raw JSON string.
        #       Therefore, you must handle this potential wrapping as the first step.
        "**CRITICAL FIRST STEP:** Check if the input data string looks like a wrapped structure (e.g., `{\"result\": \"...\"}`). If it does, you MUST parse the outer structure, extract the inner JSON string (likely from the 'result' field), and then parse that inner string to get the actual data dictionary/list.",
        "If the input data string appears to be a direct JSON representation of a dictionary or list (not wrapped), parse it directly.",
        "Once you have the actual data dictionary/list, analyze it based on the user's request (e.g., compare players, explain a team's performance, identify trends).",
        "Provide insights in a clear, easy-to-understand manner.",
        "Use markdown for formatting responses, including tables or lists where appropriate.",
        "Focus solely on interpreting the provided data; do not fetch external data unless explicitly given a tool to do so.",
        "If asked to predict, base it strictly on the provided historical data and state the limitations.",
        "If the provided data is an error message (e.g., {'error': '...'}) or if you cannot extract valid data after attempting the steps above, state that you could not perform the analysis due to missing or invalid data.",
    ],
    tools=[get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games], # Add data tools
    # knowledge=None, # No external knowledge base initially
    storage=storage, # Persist sessions locally
    add_history_to_messages=True, # Enable chat history memory
    num_history_responses=5,      # Number of past messages to include
    markdown=True,
    debug_mode=AGENT_DEBUG_MODE, # Use config value
)

data_aggregator_agent = Agent(
    name="NBA Data Aggregator Agent",
    model=OpenRouter(id=AGENT_MODEL_ID, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3), # Add max_retries
    description="An agent responsible for fetching data from various NBA APIs based on requests.",
    instructions=[
        "Receive requests for specific NBA data.",
        "Analyze the request to determine the correct tool to use (get_player_info, get_player_gamelog, get_player_career_stats, get_team_info_and_roster, find_games).",
        "Extract the necessary parameters for the chosen tool from the request.",
        "For get_player_info, get_player_gamelog, get_player_career_stats: Extract player_name. Also extract season/season_type for gamelog, and per_mode36 for career stats if specified.",
        "For get_team_info_and_roster: Extract team_identifier (name or abbreviation) and optional season.",
        "For find_games: Determine if the request is for a player ('P') or team ('T'). Extract the player name or team identifier (name/abbreviation) and pass it as the 'identifier' parameter. Set 'player_or_team' to 'P' or 'T' accordingly. Date/Season/League filters are NOT currently supported by this tool.", # Updated find_games instruction
        "Execute the chosen tool with the extracted parameters.",
        # NOTE: Despite the critical instruction below, when this agent's string output is passed
        #       to another agent within an Agno Team workflow (coordinated by NBAnalysisTeam),
        #       the framework might implicitly wrap it (e.g., {'result': '<escaped_json>'}).
        #       The receiving agent (AnalysisAgent) is instructed to handle this potential wrapping.
        "CRITICAL INSTRUCTION: Your final response MUST be *only* the raw JSON string returned directly by the tool. Do not add *any* surrounding text, markdown, or explanation. Just output the JSON string.",
        "If the request cannot be mapped to an available tool or parameters are missing/invalid, respond with a clear error message stating the issue.",
    ],
    tools=[get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats, find_games], # Add find_games
    storage=storage,
    add_history_to_messages=True, # Enable chat history memory
    num_history_responses=5,      # Number of past messages to include
    # response_model=str, # Removed as it caused issues with OpenRouter/structured output check
    debug_mode=AGENT_DEBUG_MODE, # Use config value
)

# TODO: DataNormalizerAgent - Defined but currently unused.
# The corresponding API endpoint (/normalize_data in main.py) is commented out.
# This agent was previously reported to cause an ImportError when imported elsewhere,
# likely due to missing dependencies or incomplete implementation.
# Needs further investigation and implementation if data normalization is required.
data_normalizer_agent = Agent(
    name="NBA Data Normalizer Agent",
    model=OpenRouter(id=AGENT_MODEL_ID), # Use config value
    description="An agent responsible for transforming raw data from various NBA APIs into a standardized project schema.",
    instructions=[
        "Receive raw data chunks from different API sources.",
        "Identify the source and structure of the incoming data.",
        "Map the raw data fields to the predefined standard schema for players, teams, games, stats, etc.",
        "Handle missing fields or inconsistencies gracefully, potentially flagging them.",
        "Ensure data types are consistent (e.g., dates, numbers).",
        "Output the data in the standardized JSON format.",
    ],
    # tools=[], # Likely no external tools needed initially
    storage=storage,
    debug_mode=AGENT_DEBUG_MODE, # Use config value
)

# print("AnalysisAgent, DataAggregatorAgent, and DataNormalizerAgent defined.") # Keep console clean