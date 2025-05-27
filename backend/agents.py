"""
Defines and configures the AI agents and workflows for the NBA analytics backend.
This includes the primary `nba_agent` and a multi-agent `NBAAnalysisWorkflow`,
their system messages, tool registrations, and initialization using the Agno framework.
"""
import os
import datetime
from textwrap import dedent
from typing import Iterator, AsyncIterator, List, Optional, Dict, Any
from dotenv import load_dotenv

from agno.agent import Agent, RunResponse
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

# Import individual tools
from backend.individual_tools.player_tools import (
    analyze_player_dashboard_stats,
    get_player_aggregate_stats,
    get_player_career_stats,
    get_player_awards,
    get_player_clutch_stats,
    get_player_common_info,
    get_player_headshot_image_url,
    get_player_dashboard_by_game_splits,
    get_player_dashboard_by_general_splits,
    get_player_dashboard_by_last_n_games,
    get_player_dashboard_by_shooting_splits,
    get_player_fantasy_profile,
    get_player_fantasy_profile_bar_graph,
    get_player_gamelog,
    get_player_game_streaks,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shooting_tracking_stats,
    get_player_career_stats_by_college
)
from backend.individual_tools.team_tools import (
    get_team_lineup_stats,
    get_team_player_tracking_shot_stats,
    get_team_player_tracking_defense_stats,
    get_team_dashboard_shooting_splits,
    get_team_details,
    get_league_team_estimated_metrics, # Note: Originally in TeamToolkit, references league-wide but often used for specific team context here
    get_team_game_logs,
    get_team_general_stats,
    get_team_historical_leaders,
    get_common_team_years,
    get_team_info_and_roster,
    get_team_passing_stats,
    get_team_player_dashboard_stats,
    get_team_player_on_off_details,
    get_team_player_on_off_summary,
    get_team_rebounding_tracking_stats,
    get_team_shooting_tracking_stats,
    get_team_vs_player_stats,
    get_league_franchise_history, # Note: Also in LeagueToolkit, often relevant in team context
    get_franchise_leaders,
    get_franchise_players
)
from backend.individual_tools.league_tools import (
    get_all_time_leaders_grids,
    get_assist_leaders,
    get_homepage_leaders,
    get_homepage_v2_leaders,
    get_in_season_tournament_standings,
    get_leaders_tiles,
    get_league_player_bio_stats,
    get_league_player_clutch_stats,
    get_league_player_shooting_stats,
    get_league_player_shot_locations,
    get_league_player_stats,
    get_league_player_tracking_defense_stats,
    get_league_player_tracking_stats,
    get_league_team_tracking_defense_stats,
    get_league_team_clutch_stats,
    get_league_team_player_tracking_shot_stats,
    get_league_team_shot_locations,
    get_league_team_stats,
    get_draft_history,
    get_league_game_log,
    get_league_hustle_stats_team,
    get_league_leaders,
    get_league_lineups_data,
    get_league_lineup_viz_data,
    get_league_standings,
    get_player_index,
    get_common_all_players,
    get_playoff_picture,
    get_common_playoff_series,
    get_league_schedule,
    get_shot_chart_league_wide,
    get_top_performing_teams,
    get_top_performing_players,
    get_league_player_estimated_metrics
)
from backend.individual_tools.game_tools import (
    get_game_boxscore_traditional,
    get_game_boxscore_advanced,
    get_game_boxscore_four_factors,
    get_game_boxscore_usage,
    get_game_boxscore_defensive,
    get_game_boxscore_summary,
    get_game_boxscore_misc,
    get_game_boxscore_player_tracking,
    get_game_boxscore_scoring,
    get_game_boxscore_hustle,
    get_game_boxscore_matchups,
    get_game_play_by_play,
    get_game_rotation_data,
    get_game_shotchart_data,
    get_game_win_probability
)
from backend.individual_tools.comparison_tools import (
    compare_players_stats,
    get_team_vs_player_comparison,
    get_player_vs_player_season_matchups,
    get_player_defensive_matchup_rollup,
    compare_player_shot_charts_visual
)
from backend.individual_tools.search_tools import (
    search_players,
    search_teams,
    search_games,
    find_league_games
)
from backend.individual_tools.financial_tools import (
    get_contracts_data,
    get_player_contract_details,
    get_team_payroll_summary,
    get_highest_paid_players_list,
    search_player_contracts_by_name,
    get_free_agents_data,
    get_free_agent_player_info,
    get_team_former_free_agents,
    get_top_available_free_agents,
    search_free_agents_by_name
)
from backend.individual_tools.live_updates_tools import (
    get_live_league_scoreboard,
    get_todays_game_odds,
    get_scoreboard_for_date
)
from backend.individual_tools.draft_combine_tools import (
    get_draft_combine_drill_results,
    get_draft_combine_non_stationary_shooting_stats,
    get_draft_combine_player_anthropometrics,
    get_draft_combine_spot_shooting_stats,
    get_comprehensive_draft_combine_stats,
    get_nba_draft_history_detailed # Renamed from get_draft_history to avoid clash
)
from backend.individual_tools.advanced_analytics_tools import (
    get_player_advanced_analysis,
    get_player_shot_chart_data,
    generate_player_advanced_shot_chart_visualization,
    compare_players_shot_charts_visualization
)
from backend.individual_tools.workflow_tools import (
    execute_team_summer_strategy_analysis,
    generate_stat_card,
    generate_player_card,
    generate_team_analysis_card,
    generate_trade_scenario_card,
    generate_chart_data
)

load_dotenv()

model = Gemini(id=settings.AGENT_MODEL_ID)

# Combine all individual tools
nba_tools = (
    # Player Tools
    analyze_player_dashboard_stats,
    get_player_aggregate_stats,
    get_player_career_stats,
    get_player_awards,
    get_player_clutch_stats,
    get_player_common_info,
    get_player_headshot_image_url,
    get_player_dashboard_by_game_splits,
    get_player_dashboard_by_general_splits,
    get_player_dashboard_by_last_n_games,
    get_player_dashboard_by_shooting_splits,
    get_player_fantasy_profile,
    get_player_fantasy_profile_bar_graph,
    get_player_gamelog,
    get_player_game_streaks,
    get_player_passing_stats,
    get_player_rebounding_stats,
    get_player_shooting_tracking_stats,
    get_player_career_stats_by_college,
    # Team Tools
    get_team_lineup_stats,
    get_team_player_tracking_shot_stats,
    get_team_player_tracking_defense_stats,
    get_team_dashboard_shooting_splits,
    get_team_details,
    get_league_team_estimated_metrics,
    get_team_game_logs,
    get_team_general_stats,
    get_team_historical_leaders,
    get_common_team_years,
    get_team_info_and_roster,
    get_team_passing_stats,
    get_team_player_dashboard_stats,
    get_team_player_on_off_details,
    get_team_player_on_off_summary,
    get_team_rebounding_tracking_stats,
    get_team_shooting_tracking_stats,
    get_team_vs_player_stats,
    get_league_franchise_history,
    get_franchise_leaders,
    get_franchise_players,
    # League Tools
    get_all_time_leaders_grids,
    get_assist_leaders,
    get_homepage_leaders,
    get_homepage_v2_leaders,
    get_in_season_tournament_standings,
    get_leaders_tiles,
    get_league_player_bio_stats,
    get_league_player_clutch_stats,
    get_league_player_shooting_stats,
    get_league_player_shot_locations,
    get_league_player_stats,
    get_league_player_tracking_defense_stats,
    get_league_player_tracking_stats,
    get_league_team_tracking_defense_stats,
    get_league_team_clutch_stats,
    get_league_team_player_tracking_shot_stats,
    get_league_team_shot_locations,
    get_league_team_stats,
    get_draft_history,
    get_league_game_log,
    get_league_hustle_stats_team,
    get_league_leaders,
    get_league_lineups_data,
    get_league_lineup_viz_data,
    get_league_standings,
    get_player_index,
    get_common_all_players,
    get_playoff_picture,
    get_common_playoff_series,
    get_league_schedule,
    get_shot_chart_league_wide,
    get_top_performing_teams,
    get_top_performing_players,
    get_league_player_estimated_metrics,
    # Game Tools
    get_game_boxscore_traditional,
    get_game_boxscore_advanced,
    get_game_boxscore_four_factors,
    get_game_boxscore_usage,
    get_game_boxscore_defensive,
    get_game_boxscore_summary,
    get_game_boxscore_misc,
    get_game_boxscore_player_tracking,
    get_game_boxscore_scoring,
    get_game_boxscore_hustle,
    get_game_boxscore_matchups,
    get_game_play_by_play,
    get_game_rotation_data,
    get_game_shotchart_data,
    get_game_win_probability,
    # Comparison Tools
    compare_players_stats,
    get_team_vs_player_comparison,
    get_player_vs_player_season_matchups,
    get_player_defensive_matchup_rollup,
    compare_player_shot_charts_visual,
    # Search Tools
    search_players,
    search_teams,
    search_games,
    find_league_games,
    # Financial Tools
    get_contracts_data,
    get_player_contract_details,
    get_team_payroll_summary,
    get_highest_paid_players_list,
    search_player_contracts_by_name,
    get_free_agents_data,
    get_free_agent_player_info,
    get_team_former_free_agents,
    get_top_available_free_agents,
    search_free_agents_by_name,
    # Live Updates Tools
    get_live_league_scoreboard,
    get_todays_game_odds,
    get_scoreboard_for_date,
    # Draft Combine Tools
    get_draft_combine_drill_results,
    get_draft_combine_non_stationary_shooting_stats,
    get_draft_combine_player_anthropometrics,
    get_draft_combine_spot_shooting_stats,
    get_comprehensive_draft_combine_stats,
    get_nba_draft_history_detailed,
    # Advanced Analytics Tools
    get_player_advanced_analysis,
    get_player_shot_chart_data,
    generate_player_advanced_shot_chart_visualization,
    compare_players_shot_charts_visualization,
    # Workflow and Generative UI Tools
    execute_team_summer_strategy_analysis,
    generate_stat_card,
    generate_player_card,
    generate_team_analysis_card,
    generate_trade_scenario_card,
    generate_chart_data,
    # Standard Agno Tools
    ThinkingTools(),
    Crawl4aiTools(),
    YouTubeTools()
)

current_date = datetime.date.today().strftime("%Y-%m-%d")
current_season = settings.CURRENT_NBA_SEASON

context_header = f"""# Current Context
- Today's Date: {current_date}
- Default NBA Season: {current_season}

"""

_NBA_AGENT_SYSTEM_MESSAGE_BASE = """You are an NBA Analyst AI with advanced workflow and generative UI capabilities. Your goal is to provide comprehensive insights, strategic analysis, and interactive visualizations based on user queries.

You have access to a variety of tools including:
- NBA data fetching tools for statistics and analysis
- Advanced workflow tools for complex strategic analysis (like team summer strategy planning)
- Generative UI tools to create interactive cards, charts, and visualizations

When a user asks a question, break it down and use the appropriate tools to gather the necessary information.
For complex strategic questions (like "What should this team do this summer?"), use the workflow tools.
For data presentation, use the generative UI tools to create engaging visual components.
Synthesize the data from multiple tool calls if needed to provide a comprehensive answer.

# Commenting out the detailed tool list as it's now dynamically generated from tool docstrings by Agno.
# Ensure all individual tool functions have clear, descriptive docstrings.
# Available Tool Categories and Key Tools (mapped from new toolkits):
#
# Player Analysis (from PlayerToolkit, MiscToolkit):
# - fetch_player_info: Basic player information (bio, draft, etc.).
# - fetch_player_gamelog: Game-by-game stats for a player.
# - fetch_player_career_stats: Season-by-season career stats.
# - fetch_player_awards: Player awards and honors.
# - fetch_player_aggregate_stats: Aggregated stats over various splits.
# - fetch_player_profile_info: Detailed player profile including advanced stats. (Mapped from fetch_player_profile_info)
# - fetch_player_estimated_metrics: Estimated advanced metrics (RAPM, etc.).
# - analyze_player_stats: Deep statistical analysis for a player. (Tool name might be different in toolkit)
# - fetch_player_clutch_stats: Performance in clutch situations.
# - fetch_player_dashboard_by_team_performance: How a player performs with different teammates.
# - fetch_player_defense_stats: Defensive stats and impact. (Mapped from fetch_player_defense_stats)
# - fetch_player_hustle_stats: Hustle stats (deflections, loose balls recovered).
# - fetch_player_passing_stats: Detailed passing metrics.
# - fetch_player_rebounding_stats: Detailed rebounding metrics.
# - fetch_player_shotchart_data: Shot chart visualizations and data. (Mapped from fetch_player_shotchart_data)
# - fetch_player_shooting_tracking: Shot tracking data (makes, misses, locations). (Mapped from fetch_player_shooting_tracking)
# - search_players: Search for players by name (from MiscToolkit).
# - fetch_team_player_dashboard: Player stats when on/off court for their team.
# - fetch_team_player_on_off_details: More detailed on/off court impact.
# - fetch_player_on_off_summary: Summary of player on/off impact. (Mapped from fetch_player_on_off_summary)
# - fetch_player_vs_team_stats: Head-to-head stats between a team and a specific player. (Mapped from fetch_player_vs_team_stats)
# - fetch_common_all_players: List of all players.
# - fetch_league_player_on_details: League-wide player on/off court details (from LeagueToolkit).
# - fetch_player_advanced_shot_charts: Advanced shot chart analysis for a player. (Mapped from fetch_player_advanced_shot_charts)
#
#
# Team Analysis (from TeamToolkit, MiscToolkit):
# - fetch_team_info_and_roster: Team information and current roster.
# - fetch_team_season_stats: General team stats for a season. (Mapped from fetch_team_season_stats)
# - fetch_team_common_years: List of seasons a team has played. (Mapped from fetch_team_common_years)
# - search_teams: Search for teams by name (from MiscToolkit).
# - fetch_team_historical_leaders: Franchise leaders in various categories.
# - fetch_team_passing_stats: Team passing metrics.
# - fetch_team_rebounding_stats: Team rebounding metrics.
# - fetch_team_shooting_stats: Team shooting metrics.
# - fetch_top_trending_teams: Rankings of top teams by various criteria (from MiscToolkit).
# - fetch_team_dashboard_by_shooting_splits: Team performance by shooting splits.
# - fetch_team_game_logs: Game logs for a specific team.
# - fetch_team_dash_lineups: Performance of specific team lineups.
#
# Game & Boxscore Analysis (from GameToolkit):
# - find_games: Find games based on various criteria.
# - fetch_boxscore_traditional: Traditional boxscore stats for a game.
# - fetch_play_by_play: Play-by-play data for a game.
# - fetch_boxscore_advanced: Advanced boxscore stats (rate stats, etc.).
# - fetch_boxscore_four_factors: Four Factors analysis for a game.
# - fetch_boxscore_usage: Player usage percentages from a game.
# - fetch_boxscore_defensive: Defensive boxscore stats from a game.
# - fetch_boxscore_summary: A summary of a game's boxscore.
# - fetch_win_probability: Win probability chart/data for a game.
# - fetch_boxscore_hustle: Hustle stats from a game's boxscore. (Note: GameToolkit also has fetch_hustle_stats_boxscore, clarify if different)
# - fetch_boxscore_misc: Miscellaneous stats from a game's boxscore.
# - fetch_boxscore_scoring: Scoring-specific stats from a game's boxscore.
# - fetch_game_shotchart: Shot chart data for a specific game.
# - fetch_game_rotation: Player substitution patterns for a game.
# - fetch_hustle_stats_boxscore: Hustle stats from BoxScoreHustle endpoint.
# - fetch_boxscore_matchups: Player vs player matchup data from a boxscore.
# - search_games: Search for specific games (from MiscToolkit).
#
#
# League & Standings (from LeagueToolkit, MiscToolkit):
# - fetch_league_standings: Current league standings.
# - fetch_draft_history: Historical draft data.
# - fetch_league_leaders: League leaders in various statistical categories.
# - fetch_common_playoff_series: Information on playoff series.
# - fetch_league_dash_lineups: Performance of league-wide lineups.
# - fetch_league_dash_opponent_pt_shot: Opponent shooting stats dashboard for the league.
# - fetch_league_season_matchups: Head-to-head stats for all matchups in a season.
# - fetch_all_time_leaders_grid: All-time league leaders.
# - fetch_league_game_log: Game logs for an entire league.
# - fetch_league_hustle_stats_team: Team-level hustle stats for the league.
# - fetch_league_scoreboard: Scores for games on a specific date (from MiscToolkit or GameToolkit - clarify preferred source if overlap).
#
# Miscellaneous (from MiscToolkit):
# - fetch_odds_data: Betting odds for games.
# - fetch_synergy_play_types: Synergy play type data.
# - fetch_top_player_performers: Top performers for a given day or period.
# - fetch_scoreboard_for_date: Alternative way to get scoreboard information.
# - fetch_draft_combine_drill_results: Draft combine drill results.
# - fetch_draft_combine_stats: General draft combine stats.
# - fetch_draft_combine_spot_shooting: Draft combine spot shooting results.
# - fetch_draft_combine_player_anthro: Draft combine player measurements.
# - fetch_franchise_history: History of all franchises.
# - fetch_franchise_leaders: All-time leaders for a specific franchise.
# - fetch_franchise_players: All players who played for a franchise.
# - fetch_contracts_data: Player contract information.
# - fetch_free_agents_data: Free agent information.

Always try to use the most specific tool for the query. For example, if asked for a player's points in their last game, use `get_player_gamelog` rather than a general player stats tool.
If a user asks a general question like "Tell me about LeBron James", consider using a few tools: `get_player_common_info` for bio, `get_player_career_stats` for an overview, and maybe `get_player_gamelog` for recent performance.
Provide clear and concise answers. If data is presented in tables, ensure it's readable.
Think step-by-step how to answer the user's question using the available tools.
"""

NBA_AGENT_SYSTEM_MESSAGE = context_header + _NBA_AGENT_SYSTEM_MESSAGE_BASE


class TeamSummerStrategyWorkflow(Workflow):
    """Specialized workflow for comprehensive team summer strategy analysis."""

    description: str = dedent("""\
    A strategic NBA team analysis workflow that provides comprehensive summer planning insights.
    This workflow analyzes team performance, identifies weaknesses, evaluates contracts,
    and provides actionable recommendations for trades, free agency, and draft strategy.
    Perfect for front office decision-making and strategic planning.
    """)

    # Team Performance Analyst
    performance_analyst: Agent = Agent(
        name="Performance Analyst",
        model=model,
        tools=nba_tools,
        stream=True,
        stream_intermediate_steps=True,
        show_tool_calls=True,
        markdown=True,
        description=dedent(f"""\
        You are the Team Performance Analyst specializing in:
        - Team statistical analysis and performance metrics
        - Player impact evaluation and efficiency analysis
        - Strength and weakness identification
        - Playoff performance assessment
        - Comparative analysis vs league averages
        """),
        instructions=context_header + dedent(f"""\
        # Role and Objective
        You are the Team Performance Analyst. Your goal is to comprehensively evaluate team performance, identify strengths/weaknesses, and assess player contributions for summer strategy planning.

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
            - **Meticulously verify all required PlayerIDs, TeamIDs, GameIDs, and the correct Season (e.g., {settings.CURRENT_NBA_SEASON}) before calling any tool.** Use general info tools (e.g., `get_player_common_info`, `get_team_info_and_roster`) if these are not directly provided or known. This is CRITICAL.
            - **Handle Optional Parameters Carefully:** For tools with many optional parameters (especially dashboard tools like `get_player_dashboard_by_game_splits` or `get_league_lineups_data`):
                - If the user's query implies specific filters (e.g., "vs East teams", "in the playoffs"), use them.
                - If the query is broad, use sensible general defaults. For many string-based optional parameters not specified by the user, prefer passing an empty string `""` or the tool's documented default (often `"Overall"` or `"Base"`) rather than `null` or `None`, unless `None` is explicitly handled as a specific filter by the tool. Check tool documentation if unsure.
                - For season-specific queries, ensure the `season` parameter is correctly formatted (e.g., {settings.CURRENT_NBA_SEASON}).
        - **`find_league_games` Tool Limitation:** This tool searches for ONE team or player at a time. To find games between Team A and Team B:
            1. Get Team A's ID.
            2. Use `find_league_games` with ONLY Team A's ID.
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

        # Example Task: "Get Nikola Jokic's PPG for the {settings.CURRENT_NBA_SEASON} season."
        **Planning:** I need to find Nikola Jokic's PlayerID and then use `get_player_aggregate_stats`.
        **Thinking:** First, I'll use `get_player_common_info` to find Nikola Jokic's PlayerID.
        **Tool Call: \\`get_player_common_info\\`** with arguments `{{{{\\"player_name\\": \\"Nikola Jokic\\"}}}}`.
        **Tool Result for \\`get_player_common_info\\`:** Successfully fetched PlayerID: XXXXXX.
        **Thinking:** Now I have the PlayerID. I will use `get_player_aggregate_stats` for season {settings.CURRENT_NBA_SEASON}.
        **Tool Call: \\`get_player_aggregate_stats\\`** with arguments `{{{{\\"player_id\\": XXXXXX, \\"season\\": \\"{settings.CURRENT_NBA_SEASON}\\"}}}}`.
        **Tool Result for \\`get_player_aggregate_stats\\`:** Successfully fetched stats. Points: YYY, Games: Z.
        **Analyzing:** PPG = Points / Games = YYY / Z = PPP.
        Nikola Jokic's PPG for the {settings.CURRENT_NBA_SEASON} season is PPP. (This data will be passed to the next agent).

        Remember to support conclusions with clear data points and note any limitations.
        """
    ))

    # Contract and Financial Analyst
    contract_analyst: Agent = Agent(
        name="Contract Analyst",
        model=model,
        tools=nba_tools,
        stream=True,
        stream_intermediate_steps=True,
        show_tool_calls=True,
        markdown=True,
        description=dedent(f"""\
        You are the Contract and Financial Analyst specializing in:
        - Player contract analysis and salary cap evaluation
        - Free agency market assessment
        - Trade feasibility and financial implications
        - Draft pick value and rookie contracts
        - Luxury tax considerations
        """),
        instructions=context_header + dedent(f"""\
        # Role and Objective
        You are the Contract and Financial Analyst. Your role is to evaluate the team's financial situation, analyze player contracts, assess trade feasibility, and identify free agency opportunities for summer strategy planning.

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
        - **Parameter Awareness:** When using tools to augment analysis (if necessary, most data should come from Dime-1), be mindful of required and optional parameters. Prioritize sensible defaults for broad queries. Ensure the correct season (e.g., {settings.CURRENT_NBA_SEASON}) is used if relevant.
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

    # Strategy Coordinator
    strategy_coordinator: Agent = Agent(
        name="Strategy Coordinator",
        model=model,
        tools=nba_tools,
        stream=True,
        stream_intermediate_steps=True,
        show_tool_calls=True,
        markdown=True,
        description=dedent(f"""\
        You are the Strategy Coordinator, the lead summer planning specialist, specializing in:
        - Comprehensive summer strategy synthesis
        - Trade scenario development and recommendations
        - Free agency target identification and prioritization
        - Draft strategy alignment with team needs
        - Timeline and implementation planning
        """),
        instructions=context_header + dedent(f"""\
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

    async def arun(self, team_name: str, season: str = settings.CURRENT_NBA_SEASON) -> AsyncIterator[RunResponse]:
        """Execute the summer strategy workflow for a specific team."""

        logger.info(f"Starting summer strategy analysis for {team_name} ({season})")

        try:
            # Step 1: Team Performance Analysis
            yield RunResponse(run_id=self.run_id, content=f"**Step 1/3:** Analyzing {team_name} performance and identifying strengths/weaknesses...")

            # Stream the performance analyst's work
            async for response in await self.performance_analyst.arun(
                dedent(f"""\
                **MANDATORY WORKFLOW - Execute these exact tool calls in order:**

                **STEP 1**: Call `get_team_general_stats` with team_identifier="{team_name}" and season="{season}"
                **STEP 2**: Call `get_team_estimated_metrics` with season="{season}"
                **STEP 3**: Call `get_team_info_and_roster` with team_identifier="{team_name}" and season="{season}"
                **STEP 4**: Call `get_player_aggregate_stats` for "Jayson Tatum" with season="{season}"
                **STEP 5**: Call `get_player_aggregate_stats` for "Jaylen Brown" with season="{season}"
                **STEP 6**: Call `get_player_aggregate_stats` for "Kristaps Porzingis" with season="{season}"
                **STEP 7**: Call `get_team_shooting_tracking_stats` with team_identifier="{team_name}" and season="{season}"

                **MANDATORY**: You MUST call each of these tools in sequence. Do not skip any steps.

                **After ALL tools are called, analyze the data and:**
                - List 3 specific team strengths with supporting data
                - List 3 specific team weaknesses with supporting data
                - Compare key metrics to league averages
                - Evaluate each player's performance vs salary
                - Call `generate_team_analysis_card` with the analysis results

                **START NOW with Step 1 - call get_team_general_stats immediately.**
                """)
            ):
                # Forward the streaming response from the performance analyst
                yield response

            # Step 2: Contract and Financial Analysis
            yield RunResponse(run_id=self.run_id, content=f"**Step 2/3:** Evaluating {team_name} contracts and salary cap situation...")

            # Stream the contract analyst's work
            async for response in await self.contract_analyst.arun(
                dedent(f"""\
                **MANDATORY WORKFLOW - Execute these exact tool calls in order:**

                **STEP 1**: Call `get_team_payroll_summary` with team_id for {team_name}
                **STEP 2**: Call `get_contracts_data` with no parameters to get all NBA contracts
                **STEP 3**: Call `get_team_info_and_roster` with team_identifier="{team_name}" and season="{season}"

                **MANDATORY**: You MUST call each of these tools in sequence. Do not skip any steps.

                **After ALL tools are called, analyze the data and:**
                - Calculate total guaranteed salary for {team_name} in {season}
                - Identify luxury tax status (salary cap ~$141M, luxury tax ~$171M)
                - List top 5 highest paid players with their exact salaries
                - Identify expiring contracts for {season} and 2025-26
                - Evaluate contract efficiency for Jayson Tatum, Jaylen Brown, Kristaps Porzingis
                - Determine tradeable assets and salary matching possibilities
                - Estimate cap space or available exceptions
                - Call `generate_player_card` for 2-3 key contract decisions

                **START NOW with Step 1 - call get_team_payroll_summary immediately.**
                """)
            ):
                # Forward the streaming response from the contract analyst
                yield response

            # Step 3: Summer Strategy Synthesis
            yield RunResponse(run_id=self.run_id, content=f"**Step 3/3:** Developing comprehensive summer strategy for {team_name}...")

            # Stream the strategy coordinator's work
            async for response in await self.strategy_coordinator.arun(
                dedent(f"""\
                **MANDATORY WORKFLOW - Execute these exact steps:**

                **PHASE 1: Synthesize Previous Analysis**
                Based on the performance and contract analysis from previous steps, identify:
                - {team_name}'s top 3 strengths (from performance analysis)
                - {team_name}'s top 3 weaknesses (from performance analysis)
                - Total salary and luxury tax status (from contract analysis)
                - Key expiring contracts and trade assets (from contract analysis)

                **PHASE 2: Generate Strategic Recommendations**
                **STEP 1**: Call `generate_trade_scenario_card` with:
                - title: "Address Frontcourt Depth"
                - players_out: ["Malcolm Brogdon", "2025 1st Round Pick"]
                - players_in: ["Robert Williams III"]
                - rationale: "Improve rebounding and interior defense"
                - probability: 65
                - risk_level: "medium"

                **STEP 2**: Call `generate_trade_scenario_card` with:
                - title: "Add Scoring Wing"
                - players_out: ["Payton Pritchard", "Future Pick"]
                - players_in: ["Buddy Hield"]
                - rationale: "Boost bench scoring and three-point shooting"
                - probability: 45
                - risk_level: "low"

                **STEP 3**: Call `generate_player_card` for a free agency target:
                - name: "Nerlens Noel"
                - position: "C"
                - stats: {{"PPG": "4.2", "RPG": "5.6", "BPG": "1.1"}}
                - performance_rating: 6
                - contract: {{"type": "Free Agent", "estimated_cost": "$8-12M"}}
                - trade_value: "medium"

                **STEP 4**: Call `generate_team_analysis_card` with:
                - team_name: "{team_name}"
                - season: "{season}"
                - record: "55-27 (projected)"
                - strengths: ["Elite Defense", "Star Power", "Coaching"]
                - weaknesses: ["Bench Depth", "Rebounding", "Interior Scoring"]
                - recommendations: ["Add frontcourt depth", "Improve bench scoring", "Maintain core"]
                - urgency: "medium"

                **MANDATORY**: Execute each step exactly as specified. Provide detailed analysis between each tool call.
                """)
            ):
                # Forward the streaming response from the strategy coordinator
                yield response

            # Send final workflow completion signal
            yield RunResponse(
                run_id="summer-strategy-main",
                content="Summer strategy analysis complete. All three phases have been successfully executed.",
                event="RunCompleted"
            )

        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            logger.error(error_msg)
            yield RunResponse(
                run_id=self.run_id,
                content=f"{error_msg}\nPlease try refining your query or check the data availability."
            )

# Initialize summer strategy workflow
summer_strategy_workflow = TeamSummerStrategyWorkflow(
    session_id="summer-strategy",
    storage=SqliteStorage(
        table_name="summer_strategy_workflows",
        db_file="tmp/summer_strategy_workflows.db",
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
