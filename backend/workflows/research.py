# backend/workflows/research.py
import json
from textwrap import dedent
from typing import Dict, AsyncIterator, Optional, List
import logging

from agno.agent import Agent
from agno.models.google import Gemini # Assuming Gemini model
from agno.storage.workflow.sqlite import SqliteWorkflowStorage
from agno.workflow import RunEvent, RunResponse, Workflow

# Import agent tools and configurations (adjust path if needed)
from backend.agents import nba_tools, model, CURRENT_SEASON, AGENT_DEBUG_MODE, current_date

# --- Initialize logger ---
logger = logging.getLogger(__name__)

# Define the Data Gathering Agent Configuration
# (Focuses on tool use, less on strict output format)
# Note: We might not need 'expected_output' here if its raw output is processed by the next agent.
data_gathering_agent = Agent(
    name="NBADataGatherer",
    model=model,
    tools=nba_tools,
    description=dedent(f"""
        You are an efficient NBA data retrieval specialist. 
        Your goal is to use the available tools to gather all relevant 
        statistics and information based on the research topic provided. 
        Focus on comprehensive data collection.
        Current context: Date {current_date}, Season {CURRENT_SEASON}.
        """),
    instructions=dedent("""
        1. Analyze the user's research topic to understand the core entities (players, teams, games) and data points required.
        2. Plan the sequence of tool calls needed to gather the necessary information.
        3. Execute the tool calls methodically. Call multiple tools if needed for a complete picture (e.g., get player info first, then stats).
        4. Output the raw or slightly summarized results from the tool calls.
        """),
    # No strict 'expected_output' needed here, maybe just basic markdown or JSON aggregation?
    markdown=True, # Keep markdown for readability of potential summaries
    show_tool_calls=True, # Show tool calls for debugging
    debug_mode=AGENT_DEBUG_MODE,
    stream=True, # Enable streaming for intermediate steps
    stream_intermediate_steps=True,
    resolve_context=True,
    reasoning=True,
    exponential_backoff=True,
    delay_between_retries=2
)

# Define the Report Writing Agent Configuration
# (Takes gathered data, synthesizes, and formats the final report)
report_writer_agent = Agent(
    name="NBAReportWriter",
    model=model,
    # This agent likely doesn't need direct tool access if it gets all data from the previous step
    # tools=[], 
    description=dedent(f"""
        You are a meticulous NBA Research Analyst and writer. Your expertise is in 
        synthesizing gathered data into clear, well-structured research reports. 
        You focus on accuracy, insightful analysis, and presenting data-driven insights 
        based on the provided information and the original research topic.
        Today's date is {current_date}. The current NBA season is {CURRENT_SEASON}.
        """),
    instructions=dedent("""
        1. Review the provided data dump and the original research topic.
        2. Synthesize the key findings and statistics.
        3. Analyze the synthesized data (e.g., season totals, comparisons if available) to identify trends or points suitable for visualization (like year-over-year point averages).
        4. Structure the information into a coherent report using the 'Expected Output' Markdown format.
        5. Write clear analysis and insights based *only* on the provided data.
        6. Embed key statistics as Stat Cards using `<!-- STAT_CARD_DATA {...} -->`.
        7. **If chartable data was identified in step 3 (like PPG over multiple seasons), generate appropriate `CHART_DATA` comments.** 
           **- CRITICAL FORMATTING:** Use the exact JSON structure below:
           **- For time-series (e.g., stats over seasons):** `<!-- CHART_DATA {"type": "line", "title": "Your Chart Title", "data": [{"label": "SEASON_YEAR", "value": STAT_VALUE}, ...]} -->` 
           **- For comparisons (e.g., multiple players):** `<!-- CHART_DATA {"type": "bar", "title": "Your Chart Title", "data": [{"label": "CATEGORY_NAME", "value": STAT_VALUE}, ...]} -->`
           **- Replace `SEASON_YEAR`, `STAT_VALUE`, `CATEGORY_NAME`, etc. with the actual data. Ensure keys are exactly "label" and "value" in the data array.**
        8. **For any data best presented as a table (e.g., lists of stats, comparisons), enclose the raw Markdown table within a `TABLE_DATA` comment like this:** `<!-- TABLE_DATA {"title": "Optional Table Title", "markdown": "YOUR MARKDOWN TABLE HERE"} -->`
        9. Ensure the final report adheres strictly to the expected format.
        10. List the tools that were *likely* used to gather the data (provided in the input or inferred) in the 'Data Sources Used' section.
        """),
    expected_output=dedent(f"""
        A professional NBA research report in markdown format:

        # Research Report: {{Concise Title Reflecting the Research Topic}}

        ## 1. Research Topic Summary
        {{Briefly restate the user's original research request or topic.}}

        ## 2. Key Findings & Data
        {{Present the main data points and findings synthesized from the input data. Use subheadings and tables. Embed Stat Cards and Charts using comments as instructed.}}

        ## 3. Analysis & Insights
        {{Analyze the synthesized data. Compare statistics, identify trends. Provide context.}}

        ## 4. Conclusion
        {{Summarize the main conclusions.}} 

        ## 5. Data Sources Used
        {{List the primary tool_names used by the data gathering step (e.g., - get_player_career_stats).}}

        ---
        Report Generated: {current_date}
        """),
    markdown=True,
    show_tool_calls=False, # Doesn't call tools directly
    debug_mode=AGENT_DEBUG_MODE,
    stream=True, # Stream the final report generation
    stream_intermediate_steps=False, # Less relevant if not calling tools
    resolve_context=False, # Gets context via input
    reasoning=True, # Needs reasoning for synthesis
    exponential_backoff=True,
    delay_between_retries=2
)


# Define the Research Workflow
class ResearchWorkflow(Workflow):
    data_gatherer: Agent = data_gathering_agent
    report_writer: Agent = report_writer_agent

    async def arun(self, topic: str, selected_sections: Optional[List[str]] = None) -> AsyncIterator[RunEvent]:
        """Orchestrates the research process based on selected sections."""
        
        # Construct instructions for data gatherer based on selected sections
        section_mapping = { # Map section ID to a descriptive phrase for the prompt
            'basic': 'basic player information (team, position, draft info)',
            'career_stats': 'career statistics (totals and per-season)',
            'current_stats': 'current season aggregate statistics',
            'gamelog': 'current season game logs',
            'awards': 'player awards and accolades',
            'profile': 'player profile details (career/season highs)',
            'hustle': 'hustle statistics (deflections, loose balls, etc.)',
            'defense': 'detailed defensive statistics',
            'shooting': 'shot chart details and shooting splits',
            'passing': 'detailed passing statistics',
            'rebounding': 'detailed rebounding statistics',
            'clutch': 'clutch time statistics',
            'analysis': 'year-over-year analysis (if applicable data is found)',
            'insights': 'general player insights or dashboards'
        }
        
        # Use default sections if none provided or list is empty
        if not selected_sections:
            selected_sections = ['basic', 'career_stats', 'current_stats'] # Default sections
            logger.warning(f"No sections selected or list empty, using defaults: {selected_sections}")
        
        requested_data_desc = ", ".join([section_mapping.get(s_id, s_id) for s_id in selected_sections])
        
        gatherer_instructions = dedent(f"""
            1. Analyze the user's research topic: '{topic}'
            2. The user wants data specifically for these aspects: **{requested_data_desc}**.
            3. Plan the sequence of tool calls *only* needed to gather the information for the requested aspects. Do not call tools for unrequested data.
            4. Execute the planned tool calls methodically.
            5. Output the raw or slightly summarized results from the tool calls.
            """)
        
        # Step 1: Gather Data (Stream intermediate steps)
        logger.info(f"Workflow Step 1: Gathering data for topic: {topic}, Aspects: {requested_data_desc}")
        gathered_data_content = ""
        # Pass the tailored instructions to the data gatherer
        data_gatherer_iterator = await self.data_gatherer.arun(topic, instructions=gatherer_instructions, stream=True, stream_intermediate_steps=True)
        async for event in data_gatherer_iterator:
            yield event 
            if isinstance(event, RunResponse) and isinstance(event.content, str):
                gathered_data_content += event.content
        
        logger.info(f"Workflow Step 1 Completed. Gathered data length: {len(gathered_data_content)}")
        if not gathered_data_content:
             logger.warning("Data gathering step produced no content.")
             yield RunEvent(event="error", data={"type": "error", "content": "Data gathering failed to produce results."})
             return

        # Step 2: Write Report (Stream final report chunks)
        logger.info("Workflow Step 2: Writing report based on gathered data.")
        writer_input = f"Original Topic: {topic}\n\nGathered Data:\n---\n{gathered_data_content}\n---"

        # Await the agent call to get the async iterator
        report_writer_iterator = await self.report_writer.arun(writer_input, stream=True, stream_intermediate_steps=False)
        async for event in report_writer_iterator:
             yield event

        logger.info("Workflow Step 2 Completed. Report writing stream finished.")

# Example (Optional, for direct testing)
# if __name__ == "__main__":
#     import asyncio
#     workflow = ResearchWorkflow()
#     async def main():
#         async for event in workflow.arun("Deep dive on LeBron James career stats"):
#             print(event)
#     asyncio.run(main()) 