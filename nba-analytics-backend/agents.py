# Placeholder for Agno Agent definitions
# This file will contain the definitions for agents like:
# - DataAggregatorAgent
# - DataNormalizerAgent
# - AnalysisAgent (using Gemini)
# - Potentially a Team or Workflow orchestrating these agents

import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from tools import get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats # Import new tool
# from agno.tools. ... import ... # Import necessary tools later
# from agno.knowledge. ... import ... # Import knowledge bases later
from agno.storage.agent.sqlite import SqliteAgentStorage # Using SQLite for initial dev

# Load environment variables from .env file
load_dotenv()

# Example Placeholder (will be refined based on specific tasks)
# Ensure GOOGLE_API_KEY is loaded before initializing Gemini
# The Gemini model in Agno likely uses the google-generativeai library,
# which automatically looks for the GOOGLE_API_KEY environment variable.
storage = SqliteAgentStorage(table_name="agent_sessions", db_file="agno_storage.db") # Simple local storage for now

analysis_agent = Agent(
    name="NBA Analyst Agent",
    model=Gemini(id="gemini-2.0-flash"), # Using Gemini 2.0 Flash as requested
    description="An AI agent specialized in analyzing NBA data (like stats, trends, comparisons) and providing clear, concise insights.",
    instructions=[
        "You receive structured NBA data (e.g., player stats, team stats, game logs).",
        "Analyze the data based on the user's request (e.g., compare players, explain a team's performance, identify trends).",
        "Provide insights in a clear, easy-to-understand manner.",
        "Use markdown for formatting responses, including tables or lists where appropriate.",
        "Focus solely on interpreting the provided data; do not fetch external data unless explicitly given a tool to do so.",
        "If asked to predict, base it strictly on the provided historical data and state the limitations.",
    ],
    # tools=[], # No external tools for analysis initially
    # knowledge=None, # No external knowledge base initially
    storage=storage, # Persist sessions locally
    markdown=True,
    debug_mode=True, # Enable for development
)

data_aggregator_agent = Agent(
    name="NBA Data Aggregator Agent",
    model=Gemini(id="gemini-2.0-flash"), # Assign model to potentially help tool routing/execution
    description="An agent responsible for fetching data from various NBA APIs based on requests.",
    instructions=[
        "Receive requests for specific NBA data.",
        "Analyze the request to determine the data type needed (player info, player gamelog, player career stats, team info/roster).",
        "If the request is for basic player information, use the 'get_player_info' tool with the player's full name.",
        "If the request is for a player's game log, use the 'get_player_gamelog' tool with the player's full name, the season (e.g., '2023-24'), and optionally the season_type ('Regular Season', 'Playoffs', etc.).",
        "If the request is for a player's career stats, use the 'get_player_career_stats' tool with the player's full name and optionally the per_mode ('PerGame', 'Totals', 'Per36', etc.).",
        "If the request is for team information or roster, use the 'get_team_info_and_roster' tool with the team's full name or abbreviation and optionally the season.",
        "If the request is for other data types, state that you cannot fulfill the request with current capabilities.",
        "Handle potential errors reported by the tools gracefully.",
        "Return the structured data dictionary obtained from the tool, or an error dictionary if applicable.",
    ],
    tools=[get_player_info, get_player_gamelog, get_team_info_and_roster, get_player_career_stats], # Add the new tool
    storage=storage,
    debug_mode=True,
)

data_normalizer_agent = Agent(
    name="NBA Data Normalizer Agent",
    # model=None, # Likely no LLM needed for schema mapping logic
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
    debug_mode=True,
)

# print("AnalysisAgent, DataAggregatorAgent, and DataNormalizerAgent defined.") # Keep console clean