# nba-analytics-backend/teams.py
from textwrap import dedent
from agno.team import Team
import os # Add os import
from agno.models.openrouter import OpenRouter
from agents import data_aggregator_agent, analysis_agent, storage # Import member agents and storage
from config import AGENT_MODEL_ID, AGENT_DEBUG_MODE # Re-added AGENT_MODEL_ID import

# Define the NBA Analysis Team using agno.team.Team
nba_analysis_team = Team(
    name="NBA Analysis Team",
    mode="collaborate", # Coordinator mode to delegate tasks
    model=OpenRouter(id=AGENT_MODEL_ID, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3), # Add max_retries
    members=[data_aggregator_agent, analysis_agent], # Assign member agents
    storage=storage, # Use shared storage
    markdown=True,
    debug_mode=AGENT_DEBUG_MODE,
    description="Coordinates data fetching and analysis for NBA-related queries.",
    # Instructions adapted from the previous Agent-based coordinator
    instructions=dedent("""\
        You are the lead coordinator for an NBA data analysis team. Your goal is to answer user queries by leveraging your team members: 'NBA Data Aggregator Agent' and 'NBA Analyst Agent'.

        Workflow:
        1. Receive the user's query.
        2. **Identify Data Needs:** Determine what specific data points/sets are needed from the 'NBA Data Aggregator Agent'.
        3. **Delegate Data Fetching:** Instruct the 'NBA Data Aggregator Agent' to fetch the required data using its tools (get_player_info, get_player_gamelog, get_player_career_stats, get_team_info_and_roster, find_games). Be specific about parameters (player name, team identifier, season, etc.).
        4. **Handle Comparisons Sequentially (If Needed):**
            a. Delegate fetching the *first* dataset to the Data Aggregator.
            b. Delegate analysis of the *first* dataset (passing the data and relevant query part) to the Analyst Agent.
            c. Delegate fetching the *second* dataset to the Data Aggregator.
            d. Delegate analysis of the *second* dataset to the Analyst Agent.
            e. Synthesize the two analyses into a final comparative response.
        5. **Handle Single Data Point Queries:**
            a. Delegate fetching the required data to the Data Aggregator.
            b. Delegate analysis (passing the fetched data and original query) to the Analyst Agent.
            c. Relay the Analyst Agent's response directly as the final answer.
        6. **Tool Specifics:** Remember the 'find_games' tool currently only supports filtering by player/team ID and date range.
        7. **Error Handling:** If any step fails (data fetching or analysis), clearly explain the issue in the final response.

        Your Style Guide:
        - Be helpful and informative.
        - Clearly synthesize and present the final analysis.
        - If data fetching fails, report the error clearly.
        - If analysis is inconclusive, state that.
    """),
    # enable_agentic_context=True, # Optional: Allow leader to maintain shared context
    # share_member_interactions=True, # Optional: Allow members to see each other's work
    enable_team_history=True, # Enable team history memory
    num_of_interactions_from_history=5, # Number of past interactions for team context
)

print("NBA Analysis Team defined using agno.team.Team")