# backend/workflows/research.py
import json
from textwrap import dedent
from typing import Dict, AsyncIterator, Optional
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
        8. Ensure the final report adheres strictly to the expected format.
        9. List the tools that were *likely* used to gather the data (provided in the input or inferred) in the 'Data Sources Used' section.
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

    async def arun(self, topic: str) -> AsyncIterator[RunEvent]:
        """Orchestrates the research process: gather data, then write report."""
        
        # Step 1: Gather Data (Stream intermediate steps)
        logger.info(f"Workflow Step 1: Gathering data for topic: {topic}")
        gathered_data_content = ""
        # Await the agent call to get the async iterator
        data_gatherer_iterator = await self.data_gatherer.arun(topic, stream=True, stream_intermediate_steps=True)
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