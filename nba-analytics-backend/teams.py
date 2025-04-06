import logging
from textwrap import dedent
from agno.agent import Agent
from agno.models.google import Gemini # Use Gemini for the lead agent too

# Import the sub-agents
from agents import data_aggregator_agent, analysis_agent, storage
from config import AGENT_MODEL_ID # Import model ID from config

logger = logging.getLogger(__name__)

# Define the Lead Agent (Team Coordinator)
NBAnalysisTeam = Agent(
    name="NBA Analysis Team Lead",
    model=Gemini(id=AGENT_MODEL_ID), # Use configured model ID
    team=[data_aggregator_agent, analysis_agent], # Define the team members
    description="Coordinates data fetching and analysis for NBA-related queries.",
    instructions=dedent("""\
        You are the lead coordinator for an NBA data analysis team. Your goal is to answer user queries by leveraging your team members.

        Workflow:
        1. Receive the user's query.
        2. **Identify Data Needs:** Determine what specific data points/sets are needed.
        3. **Handle Comparisons Sequentially:** If the query requires comparing two datasets (e.g., career stats per game vs. totals):
            a. Instruct the 'NBA Data Aggregator Agent' to fetch the *first* dataset.
            b. Pass the *first* dataset and the relevant part of the query to the 'NBA Analyst Agent' for initial analysis.
            c. Instruct the 'NBA Data Aggregator Agent' to fetch the *second* dataset.
            d. Pass the *second* dataset and the relevant part of the query to the 'NBA Analyst Agent' for its analysis.
            e. Synthesize the two analyses from the 'NBA Analyst Agent' into a final comparative response for the user.
        4. **Handle Single Data Point Queries:** If the query needs only one dataset:
            a. Instruct the 'NBA Data Aggregator Agent' to fetch the required data.
            b. Pass the fetched data and the original query to the 'NBA Analyst Agent'.
            c. Relay the 'NBA Analyst Agent's response directly to the user.
        5. **Tool Specifics:** Remember the 'find_games' tool currently only supports filtering by player/team ID and date range.
        6. **Error Handling:** If any step fails (data fetching or analysis), clearly explain the issue to the user.

        Your Style Guide:
        - Be helpful and informative.
        - Clearly synthesize and present the final analysis.
        - If data fetching fails, report the error clearly.
        - If analysis is inconclusive, state that.
    """), # Added closing triple quote and parenthesis
    storage=storage, # Use the same storage for session persistence
    markdown=True,
    debug_mode=True, # Enable debug for development
    # The lead agent typically doesn't need tools itself, it delegates
) # Added closing parenthesis for Agent constructor

logger.info("NBAnalysisTeam defined.")

# Example usage (for direct testing if needed)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    print("Testing NBAnalysisTeam directly...")
    # Example prompt requiring data fetching then analysis
    test_prompt = "What were Stephen Curry's per game stats for his 2023-24 season according to his game log, and how did that compare to his career average?"
    print(f"Running prompt: {test_prompt}")
    try:
        # Use sync run for direct script test
        response = NBAnalysisTeam.run(test_prompt)
        print("\n--- Team Response ---")
        # Accessing response might still require history inspection based on previous issues
        final_content = None
        if hasattr(response, 'messages') and response.messages:
            last_message = response.messages[-1]
            if last_message.role == 'assistant':
                final_content = last_message.content
        if final_content is None:
            final_content = getattr(response, 'response', 'No response attribute found.')

        print(final_content)
        print("--------------------")
    except Exception as e:
        print(f"Error running team directly: {e}")
        logger.exception("Error during direct team run")