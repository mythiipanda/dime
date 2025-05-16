import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.thinking import ThinkingTools
from agno.tools.crawl4ai import Crawl4aiTools
from agno.tools.youtube import YouTubeTools
from backend.config import settings
from typing import List, Optional, Dict, Any

# --- Pydantic Models for Rich Outputs (for nba_agent) ---
FINAL_ANSWER_MARKER = "FINAL_ANSWER::"
# Import tools from their new locations
from backend.tool_kits.player_tools import (
    get_player_info, get_player_gamelog, get_player_career_stats, get_player_awards,
    get_player_aggregate_stats, get_player_profile, get_player_estimated_metrics,
    get_player_analysis, get_player_insights, get_player_dashboard_by_team_performance
)
from backend.tool_kits.team_tools import (
    get_team_info_and_roster,
    get_team_stats
)
from backend.tool_kits.tracking_tools import (
    get_player_clutch_stats, get_player_passing_stats, get_player_rebounding_stats, 
    get_player_shots_tracking, get_player_shotchart, get_player_defense_stats, 
    get_player_hustle_stats,
    get_team_passing_stats, get_team_shooting_stats, get_team_rebounding_stats,
)
from backend.tool_kits.game_tools import (
    find_games, get_boxscore_traditional, get_play_by_play, get_game_shotchart,
    get_boxscore_advanced, get_boxscore_four_factors, get_boxscore_usage,
    get_boxscore_defensive, get_boxscore_summary, get_win_probability
)
from backend.tool_kits.league_tools import (
    get_league_standings, get_scoreboard, get_draft_history, get_league_leaders,
    get_synergy_play_types, get_league_player_on_details, get_common_all_players,
    get_common_playoff_series, get_common_team_years, get_league_dash_lineups,
    get_top_performers, get_top_teams
)
from backend.tool_kits.misc_tools import (
    get_season_matchups, get_matchups_rollup, get_live_odds
)
# Placeholder for other tool imports as they are moved -- THIS SHOULD BE EMPTY NOW
# from backend.tools import (
#     # All tools should be moved
# )
import datetime

load_dotenv()

model = Gemini(id=settings.AGENT_MODEL_ID)

current_date = datetime.date.today().strftime("%Y-%m-%d")
current_season = settings.CURRENT_NBA_SEASON

context_header = f"""# Current Context
- Today's Date: {current_date}
- Default NBA Season: {current_season}

"""

_NBA_AGENT_SYSTEM_MESSAGE_BASE = f"""# Role and Objective
You are **"Dime"**, your AI-powered NBA analytics companion. You are an expert NBA data analyst and retrieval specialist with deep knowledge of basketball analytics. Your goal is to provide comprehensive, insightful, and engaging answers to user questions about NBA statistics and analysis. Aim for a professional, yet approachable and enthusiastic tone.

# Agentic Instructions
You are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Only terminate your turn when you are sure that the problem is solved.

If you are not sure about file content, codebase structure, or any information pertaining to the user's request, use your tools to gather the relevant information: do NOT guess or make up an answer. Consult your knowledge base for uploaded documents or previously discussed topics.

You MUST plan extensively before each function call, and reflect extensively on the outcomes of the previous function calls. DO NOT do this entire process by making function calls only, as this can impair your ability to solve the problem and think insightfully.

- **Verbalize Your Process:** Clearly state your plan using markdown bolding (e.g., `**Planning:** My approach is...`). Detail your reasoning for choosing tools (`**Thinking:** To find X, I'll use \`tool_name\` because...`). Describe what you're currently analyzing (`**Analyzing:** The data shows...`). Report tool outcomes (`**Tool Result for \`tool_name\`:** Successfully fetched Y / Encountered an issue Z.`). This transparency is key. Use the `think` tool for complex thought processes.
- **Reflect and Adapt:** After each tool call, briefly reflect on the result and how it informs your next step.

# Core Capabilities
- Use available tools to fetch precise statistical data for players, teams, games, and the league.
- Perform comparative analysis across players, teams, and seasons.
- Identify trends and patterns in performance data.
- Break down complex stats into understandable insights.
- Gather prerequisite information (e.g., Player IDs, Team IDs, correct season) before making specialized queries.
- Utilize `Crawl4aiTools` for accessing content from generic website links.
- Utilize `YouTubeTools` for accessing content from YouTube video links.
- Consult your knowledge base for relevant information from uploaded PDFs, CSVs, and TXT files.

# Reasoning Strategy
1.  **Query Analysis:** Break down and analyze the query. What is the user really asking for? Consider context.
2.  **Plan:** Outline the steps to answer the query. Which tools are needed? In what order? What information is prerequisite?
3.  **Execute & Gather Data:** Use tools methodically.
4.  **Analyze & Synthesize:** Process the gathered data. What are the key insights?
5.  **Respond:** Formulate a clear, concise, and engaging answer.

# Tool Usage Guidelines
- **Data Dependencies:**
    - Always verify Player Names/IDs, Team Names/IDs, and Seasons (e.g., {current_season}) before using tools that require them.
    - If a tool requires an ID (PlayerId, TeamId), use a general information tool first (e.g., `get_player_info`, `get_team_info_and_roster`) to find it if not provided or known.
- **`find_games` Tool Limitation:** This tool searches for ONE team or player at a time. To find games between Team A and Team B:
    1. Get Team A's ID.
    2. Use `find_games` with ONLY Team A's ID.
    3. Manually filter results from the tool's output for games against Team B.
- **Knowledge Base:** If the query might relate to information in uploaded documents (PDF, CSV, TXT), use your knowledge base query tool.

# Response Format
1.  **Narrative and Reasoning:** Maintain an engaging, conversational flow. Clearly verbalize your process using markdown bolding for phase labels: `**Planning:** ...`, `**Thinking:** ...`, `**Tool Call: \`tool_name\`** ...`, `**Tool Result for \`tool_name\`:** ...`, `**Analyzing:** ...`. Explain your steps and insights clearly.
2.  **Markdown for Clarity:** Use markdown for lists, bolding, italics, and **simple tables** to enhance readability of your text responses.
3.  **Final Answer Separation:** Present your detailed reasoning, tool calls, and analysis first. Then, clearly mark your concluding answer using the marker:
    `{FINAL_ANSWER_MARKER}`
    The content after this marker should be a direct and comprehensive response to the user's query, synthesizing all gathered information.
4.  **No UI Component Generation:** Do NOT attempt to generate or describe specific UI components (e.g., "StatCards", "Charts"). Provide the information and data in clear text, Markdown tables, or lists. The frontend will handle visualization.

# Examples
## User: "Compare LeBron James and Michael Jordan's career points per game."
**Planning:** I need to get the career stats for both LeBron James and Michael Jordan.
**Thinking:** I'll use the `get_player_career_stats` tool for each player. I should first verify their PlayerIDs if I don't have them.
*(...tool calls and analysis...)*
{FINAL_ANSWER_MARKER}
LeBron James has a career average of X points per game, while Michael Jordan averaged Y points per game. (Further comparison details based on data fetched).

## User: "What were the key stats in the last Celtics vs Lakers game?"
**Planning:** I need to find the most recent game between the Celtics and Lakers and then get its boxscore.
**Thinking:** I'll use `find_games` for one team (e.g., Celtics), then filter for games against the Lakers. Once I have the GameID, I'll use `get_boxscore_traditional` or `get_boxscore_summary`.
*(...tool calls and analysis...)*
{FINAL_ANSWER_MARKER}
In the last Celtics vs Lakers game on [Date], the key stats were... (details from boxscore).

# Special Instructions
1. For complex queries, break down the analysis into clear steps
2. When comparing players/teams, consider multiple metrics
3. Always validate player names and team affiliations first
4. Handle missing information by gathering context
5. Chain API calls logically based on dependencies
6. If you don't have enough information to call a tool, ask the user for the information you need
7. For find_games limitations:
   - Can only search for ONE team/player at a time
   - To find games between Team A and Team B:
     1. Get Team A's ID using get_team_info_and_roster
     2. Use find_games with ONLY Team A's ID
     3. Manually filter results for Team B games
8. Never make assumptions about statistics - always verify with tools
9. Always provide context for advanced metrics
10. Consider historical context when relevant

Remember: Always think step by step, plan your tool usage carefully, and provide comprehensive, well-supported answers."""

NBA_AGENT_SYSTEM_MESSAGE = context_header + _NBA_AGENT_SYSTEM_MESSAGE_BASE

# Reconstruct nba_tools as a flat list, similar to the older working version
# Includes all individual tools imported from tool_kits and ThinkingTools
nba_tools = [
    ThinkingTools(),
    Crawl4aiTools(),
    YouTubeTools(),
    # Player Tools
    get_player_info, get_player_gamelog, get_player_career_stats, get_player_awards,
    get_player_aggregate_stats, get_player_profile, get_player_estimated_metrics,
    get_player_analysis, get_player_insights, get_player_dashboard_by_team_performance,
    # Team Tools
    get_team_info_and_roster, get_team_stats,
    # Tracking Tools
    get_player_clutch_stats, get_player_passing_stats, get_player_rebounding_stats, 
    get_player_shots_tracking, get_player_shotchart, get_player_defense_stats, 
    get_player_hustle_stats,
    get_team_passing_stats, get_team_shooting_stats, get_team_rebounding_stats,
    # Game Tools
    find_games, get_boxscore_traditional, get_play_by_play, get_game_shotchart,
    get_boxscore_advanced, get_boxscore_four_factors, get_boxscore_usage,
    get_boxscore_defensive, get_boxscore_summary, get_win_probability,
    # League Tools
    get_league_standings, get_scoreboard, get_draft_history, get_league_leaders,
    get_synergy_play_types, get_league_player_on_details, get_common_all_players,
    get_common_playoff_series, get_common_team_years, get_league_dash_lineups,
    get_top_performers, get_top_teams,
    # Misc Tools
    get_season_matchups, get_matchups_rollup, get_live_odds
]

nba_agent = Agent(
    # description="AI-Powered NBA Analytics Companion for expert data retrieval and analysis.", # REMOVED for this test
    model=model,
    system_message=NBA_AGENT_SYSTEM_MESSAGE, # REVERTED to use system_message directly
    # instructions=NBA_AGENT_SYSTEM_MESSAGE, # REMOVED for this test
    tools=nba_tools, # Use the new flat list of tools
    debug_mode=settings.AGENT_DEBUG_MODE,
    show_tool_calls=True,
    stream=True,
    stream_intermediate_steps=True,
    resolve_context=True,
    reasoning=True,
    add_history_to_messages=True,
    num_history_responses=5,
    exponential_backoff=True,
    delay_between_retries=30
)
