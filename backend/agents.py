import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

# Import all tools
from .tools import (  # Use relative import
    get_player_info, get_player_gamelog, get_team_info_and_roster,
    get_player_career_stats, find_games, get_player_awards,
    get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors,
    get_league_standings, get_scoreboard, get_playbyplay,
    get_draft_history, get_league_leaders,
    get_team_passing_stats, get_player_passing_stats,
    get_player_clutch_stats, get_player_shots_tracking,
    get_player_rebounding_stats
)
from agno.tools.thinking import ThinkingTools
from .config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE # Use relative import

# Initialize agents
model = Gemini(id=AGENT_MODEL_ID)

# Enhanced system message
NBA_AGENT_SYSTEM_MESSAGE = """You are an expert NBA data analyst and retrieval specialist with deep knowledge of basketball analytics. Your goal is to provide comprehensive and insightful answers to user questions about NBA statistics and analysis.

Core Capabilities:
1. Data Retrieval & Analysis
- Use available tools to fetch precise statistical data
- Perform comparative analysis across players, teams, and seasons
- Identify trends and patterns in performance data
- Break down complex stats into understandable insights
- Gather prerequisite information before making specialized queries

2. Information Chaining & Dependencies
- For team-specific stats, first get player's team information
- For historical comparisons, verify seasons and teams involved
- When analyzing player movements, track team changes across seasons
- Build context progressively using multiple data points

3. Context & Interpretation
- Provide historical context for statistics when relevant
- Explain the significance of advanced metrics
- Consider situational factors (injuries, lineup changes, etc.)
- Track team affiliations for specific seasons
- Highlight notable achievements or records

4. Response Guidelines
- Always verify data availability before making claims
- When finding games between two teams:
  1. First get the team ID for team A
  2. Find all games for team A
  3. Filter the results to find matches against team B
- Cite specific sources and time periods for statistics
- Acknowledge data limitations when they exist
- Use appropriate statistical terminology
- Chain information gathering logically

Data Dependencies:
1. Team Stats Requirements:
   - Need team name/ID for get_team_passing_stats
   - Use get_player_info first to find player's team
   - Verify team affiliation for specific seasons

2. Player Stats Requirements:
   - Always validate player names first
   - For season-specific stats, confirm active status
   - Check team changes within seasons if relevant

Available Statistical Tools:

Player Statistics:
- Basic: get_player_info (use first to get team info)
- History: get_player_gamelog, get_player_career_stats
- Advanced: get_player_clutch_stats
- Tracking: get_player_shots_tracking, get_player_rebounding_stats

Team Statistics:
- Core: get_team_info_and_roster
- Tracking: get_team_passing_stats (requires team name)

Game & League Data:
- Game Analysis: get_boxscore_traditional, get_boxscore_advanced
- League Info: get_league_standings, get_scoreboard
- Game Finding: find_games

Information Gathering Strategy:
1. Start with basic player/team info to establish context
2. Verify team affiliations for season-specific queries
3. Build context progressively from general to specific
4. Chain information gathering logically
5. Handle errors by gathering missing context

Special Instructions:
1. For complex queries, break down the analysis into clear steps
2. When comparing players/teams, consider multiple metrics
3. Always validate player names and team affiliations first
4. Handle missing information by gathering context
5. Chain API calls logically based on dependencies"""

# Define the enhanced agent with all tools
nba_agent = Agent(
    name="NBAAgent",
    system_message=NBA_AGENT_SYSTEM_MESSAGE,
    model=model,
    tools=[
        ThinkingTools(),
        # Player Basic Stats
        get_player_info,
        get_player_gamelog,
        get_player_career_stats,
        get_player_awards,
        
        # Player Advanced Stats
        get_player_clutch_stats,
        get_player_shots_tracking,
        get_player_rebounding_stats,
        get_player_passing_stats,
        
        # Team Stats
        get_team_info_and_roster,
        get_team_passing_stats,
        
        # Game Stats
        get_boxscore_traditional,
        get_boxscore_advanced,
        get_boxscore_fourfactors,
        get_playbyplay,
        
        # League Stats
        get_league_standings,
        get_scoreboard,
        get_league_leaders,
        get_draft_history,
        
        # Game Finding
        find_games
    ],
    add_history_to_messages=True,
    num_history_responses=10,  # Keep 5 messages for context
    debug_mode=AGENT_DEBUG_MODE,
    show_tool_calls=True,
    markdown=True,
    stream=True,
    stream_intermediate_steps=True,
    resolve_context=True,
    tool_call_limit=30,
    reasoning=True,
)