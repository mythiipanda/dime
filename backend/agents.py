import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini

# Import all tools
from tools import (
    get_player_info, get_player_gamelog, get_team_info_and_roster, 
    get_player_career_stats, find_games, get_player_awards, 
    get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors, 
    get_league_standings, get_scoreboard, get_playbyplay, 
    get_draft_history, get_league_leaders, 
    get_team_passing_stats, get_team_shooting_stats, get_team_rebounding_stats,
    get_player_passing_stats, get_player_clutch_stats, get_team_clutch_stats,
    get_team_hustle_stats, get_player_hustle_stats, get_team_defense_stats,
    get_player_defense_stats, get_team_shot_chart, get_player_shot_chart,
    get_team_lineup_stats, get_player_impact_stats
)
from api_tools.tools import (
    get_player_shots_tracking, get_player_rebounding_stats,
    get_player_defense_tracking, get_player_drives_tracking,
    get_player_passing_tracking, get_player_touches_tracking,
    get_player_efficiency_tracking
)
from config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE

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

2. Context & Interpretation
- Provide historical context for statistics when relevant
- Explain the significance of advanced metrics
- Consider situational factors (injuries, lineup changes, etc.)
- Highlight notable achievements or records

3. Response Guidelines
- Always verify data availability before making claims
- Cite specific sources and time periods for statistics
- Acknowledge data limitations when they exist
- Use appropriate statistical terminology

Available Statistical Tools:

Player Statistics:
- Basic: get_player_info, get_player_gamelog, get_player_career_stats
- Advanced: get_player_impact_stats, get_player_clutch_stats
- Tracking: get_player_shots_tracking, get_player_rebounding_stats, get_player_defense_tracking
- Specialized: get_player_drives_tracking, get_player_passing_tracking, get_player_touches_tracking, get_player_efficiency_tracking
- Visual: get_player_shot_chart

Team Statistics:
- Core: get_team_info_and_roster, get_team_lineup_stats
- Advanced: get_team_clutch_stats, get_team_hustle_stats, get_team_defense_stats
- Tracking: get_team_passing_stats, get_team_shooting_stats, get_team_rebounding_stats
- Visual: get_team_shot_chart

Game & League Data:
- Game Analysis: get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors, get_playbyplay
- League Info: get_league_standings, get_scoreboard, get_league_leaders, get_draft_history
- Game Finding: find_games

Special Instructions:
1. For complex queries, break down the analysis into clear steps
2. When comparing players/teams, consider using multiple metrics for a complete picture
3. For tracking data, explain the significance of the metrics being used
4. When analyzing trends, consider both short-term and long-term patterns
5. For visual data (shot charts), describe key patterns and hot/cold zones
6. Always validate player names and team names before querying
7. Handle errors gracefully and suggest alternative approaches when data is unavailable"""

# Define the enhanced agent with all tools
nba_agent = Agent(
    name="NBAAgent",
    system_message=NBA_AGENT_SYSTEM_MESSAGE,
    model=model,
    tools=[
        # Player Basic Stats
        get_player_info,
        get_player_gamelog,
        get_player_career_stats,
        get_player_awards,
        
        # Player Advanced Stats
        get_player_impact_stats,
        get_player_clutch_stats,
        
        # Player Tracking Stats
        get_player_shots_tracking,
        get_player_rebounding_stats,
        get_player_defense_tracking,
        get_player_drives_tracking,
        get_player_passing_tracking,
        get_player_touches_tracking,
        get_player_efficiency_tracking,
        
        # Team Stats
        get_team_info_and_roster,
        get_team_lineup_stats,
        get_team_clutch_stats,
        get_team_hustle_stats,
        get_team_defense_stats,
        get_team_passing_stats,
        get_team_shooting_stats,
        get_team_rebounding_stats,
        
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
        
        # Visual Stats
        get_team_shot_chart,
        get_player_shot_chart,
        
        # Game Finding
        find_games
    ],
    add_history_to_messages=True,
    num_history_responses=5,  # Keep 5 messages for context
    debug_mode=AGENT_DEBUG_MODE
)