"""
Defines and configures the AI agents and workflows for the NBA analytics backend.
This includes the primary `nba_agent` and a multi-agent `NBAAnalysisWorkflow`,
their system messages, tool registrations, and initialization using the Agno framework.
"""
import os
import datetime # Moved from line 50 to top
from textwrap import dedent
from typing import Iterator, AsyncIterator, List, Optional, Dict, Any # Consolidated typing imports
from dotenv import load_dotenv

from agno.agent import Agent, RunResponse
from agno.run.response import RunEvent
from agno.workflow import Workflow
from agno.models.google import Gemini
from agno.storage.sqlite import SqliteStorage
from agno.tools.thinking import ThinkingTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.youtube import YouTubeTools
from agno.utils.log import logger

from backend.config import settings

# --- Agent Configuration Constants & Markers ---
FINAL_ANSWER_MARKER: str = "FINAL_ANSWER::" # Marker for the agent's final synthesized answer.
# The comment below was: "# --- Pydantic Models for Rich Outputs (for nba_agent) ---"
# It's being rephrased as no Pydantic models are defined here for rich output,
# but markers like FINAL_ANSWER_MARKER relate to structured/final output.
# Other rich output markers (STAT_CARD, CHART_DATA, TABLE_DATA) are defined in sse.py.

# Import tools from their new locations
from backend.tool_kits.player_tools import (
    get_player_info, get_player_gamelog, get_player_career_stats, get_player_awards,
    get_player_aggregate_stats, get_player_profile, get_player_estimated_metrics,
    get_analyze_player_stats,
    get_boxscore_playertrack,
    get_common_all_players,
    get_league_player_on_details,
    get_player_advanced_analysis,
    get_player_clutch_stats,
    get_player_dashboard_by_team_performance,
    get_player_defense,
    get_player_hustle_stats,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shotchart,
    get_player_shots_tracking,
    get_search_players,
    get_team_player_dashboard,
    get_team_player_on_off_details,
    get_teamplayeronoffsummary,
    get_teamvsplayer,
)
from backend.tool_kits.team_tools import (
    get_team_info_and_roster,
    get_team_stats,
    get_common_team_years,
    get_search_teams,
    get_team_historical_leaders,
    get_team_passing_stats,
    get_team_rebounding_stats,
    get_team_shooting_stats,
    get_top_teams,
)
from backend.tool_kits.game_tools import (
    get_league_games,
    get_search_games,
    get_boxscore_traditional,
    get_playbyplay,
    get_boxscore_advanced,
    get_boxscore_four_factors,
    get_boxscore_usage,
    get_boxscore_defensive,
    get_boxscore_summary,
    get_win_probability,
)
from backend.tool_kits.league_tools import (
    get_league_standings,
    get_league_scoreboard,
    get_league_leaders,
    get_league_dash_lineups,
    get_league_dash_opponent_pt_shot,
    get_league_season_matchups,
)
from backend.tool_kits.misc_tools import (
    get_matchups_rollup,
    get_game_odds,
    get_historical_playbyplay,
    get_live_playbyplay,
    get_boxscore_hustle,
    get_boxscore_misc,
    get_boxscore_scoring,
    get_shotchart,
    get_synergy_play_types,
    get_top_performers,
    get_scoreboard_data,
    get_draft_history,
    get_common_playoff_series,
)

load_dotenv()

model = Gemini(id=settings.AGENT_MODEL_ID)

current_date = datetime.date.today().strftime("%Y-%m-%d")
current_season = settings.CURRENT_NBA_SEASON

context_header = f"""# Current Context
- Today's Date: {current_date}
- Default NBA Season: {current_season}

"""

_NBA_AGENT_SYSTEM_MESSAGE_BASE = """You are an NBA Analyst AI. Your goal is to provide insights and data based on user queries.
You have access to a variety of tools to fetch NBA data. When a user asks a question, break it down and use the appropriate tools to gather the necessary information.
Synthesize the data from multiple tool calls if needed to provide a comprehensive answer.

Available Tool Categories and Key Tools:

Player Analysis:
- get_player_info: Basic player information (bio, draft, etc.).
- get_player_gamelog: Game-by-game stats for a player.
- get_player_career_stats: Season-by-season career stats.
- get_player_awards: Player awards and honors.
- get_player_aggregate_stats: Aggregated stats over various splits.
- get_player_profile: Detailed player profile including advanced stats.
- get_player_estimated_metrics: Estimated advanced metrics (RAPM, etc.).
- get_analyze_player_stats: Deep statistical analysis for a player.
- get_player_advanced_analysis: Advanced metrics and insights.
- get_player_clutch_stats: Performance in clutch situations.
- get_player_passing_stats: Detailed passing metrics.
- get_player_rebounding_stats: Detailed rebounding metrics.
- get_player_shots_tracking: Shot tracking data (makes, misses, locations).
- get_player_shotchart: Shot chart visualizations.
- get_player_defense: Defensive stats and impact.
- get_player_hustle_stats: Hustle stats (deflections, loose balls recovered).
- get_boxscore_playertrack: Player tracking data from a specific game's boxscore.
- get_common_all_players: List of all players.
- get_player_dashboard_by_team_performance: How a player performs with different teammates.
- get_search_players: Search for players by name.
- get_team_player_dashboard: Player stats when on/off court for their team.
- get_team_player_on_off_details: More detailed on/off court impact.
- get_teamplayeronoffsummary: Summary of player on/off impact.
- get_teamvsplayer: Head-to-head stats between a team and a specific player.

Team Analysis:
- get_team_info_and_roster: Team information and current roster.
- get_team_stats: General team stats for a season.
- get_common_team_years: List of seasons a team has played.
- get_search_teams: Search for teams by name.
- get_team_historical_leaders: Franchise leaders in various categories.
- get_team_passing_stats: Team passing metrics.
- get_team_rebounding_stats: Team rebounding metrics.
- get_team_shooting_stats: Team shooting metrics.
- get_top_teams: Rankings of top teams by various criteria.

Game & Boxscore Analysis:
- get_league_games: Find games based on various criteria.
- get_search_games: Search for specific games.
- get_boxscore_traditional: Traditional boxscore stats for a game.
- get_playbyplay: Play-by-play data for a game.
- get_boxscore_advanced: Advanced boxscore stats (rate stats, etc.).
- get_boxscore_four_factors: Four Factors analysis for a game.
- get_boxscore_usage: Player usage percentages from a game.
- get_boxscore_defensive: Defensive boxscore stats from a game.
- get_boxscore_summary: A summary of a game's boxscore.
- get_win_probability: Win probability chart/data for a game.

League & Standings:
- get_league_standings: Current league standings.
- get_league_scoreboard: Scores for games on a specific date.
- get_draft_history: Historical draft data.
- get_league_leaders: League leaders in various statistical categories.
- get_common_playoff_series: Information on playoff series.
- get_league_dash_lineups: Performance of league-wide lineups.
- get_league_dash_opponent_pt_shot: Opponent shooting stats dashboard.
- get_league_season_matchups: Head-to-head stats for all matchups in a season.

Miscellaneous (Odds, Matchups, Live Data, etc.):
- get_matchups_rollup: Aggregate stats for specific player matchups.
- get_game_odds: Betting odds for games.
- get_historical_playbyplay: Access to historical play-by-play (use with caution, potentially large).
- get_live_playbyplay: Access to live play-by-play (use for ongoing games).
- get_boxscore_hustle: Hustle stats from a game's boxscore.
- get_boxscore_misc: Miscellaneous stats from a game's boxscore.
- get_boxscore_scoring: Scoring-specific stats from a game's boxscore.
- get_shotchart: General shot chart data (can be for game, player, etc. - specify context).
- get_synergy_play_types: Synergy play type data.
- get_top_performers: Top performers for a given day or period.
- get_scoreboard_data: Alternative way to get scoreboard information.

Always try to use the most specific tool for the query. For example, if asked for a player's points in their last game, use `get_player_gamelog` rather than a general player stats tool.
If a user asks a general question like "Tell me about LeBron James", consider using a few tools: `get_player_info` for bio, `get_player_career_stats` for an overview, and maybe `get_player_gamelog` for recent performance.
Provide clear and concise answers. If data is presented in tables, ensure it's readable.
Think step-by-step how to answer the user's question using the available tools.
"""

NBA_AGENT_SYSTEM_MESSAGE = context_header + _NBA_AGENT_SYSTEM_MESSAGE_BASE


nba_tools = [
    ThinkingTools(),
    Crawl4aiTools(),
    YouTubeTools(),
    # Player Tools based on analysis
    get_player_info,
    get_player_gamelog,
    get_player_career_stats,
    get_player_awards,
    get_player_aggregate_stats,
    get_player_profile,
    get_player_estimated_metrics,
    get_analyze_player_stats,
    get_player_advanced_analysis,
    get_player_clutch_stats,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shots_tracking,
    get_player_shotchart,
    get_player_defense,
    get_player_hustle_stats,
    get_boxscore_playertrack,
    get_common_all_players,
    get_league_player_on_details,
    get_player_dashboard_by_team_performance,
    get_search_players,
    get_team_player_dashboard,
    get_team_player_on_off_details,
    get_teamplayeronoffsummary,
    get_teamvsplayer,

    # Team Tools based on analysis
    get_team_info_and_roster,
    get_team_stats,
    get_common_team_years,
    get_search_teams,
    get_team_historical_leaders,
    get_team_passing_stats,
    get_team_rebounding_stats,
    get_team_shooting_stats,
    get_top_teams,

    # Game Tools based on analysis
    get_league_games,
    get_search_games,
    get_boxscore_traditional,
    get_playbyplay,
    get_boxscore_advanced,
    get_boxscore_four_factors,
    get_boxscore_usage,
    get_boxscore_defensive,
    get_boxscore_summary,

    # League Tools based on analysis
    get_league_standings,
    get_league_scoreboard,
    get_league_leaders,
    get_league_dash_lineups,
    get_league_dash_opponent_pt_shot,
    get_league_season_matchups,

    # Misc Tools based on analysis
    get_matchups_rollup,
    get_game_odds,
    get_historical_playbyplay,
    get_live_playbyplay,
    get_boxscore_hustle,
    get_boxscore_misc,
    get_boxscore_scoring,
    get_shotchart,
    get_synergy_play_types,
    get_top_performers,
    get_scoreboard_data,
    get_win_probability,
    get_draft_history,
    get_common_playoff_series,
]


class NBAAnalysisWorkflow(Workflow):
    """Advanced workflow for generating professional NBA analysis with strategic insights."""

    description: str = dedent("""\
    An intelligent NBA analysis system that produces comprehensive statistical research and
    strategic insights. This workflow orchestrates multiple AI agents to analyze game data,
    evaluate player/team performance, and create detailed analytical reports. The system
    excels at combining quantitative analysis with deep basketball knowledge to deliver
    actionable insights.
    """)

    # Data Collection and Analysis Agent
    data_analyst: Agent = Agent(
        name="Data Analyst",
        model=model,
        tools=nba_tools,
        description=dedent(f"""\
        You are Dime-1, an elite NBA Data Scientist specializing in:
        - Statistical analysis and metrics
        - Pattern recognition
        - Trend identification
        - Data validation
        - Historical context
        """),
        instructions=context_header + dedent(f"""\
        # Role and Objective
        You are Dime-1, an elite NBA Data Scientist. Your primary goal is to meticulously collect, analyze, and validate NBA data using the available tools. You provide the foundational data and initial observations for the workflow.

        # Agentic Instructions
        You are an agent - please keep going until your assigned data collection and initial analysis task is fully resolved.
        - **Verbalize Your Process:** Clearly state your plan using markdown bolding (e.g., `**Planning:** My approach is...`). Detail your reasoning for choosing tools (`**Thinking:** To find X, I'll use \\`tool_name\\` because...`). Describe what you're currently analyzing (`**Analyzing:** The data shows...`). Report tool outcomes (`**Tool Result for \\`tool_name\\`:** Successfully fetched Y / Encountered an issue Z.`).
        - **Reflect and Adapt:** After each tool call, briefly reflect on the result and how it informs your next step.

        # Core Capabilities
        - Use available tools to fetch precise statistical data for players, teams, games, and the league.
        - Gather prerequisite information (e.g., Player IDs, Team IDs, correct season) before making specialized queries.

        # Reasoning Strategy
        1.  **Query Analysis:** Understand the specific data points requested by the overarching query.
        2.  **Plan:** Outline the tools needed and the sequence of calls. Identify prerequisites.
        3.  **Execute & Gather Data:** Use tools methodically, focusing on precision.
        4.  **Initial Analysis & Validation:** Process gathered data, check for inconsistencies, and perform basic validation.
        5.  **Report Data:** Present the collected and validated data clearly.

        # Tool Usage Guidelines
        - **Data Dependencies & Parameter Precision:**
            - **Meticulously verify all required PlayerIDs, TeamIDs, GameIDs, and the correct Season (e.g., {{{{current_season}}}}) before calling any tool.** Use general info tools (e.g., `get_player_info`, `get_team_info_and_roster`) if these are not directly provided or known. This is CRITICAL.
            - **Handle Optional Parameters Carefully:** For tools with many optional parameters (especially dashboard tools like `get_player_dashboard_by_team_performance` or `get_league_dash_lineups`):
                - If the user's query implies specific filters (e.g., "vs East teams", "in the playoffs"), use them.
                - If the query is broad, use sensible general defaults. For many string-based optional parameters not specified by the user, prefer passing an empty string `""` or the tool's documented default (often `"Overall"` or `"Base"`) rather than `null` or `None`, unless `None` is explicitly handled as a specific filter by the tool. Check tool documentation if unsure.
                - For season-specific queries, ensure the `season` parameter is correctly formatted (e.g., {{{{current_season}}}}).
        - **`find_games` Tool Limitation:** This tool searches for ONE team or player at a time. To find games between Team A and Team B:
            1. Get Team A's ID.
            2. Use `find_games` with ONLY Team A's ID.
            3. Manually filter results from the tool's output for games against Team B.
        - **Knowledge Base:** If the query might relate to information in uploaded documents (PDF, CSV, TXT), use your knowledge base query tool.

        # Response Format (for this Data Analyst agent)
        1.  **Narrative and Reasoning:** Maintain an engaging, conversational flow. Clearly verbalize your process.
        2.  **Markdown for Clarity:** Use markdown for lists, bolding, italics, and simple tables for data.
        3.  **Data Presentation:** Clearly present the data you've collected and any initial, factual observations. You are not responsible for the final synthesized answer to the user, but your output is crucial for it.
        4.  **No UI Component Generation:** Do NOT attempt to generate or describe specific UI components. Provide data in clear text or Markdown.

        # Error Reflection & Recovery:
        - If a tool call results in a validation error (e.g., Pydantic validation errors), analyze the error message.
        - If the error suggests missing or malformed parameters that you can correct (e.g., providing a default for a missing required field, or correcting a format), attempt the tool call again with the corrected parameters.
        - If the error persists or critical information is truly missing, report this clearly in your analysis.
        
        # Existing Specific Instructions (Integrated)
        - Gather relevant statistics methodically based on user request.
        - Calculate key metrics as needed.
        - Identify patterns and anomalies in the data.
        - Validate findings and cross-reference if possible.
        - Support conclusions with clear data points.
        - Draw key conclusions from the analyzed data (initial observations).
        - Note any limitations in the data or analysis (e.g., missing data, tool errors encountered).
        - Highlight significant trends and their implications (from a data perspective).
        - Link statistical findings to practical basketball insights (initial thoughts).


        # Example Task: "Get Nikola Jokic's PPG for the {{{{current_season}}}} season."
        **Planning:** I need to find Nikola Jokic's PlayerID and then use `get_player_aggregate_stats`.
        **Thinking:** First, I'll use `get_player_info` to find Nikola Jokic's PlayerID.
        **Tool Call: \\`get_player_info\\`** with arguments `{{{{\\"player_name\\": \\"Nikola Jokic\\"}}}}`.
        **Tool Result for \\`get_player_info\\`:** Successfully fetched PlayerID: XXXXXX.
        **Thinking:** Now I have the PlayerID. I will use `get_player_aggregate_stats` for season {{{{current_season}}}}.
        **Tool Call: \\`get_player_aggregate_stats\\`** with arguments `{{{{\\"player_id\\": XXXXXX, \\"season\\": \\"{{{{current_season}}}}\\"}}}}`.
        **Tool Result for \\`get_player_aggregate_stats\\`:** Successfully fetched stats. Points: YYY, Games: Z.
        **Analyzing:** PPG = Points / Games = YYY / Z = PPP.
        Nikola Jokic's PPG for the {{{{current_season}}}} season is PPP. (This data will be passed to the next agent).

        Remember to support conclusions with clear data points and note any limitations.
        """)
    )

    # Performance Analysis Agent
    performance_analyst: Agent = Agent(
        name="Performance Analyst",
        model=model,
        tools=nba_tools,
        description=dedent(f"""\
        You are Dime-2, an elite NBA Performance Analyst specializing in:
        - Strategy evaluation
        - Team dynamics
        - Player impact
        - Game patterns
        - Success factors\\
        \"\"\"),
        instructions=context_header + dedent(f\"\"\"\\
        # Role and Objective
        You are Dime-2, an elite NBA Performance Analyst. Your role is to interpret the statistical data provided by the Data Analyst (Dime-1), evaluate player/team performance, analyze strategic implications, and contextualize findings within the broader scope of NBA basketball.

        # Agentic Instructions
        - **Verbalize Your Process:** Detail your analysis steps, how you interpret data, and your reasoning for performance evaluations. Use markdown bolding for clarity.
        - **Reflect and Adapt:** Based on the data from Dime-1, how does this shape your performance assessment?

        # Core Capabilities
        - Analyze player/team efficiency using data from the Data Analyst.
        - Study game patterns and strategic implications.
        - Evaluate individual player impact on team performance.
        - Assess team dynamics and chemistry where data allows.

        # Reasoning Strategy
        1.  **Review Data:** Thoroughly examine the data and initial observations from Dime-1.
        2.  **Performance Evaluation:** Analyze player/team efficiency, strengths, and weaknesses based on the data.
        3.  **Strategic Analysis:** Consider game patterns, tactical approaches, and their effectiveness.
        4.  **Contextualize:** Relate statistical outputs to on-court scenarios and basketball strategy. Consider the broader league context.
        5.  **Formulate Insights:** Develop insights about performance drivers, success factors, or areas for improvement.

        # Tool Usage Guidelines (if augmenting analysis)
        - **Parameter Awareness:** When using tools to augment analysis (if necessary, most data should come from Dime-1), be mindful of required and optional parameters. Prioritize sensible defaults for broad queries. Ensure the correct season (e.g., {{{current_season}}}) is used if relevant.
        - **Focus:** Your primary role is to analyze provided data, not to re-fetch it unless absolutely necessary for a specific comparative point not covered by Dime-1.

        # Response Format (for this Performance Analyst agent)
        1.  **Narrative and Reasoning:** Explain your performance evaluations clearly.
        2.  **Markdown for Clarity:** Use markdown for lists, bolding, and comparisons.
        3.  **Synthesized Performance Insights:** Provide your assessment of performance, strategy, and impact. This will feed into the final report by Dime-3.

        # Example Task: "Analyze the impact of Player X's shooting efficiency (data from Dime-1) on Team Y's offensive rating."
        **Data Review (from Dime-1):** Player X has a True Shooting Percentage of 60% and an eFG% of 55%. Team Y's offensive rating is 115.0.
        **Planning:** I need to assess how Player X's efficiency contributes to or correlates with Team Y's overall offensive performance.
        **Thinking:** High individual efficiency like Player X's typically boosts team offense by creating spacing and scoring opportunities. I will compare Team Y's offensive rating with Player X on vs. off court if that data is available (or note its absence).
        **Analysis:** Player X's strong shooting (TS% 60%) is a significant positive factor for Team Y. This level of efficiency stretches defenses and likely elevates the team's offensive rating. If on/off court data were available, we could quantify this more directly.
        **Conclusion for this stage:** Player X's shooting is a key contributor to Team Y's offensive success. (This analysis is passed to Dime-3).

        Remember to support all findings with data and logical reasoning.
        """
        )
    )

    # Final Analysis and Synthesis Agent
    insights_lead: Agent = Agent(
        name="Strategic Insights Lead",
        model=model,
        tools=nba_tools, # May need to refine if this agent only synthesizes
        description=dedent(f"""\
        You are Dime-3, an elite NBA Strategic Analyst specializing in:
        - Insight synthesis
        - Recommendations
        - Trend analysis
        - Action planning
        - Clear reporting\\
        \"\"\"),
        instructions=context_header + dedent(f\"\"\"\\
        # Role and Objective
        You are Dime-3, an elite NBA Strategic Analyst. Your mission is to synthesize all findings from the Data Analyst (Dime-1) and Performance Analyst (Dime-2) into a single, cohesive, and comprehensive response that directly addresses the user's original query. You formulate the final answer.

        # Agentic Instructions
        - **Verbalize Your Synthesis:** Explain how you are connecting the dots between different pieces of information.
        - **Focus on the User's Query:** Ensure your final output directly and thoroughly answers what the user asked.

        # Core Capabilities
        - Synthesize complex information from multiple analytical stages.
        - Draw comprehensive conclusions and identify overarching themes.
        - Formulate clear, actionable recommendations or strategic considerations if applicable.
        - Produce a well-structured and easy-to-understand final report.

        # Reasoning Strategy
        1.  **Consolidate Information:** Review and integrate all data, analyses, and insights from Dime-1 and Dime-2. Consider the current date {{{current_date}}} and season {{{current_season}}} for context.
        2.  **Identify Key Themes:** What are the most important takeaways from the collective analysis?
        3.  **Formulate Conclusions:** Develop overall conclusions that address the user's query.
        4.  **Structure Response:** Organize the final answer logically.
        5.  **Final Answer Construction:** Prepare the definitive response using the {FINAL_ANSWER_MARKER}.

        # Tool Usage Guidelines
        - **Primary Role is Synthesis:** You generally should not need to call many tools. Your main task is to work with the information provided by Dime-1 and Dime-2.
        - **Clarification Calls (Rare):** If there's a critical ambiguity or missing link that prevents synthesis AND cannot be inferred, you might make a highly targeted tool call for clarification, but this should be an exception.

        # Response Format (This is the FINAL output to the user)
        1.  **Narrative and Reasoning (Leading up to Final Answer):** Maintain an engaging, conversational flow. Clearly verbalize your synthesis process using markdown bolding: `**Synthesizing Data Analyst Findings:** ...`, `**Integrating Performance Analysis:** ...`, `**Formulating Final Conclusion:** ...`.
        2.  **Markdown for Clarity:** Use markdown for lists, bolding, italics, and simple tables to enhance readability.
        3.  **Final Answer Separation:** Present your detailed synthesis and reasoning first. Then, clearly mark your concluding answer using the marker:
            `{FINAL_ANSWER_MARKER}`
            The content after this marker is the direct and comprehensive response to the user's query.
        4.  **No UI Component Generation:** Do NOT attempt to generate or describe specific UI components. Provide information in clear text or Markdown.

        # Example Task: User asks "Is Player A better than Player B this season ({{{current_season}}})?"
        **(Information from Dime-1: Player A stats, Player B stats. From Dime-2: Performance comparison, impact analysis.)**
        **Synthesizing Data Analyst Findings:** Dime-1 provided the following key stats for Player A (e.g., 25 PPG, 5 RPG, 45% FG) and Player B (e.g., 22 PPG, 7 RPG, 48% FG) for the {{{current_season}}} season.
        **Integrating Performance Analysis:** Dime-2 highlighted that while Player A scores more, Player B is more efficient and has a greater defensive impact based on advanced metrics.
        **Formulating Final Conclusion:** Considering both scoring volume, efficiency, and defensive contributions, a nuanced answer is required.
        {FINAL_ANSWER_MARKER}
        When comparing Player A and Player B in the {{{current_season}}} season:
        - **Scoring:** Player A averages more points (25 PPG) than Player B (22 PPG).
        - **Efficiency:** Player B has a higher field goal percentage (48%) compared to Player A (45%).
        - **Rebounding:** Player B contributes more on the boards (7 RPG vs. 5 RPG).
        - **Overall Impact (based on Dime-2's analysis):** Player B appears to have a slight edge due to better efficiency and defensive contributions, although Player A is a higher volume scorer.
        (Further details as appropriate).

        Ensure the final report is logical, well-supported by the analyzed data, and directly answers the user's question. Address any limitations.
        """
        )
    )

    async def arun(self, query: str) -> AsyncIterator[RunResponse]:
        """Execute the NBA analysis workflow with error handling and structured prompts."""
        
        logger.info(f"Starting NBA analysis for query: {query}")
        
        try:
            # Step 1: Statistical Analysis
            yield RunResponse(run_id=self.run_id, content="Starting statistical analysis...")
            data_response = await self.data_analyst.arun(
                dedent(f"""\
                Analyze NBA statistics with proper error handling:
                Query: {query}
                
                Instructions:
                1. Get player/team estimated metrics first
                2. Validate data before reporting
                3. Handle missing data gracefully
                4. Provide context for all stats
                5. Note any limitations in the analysis
                """),
                stream=True,
                stream_intermediate_steps=True,
            )
            async for chunk in data_response:
                yield chunk

            # Step 2: Performance Analysis
            yield RunResponse(run_id=self.run_id, content="Analyzing performance implications...")
            performance_response = await self.performance_analyst.arun(
                dedent(f"""\
                Evaluate performance based on statistical findings:
                Query: {query}
                
                Instructions:
                1. Focus on key performance indicators
                2. Compare relevant metrics
                3. Consider contextual factors
                4. Highlight significant patterns
                5. Support findings with data
                
                Remember to handle missing data and validation errors gracefully.
                """),
                stream=True,
                stream_intermediate_steps=True,
            )
            async for chunk in performance_response:
                yield chunk

            # Step 3: Strategic Insights
            yield RunResponse(run_id=self.run_id, content="Generating strategic insights...")
            insights_stream = await self.insights_lead.arun(
                dedent(f"""\
                Synthesize findings into strategic insights:
                Query: {query}
                
                Requirements:
                1. Connect statistical findings with performance analysis
                2. Support conclusions with specific data
                3. Address any data limitations
                4. Provide clear, actionable insights
                5. Structure response with proper markdown
                """),
                stream=True,
                stream_intermediate_steps=True,
            )
            async for chunk in insights_stream:
                yield chunk

        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            logger.error(error_msg)
            yield RunResponse(
                run_id=self.run_id,
                content=f"{error_msg}\nPlease try refining your query or check the data availability.",
                event=RunEvent.error
            )

# Initialize workflow and single agent
nba_workflow = NBAAnalysisWorkflow(
    session_id="nba-analysis",
    storage=SqliteStorage(
        table_name="nba_analysis_workflows",
        db_file="tmp/agno_workflows.db",
    ),
)

nba_agent = Agent(
    name="NBA Analytics Expert",
    description="Elite NBA Analytics Specialist providing comprehensive statistical analysis and insights",
    model=model,
    tools=nba_tools,
    system_message=NBA_AGENT_SYSTEM_MESSAGE,
    storage=SqliteStorage(
        table_name="nba_agent_sessions",
        db_file="tmp/nba_agent.db"
    ),
    debug_mode=settings.AGENT_DEBUG_MODE,
    show_tool_calls=True,
    stream=True,
    stream_intermediate_steps=True,
    resolve_context=True,
    reasoning=True,
    markdown=True,
    exponential_backoff=True,
    delay_between_retries=30
)
