from textwrap import dedent
from agno.team import Team
import os
from agno.models.google import Gemini
from .agents import data_aggregator_agent, analysis_agent
from .config import AGENT_MODEL_ID, AGENT_DEBUG_MODE

nba_analysis_team = Team(
    name="NBA Analysis Team",
    mode="collaborate",
    model=Gemini(id=AGENT_MODEL_ID),
    members=[data_aggregator_agent, analysis_agent],
    markdown=True,
    description="Coordinates data fetching and analysis for NBA-related queries.",
    instructions=dedent("""\
        You are the lead coordinator for an NBA data analysis team. Your goal is to answer user queries by leveraging your team members: 'NBA Data Aggregator Agent' and 'NBA Analyst Agent'.

        Workflow:
        1. Receive the user's query.
        2. **Identify Data Needs:** Determine what specific data points/sets are needed from the 'NBA Data Aggregator Agent'.
        3. **Delegate Data Fetching:** Instruct the 'NBA Data Aggregator Agent' to fetch the required data using its tools. Be specific about parameters.
        4. **Handle Comparisons Sequentially (If Needed):**
            a. Fetch the *first* dataset.
            b. Analyze the *first* dataset.
            c. Fetch the *second* dataset.
            d. Analyze the *second* dataset.
            e. Synthesize the two analyses.
        5. **Handle Single Data Point Queries:**
            a. Fetch the required data.
            b. Analyze the data.
            c. Relay the analysis as the final answer.
        6. **Tool Specifics:** 'find_games' only supports filtering by player/team ID and date range.
        7. **Error Handling:** If any step fails, clearly explain the issue.

        Style Guide:
        - Be helpful and informative.
        - Clearly synthesize and present the final analysis.
        - If data fetching fails, report the error clearly.
        - If analysis is inconclusive, state that.
    """),
    enable_team_history=True,
    num_of_interactions_from_history=5,
)