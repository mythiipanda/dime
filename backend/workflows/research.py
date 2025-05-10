import json
from textwrap import dedent
from typing import Dict, AsyncIterator, Optional, List, Any
import logging
import hashlib 

from agno.agent import Agent
from agno.storage.sqlite import SqliteStorage 
from agno.workflow import RunEvent, RunResponse, Workflow 

from backend.agents import nba_tools, model as default_model, current_date 
from backend.config import Errors, CURRENT_SEASON, AGENT_DEBUG_MODE

logger = logging.getLogger(__name__)

# --- Agent Definitions ---
data_gathering_agent = Agent(
    name="NBADataGatherer",
    model=default_model, # Uses the model instance from agents.py
    tools=nba_tools,
    description=dedent(f"""
        You are an efficient NBA data retrieval specialist. 
        Your goal is to use the available tools to gather all relevant 
        statistics and information based on the research topic and specific aspects requested. 
        Focus on comprehensive and accurate data collection for ONLY the requested aspects.
        Current context: Date {current_date}, Season {CURRENT_SEASON}.
        """),
    markdown=True,
    show_tool_calls=True,
    debug_mode=AGENT_DEBUG_MODE,
    stream=True,
    stream_intermediate_steps=True,
    resolve_context=True,
    reasoning=True,
    exponential_backoff=True,
    delay_between_retries=3
)

report_writer_agent = Agent(
    name="NBAReportWriter",
    model=default_model, # Uses the model instance from agents.py
    description=dedent(f"""
        You are a meticulous NBA Research Analyst and writer. Your expertise is in 
        synthesizing gathered data into clear, well-structured research reports. 
        You focus on accuracy, insightful analysis, and presenting data-driven insights 
        based *only* on the provided information and the original research topic.
        Today's date is {current_date}. The current NBA season is {CURRENT_SEASON}.
        """),
    instructions=dedent("""
        1.  Review the provided "Original Topic" and "Gathered Data" dump carefully.
        2.  Synthesize the key findings and statistics relevant to the original topic from the "Gathered Data".
        3.  Analyze the synthesized data to identify trends, comparisons, or key data points suitable for emphasis.
        4.  Structure the information into a coherent report using the 'Expected Output' Markdown format provided below.
        5.  Write clear analysis and insights based *strictly* on the "Gathered Data". Do not infer or use external knowledge.
        6.  Embed key individual statistics as Stat Cards using the exact format: `<!-- STAT_CARD_DATA {{"label": "Statistic Name", "value": "Statistic Value", "unit": "(Optional Unit)"}} -->` on its own line.
        7.  If the "Gathered Data" contains clear time-series data (e.g., stats over multiple seasons for one player/team) or comparative data for a few entities on the same metric, embed this as Chart data using the exact format:
            - Time-series (line chart): `<!-- CHART_DATA {{"type": "line", "title": "Chart Title", "data": [{{"label": "SEASON_OR_DATE", "value": NUMERIC_STAT_VALUE}}, ...]}} -->`
            - Comparison (bar chart): `<!-- CHART_DATA {{"type": "bar", "title": "Chart Title", "data": [{{"label": "ENTITY_NAME", "value": NUMERIC_STAT_VALUE}}, ...]}} -->`
            Ensure "label" and "value" keys are used in the data array.
        8.  For tabular data (e.g., lists of player stats, game logs, multiple data points for comparison), present it as a Markdown table. Then, enclose the entire Markdown table within a `TABLE_DATA` comment: `<!-- TABLE_DATA {"title": "Optional Table Title", "markdown": "YOUR COMPLETE MARKDOWN TABLE HERE"} -->`. The markdown table itself should be well-formatted.
        9.  Ensure the final report adheres strictly to the expected output format, including all specified sections.
        10. In the 'Data Sources Used' section, list the primary `tool_name`s that were likely used to gather the data (this information might be part of the "Gathered Data" input or inferred from it).
        """),
    expected_output=dedent(f"""
        # Research Report: {{Concise Title Reflecting the Research Topic}}

        ## 1. Research Topic Summary
        {{Briefly restate the user's original research request or topic.}}

        ## 2. Key Findings & Data
        {{Present the main data points and findings synthesized from the input data. Use subheadings. Embed Stat Cards, Charts, and Markdown Tables (wrapped in TABLE_DATA comments) as instructed.}}

        ## 3. Analysis & Insights
        {{Analyze the synthesized data. Compare statistics, identify trends. Provide context. Base this *only* on the provided "Gathered Data".}}

        ## 4. Conclusion
        {{Summarize the main conclusions drawn from the analysis.}}

        ## 5. Data Sources Used
        {{List the primary tool_names that appear to have been used to generate the input data (e.g., - get_player_career_stats).}}

        ---
        Report Generated: {current_date}
        """),
    markdown=True,
    show_tool_calls=False,
    debug_mode=AGENT_DEBUG_MODE,
    stream=True,
    stream_intermediate_steps=False,
    resolve_context=False, # Report writer primarily synthesizes, less context resolution needed
    reasoning=True,
    exponential_backoff=True,
    delay_between_retries=3
)

# --- Research Workflow Definition ---
class ResearchWorkflow(Workflow):
    data_gatherer: Agent = data_gathering_agent
    report_writer: Agent = report_writer_agent

    def __init__(self, session_id: Optional[str] = None, storage: Optional[SqliteStorage] = None, **kwargs): 
        super().__init__(session_id=session_id, storage=storage, **kwargs)
        # self.session_state is initialized by the Workflow base class
        logger.info(f"ResearchWorkflow initialized. Session ID: {self.session_id}, Storage: {'Configured' if self.storage else 'None'}, Base SessionState: {'Available' if hasattr(self, 'session_state') and self.session_state is not None else 'Unavailable or Not Configured'}")

    def _generate_cache_key(self, topic: str, selected_sections: List[str]) -> str:
        key_string = f"{topic.lower().strip()}_{'_'.join(sorted(s.lower().strip() for s in selected_sections))}"
        return hashlib.md5(key_string.encode()).hexdigest()

    async def arun(self, topic: str, selected_sections: Optional[List[str]] = None) -> AsyncIterator[RunEvent]:
        if not selected_sections:
            selected_sections = ['basic', 'career_stats', 'current_stats']
        
        cache_key_base = self._generate_cache_key(topic, selected_sections)
        gathered_data_cache_key = f"research_gathered_data_{cache_key_base}"
        final_report_cache_key = f"research_final_report_{cache_key_base}"

        if self.session_state and self.session_state.get(final_report_cache_key):
            logger.info(f"Cache hit for final report: {final_report_cache_key} (Session ID: {self.session_id})")
            cached_report_content = self.session_state[final_report_cache_key]
            yield RunResponse(content=cached_report_content, event=RunEvent.workflow_completed)
            return

        gathered_data_content = ""
        if self.session_state and self.session_state.get(gathered_data_cache_key):
            logger.info(f"Cache hit for gathered data: {gathered_data_cache_key} (Session ID: {self.session_id})")
            gathered_data_content = self.session_state[gathered_data_cache_key]
            yield RunEvent(event_type="CacheHit", data={"step": "DataGathering", "message": "Loaded gathered data from cache."})
        else:
            logger.info(f"Workflow Step 1: Gathering data for topic: '{topic}', Sections: {selected_sections} (Session ID: {self.session_id})")
            section_mapping = {
                'basic': 'basic player information (team, position, draft info)', 'career_stats': 'career statistics (totals and per-season)',
                'current_stats': 'current season aggregate statistics', 'gamelog': 'current season game logs',
                'awards': 'player awards and accolades', 'profile': 'player profile details (career/season highs)',
                'hustle': 'hustle statistics', 'defense': 'detailed defensive statistics',
                'shooting': 'shot chart details and shooting splits', 'passing': 'detailed passing statistics',
                'rebounding': 'detailed rebounding statistics', 'clutch': 'clutch time statistics',
                'analysis': 'year-over-year analysis', 'insights': 'general player insights or dashboards'
            }
            requested_data_desc = ", ".join([section_mapping.get(s_id, s_id) for s_id in selected_sections])
            gatherer_instructions = dedent(f"""
                1. Analyze the user's research topic: '{topic}'
                2. The user wants data specifically for these aspects: **{requested_data_desc}**.
                3. Plan and execute tool calls *only* for these requested aspects.
                4. Output the raw or slightly summarized JSON results from each successful tool call. If a tool fails, note the error.
                """)
            
            temp_gathered_data_parts = []
            has_gatherer_error = False
            async for event in await self.data_gatherer.arun(topic, instructions=gatherer_instructions, stream=True, stream_intermediate_steps=True):
                yield event
                if isinstance(event, RunResponse) and event.content:
                    if isinstance(event.content, str):
                        temp_gathered_data_parts.append(event.content)
                    if event.event == RunEvent.agent_error or (isinstance(event.content, dict) and event.content.get("error")):
                        has_gatherer_error = True
                        logger.error(f"Data gatherer agent reported an error: {event.content}")
                        break
                elif event.event == RunEvent.agent_error:
                    has_gatherer_error = True
                    logger.error(f"Data gatherer agent error event: {event.data}")
                    break
            
            if has_gatherer_error:
                error_message = Errors.PROCESSING_ERROR.format(error="Data gathering phase failed.")
                yield RunEvent(event_type="Error", data={"type": "error", "content": error_message, "step": "DataGathering"})
                return

            gathered_data_content = "\n\n---\n\n".join(temp_gathered_data_parts)
            
            if not gathered_data_content.strip():
                logger.warning("Data gathering step produced no content.")
                yield RunEvent(event_type="Error", data={"type": "error", "content": "Data gathering failed to produce results.", "step": "DataGathering"})
                return
            
            if self.session_state: 
                self.session_state[gathered_data_cache_key] = gathered_data_content
                logger.info(f"Cached gathered data under key: {gathered_data_cache_key} (Session ID: {self.session_id})")
        
        logger.info(f"Workflow Step 1 Completed. Gathered data length: {len(gathered_data_content)} (Session ID: {self.session_id})")

        logger.info(f"Workflow Step 2: Writing report based on gathered data (Session ID: {self.session_id}).")
        writer_input_content = f"Original Research Topic: {topic}\n\nSelected Aspects for Report: {', '.join(selected_sections)}\n\nGathered Data Dump:\n===\n{gathered_data_content}\n==="
        
        final_report_parts = []
        async for event in await self.report_writer.arun(writer_input_content, stream=True, stream_intermediate_steps=False):
            yield event
            if isinstance(event, RunResponse) and isinstance(event.content, str):
                final_report_parts.append(event.content)
        
        final_report_str = "".join(final_report_parts)
        if self.session_state and final_report_str.strip(): 
            self.session_state[final_report_cache_key] = final_report_str
            logger.info(f"Cached final report under key: {final_report_cache_key} (Session ID: {self.session_id})")

        logger.info(f"Workflow Step 2 Completed. Report writing stream finished (Session ID: {self.session_id}).")