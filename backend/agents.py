import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.thinking import ThinkingTools
from config import AGENT_MODEL_ID, STORAGE_DB_FILE, AGENT_DEBUG_MODE, CURRENT_SEASON
from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, PerMode48
from tools import (
    get_player_info, get_player_gamelog, get_team_info_and_roster,
    get_player_career_stats, find_games, get_player_awards,
    get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors,
    get_league_standings, get_scoreboard, get_playbyplay,
    get_draft_history, get_league_leaders,
    get_team_passing_stats, get_player_passing_stats,
    get_player_clutch_stats, get_player_shots_tracking,
    get_player_rebounding_stats
)
import datetime # Import datetime

# Load environment variables
load_dotenv()

# --- Function Declarations for Gemini ---

# Define a helper to get enum values for descriptions
def get_enum_description(enum_class, default_value):
    valid_options = [getattr(enum_class, attr) for attr in dir(enum_class) if not attr.startswith('_') and isinstance(getattr(enum_class, attr), str)]
    return f"Options: {', '.join(valid_options)}. Defaults to '{default_value}'."

# Player Tools
get_player_info_declaration = {
    "name": "get_player_info",
    "description": "Fetches basic player information and headline stats.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
        },
        "required": ["player_name"],
    },
}

get_player_gamelog_declaration = {
    "name": "get_player_gamelog",
    "description": "Fetches the game log for a player and season.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2023-24').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
        },
        "required": ["player_name", "season"],
    },
}

get_player_career_stats_declaration = {
    "name": "get_player_career_stats",
    "description": "Fetches player career statistics (Regular Season).",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "per_mode36": {
                "type": "string",
                "description": get_enum_description(PerMode36, PerMode36.per_game),
            },
        },
        "required": ["player_name"],
    },
}

get_player_awards_declaration = {
    "name": "get_player_awards",
    "description": "Fetches the awards won by a specific player.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
        },
        "required": ["player_name"],
    },
}

get_player_clutch_stats_declaration = {
    "name": "get_player_clutch_stats",
    "description": "Fetches player stats in clutch situations.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2023-24').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
        },
        "required": ["player_name", "season"],
    },
}

get_player_passing_stats_declaration = {
    "name": "get_player_passing_stats",
    "description": "Fetches player passing tracking stats (passes made/received).",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2023-24').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
            "per_mode": {
                "type": "string",
                "description": get_enum_description(PerModeDetailed, PerModeDetailed.per_game),
            },
        },
        "required": ["player_name", "season"],
    },
}

get_player_rebounding_stats_declaration = {
    "name": "get_player_rebounding_stats",
    "description": "Fetches player rebounding stats.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2023-24').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
        },
        "required": ["player_name", "season"],
    },
}

get_player_shots_tracking_declaration = {
    "name": "get_player_shots_tracking",
    "description": "Fetches player shot tracking stats.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2023-24').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
        },
        "required": ["player_name", "season"],
    },
}

# Team Tools
get_team_info_and_roster_declaration = {
    "name": "get_team_info_and_roster",
    "description": "Fetches team information, ranks, roster, and coaches.",
    "parameters": {
        "type": "object",
        "properties": {
            "team_identifier": {
                "type": "string",
                "description": "Team name, abbreviation (e.g., 'LAL'), or ID.",
            },
            "season": {
                "type": "string",
                "description": f"Season identifier (e.g., '2023-24'). Defaults to current ({CURRENT_SEASON}).",
            },
        },
        "required": ["team_identifier"],
    },
}

get_team_passing_stats_declaration = {
    "name": "get_team_passing_stats",
    "description": "Fetches team passing tracking stats (passes between players).",
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Name of the team or team abbreviation (e.g., 'Lakers' or 'LAL').",
            },
            "season": {
                "type": "string",
                "description": "Season identifier (e.g., '2022-23').",
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
            "per_mode": {
                "type": "string",
                "description": get_enum_description(PerModeDetailed, PerModeDetailed.per_game),
            },
        },
        "required": ["team_name", "season"],
    },
}

# Game Tools
find_games_declaration = {
    "name": "find_games",
    "description": "Finds games based on Player/Team ID and optional date range. Filtering by season/type is disabled.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_or_team": {
                "type": "string",
                "enum": ["P", "T"],
                "description": "Search by 'P' (Player) or 'T' (Team). Defaults to 'T'.",
            },
            "player_id": {
                "type": "integer",
                "description": "Required if player_or_team='P'. Omit or pass null otherwise.",
            },
            "team_id": {
                "type": "integer",
                "description": "Required if player_or_team='T'. Omit or pass null otherwise.",
            },
            "date_from": {
                "type": "string",
                "description": "Optional start date filter (MM/DD/YYYY).",
            },
            "date_to": {
                "type": "string",
                "description": "Optional end date filter (MM/DD/YYYY).",
            },
        },
        # Required depends on player_or_team, handled in tool logic
    },
}

get_boxscore_traditional_declaration = {
    "name": "get_boxscore_traditional",
    "description": "Fetches the traditional box score (V3) for a specific game.",
    "parameters": {
        "type": "object",
        "properties": {
            "game_id": {
                "type": "string",
                "description": "The 10-digit ID of the game.",
            },
        },
        "required": ["game_id"],
    },
}

get_boxscore_advanced_declaration = {
    "name": "get_boxscore_advanced",
    "description": "Fetches the advanced box score (V3) for a specific game (e.g., Ratings, Pace).",
    "parameters": {
        "type": "object",
        "properties": {
            "game_id": {
                "type": "string",
                "description": "The 10-digit ID of the game.",
            },
        },
        "required": ["game_id"],
    },
}

get_boxscore_fourfactors_declaration = {
    "name": "get_boxscore_fourfactors",
    "description": "Fetches the Four Factors box score (V3) for a specific game (e.g., eFG%, TOV Ratio).",
    "parameters": {
        "type": "object",
        "properties": {
            "game_id": {
                "type": "string",
                "description": "The 10-digit ID of the game.",
            },
        },
        "required": ["game_id"],
    },
}

get_playbyplay_declaration = {
    "name": "get_playbyplay",
    "description": "Fetches the play-by-play data (V3) for a specific game.",
    "parameters": {
        "type": "object",
        "properties": {
            "game_id": {
                "type": "string",
                "description": "The 10-digit ID of the game.",
            },
            "start_period": {
                "type": "integer",
                "description": "Optional starting period filter (0 for all). Defaults to 0.",
            },
            "end_period": {
                "type": "integer",
                "description": "Optional ending period filter (0 for all). Defaults to 0.",
            },
        },
        "required": ["game_id"],
    },
}

# League Tools
get_league_standings_declaration = {
    "name": "get_league_standings",
    "description": "Fetches the league standings (V3) for a specific season (Regular Season only).",
    "parameters": {
        "type": "object",
        "properties": {
            "season": {
                "type": "string",
                "description": f"Season identifier (e.g., '2023-24'). Defaults to current ({CURRENT_SEASON}).",
            },
        },
        "required": [], # Season has a default
    },
}

get_scoreboard_declaration = {
    "name": "get_scoreboard",
    "description": "Fetches the scoreboard (V2) for a specific date.",
    "parameters": {
        "type": "object",
        "properties": {
            "game_date": {
                "type": "string",
                "description": "Date string (YYYY-MM-DD). Defaults to today if null.",
            },
            "day_offset": {
                "type": "integer",
                "description": "Offset from game_date (e.g., -1 for yesterday). Defaults to 0.",
            },
        },
        "required": [],
    },
}

get_draft_history_declaration = {
    "name": "get_draft_history",
    "description": "Fetches the NBA draft history, optionally filtered by year.",
    "parameters": {
        "type": "object",
        "properties": {
            "season_year": {
                "type": "string",
                "description": "Optional year filter (YYYY format). If null, fetches all history.",
            },
        },
        "required": [],
    },
}

get_league_leaders_declaration = {
    "name": "get_league_leaders",
    "description": "Fetches league leaders for a specific stat category and season.",
    "parameters": {
        "type": "object",
        "properties": {
            "stat_category": {
                "type": "string",
                "description": "Stat category abbreviation (e.g., 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FT_PCT', 'FG3_PCT', 'EFF').",
            },
            "season": {
                "type": "string",
                "description": f"Season identifier (e.g., '2023-24'). Defaults to current ({CURRENT_SEASON}).",
            },
            "season_type_all_star": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular),
            },
            "per_mode48": {
                "type": "string",
                "description": get_enum_description(PerMode48, PerMode48.per_game),
            },
        },
        "required": ["stat_category"],
    },
}

# --- Combine all declarations ---
all_function_declarations = [
    get_player_info_declaration,
    get_player_gamelog_declaration,
    get_player_career_stats_declaration,
    get_player_awards_declaration,
    get_player_clutch_stats_declaration,
    get_player_passing_stats_declaration,
    get_player_rebounding_stats_declaration,
    get_player_shots_tracking_declaration,
    get_team_info_and_roster_declaration,
    get_team_passing_stats_declaration,
    find_games_declaration,
    get_boxscore_traditional_declaration,
    get_boxscore_advanced_declaration,
    get_boxscore_fourfactors_declaration,
    get_playbyplay_declaration,
    get_league_standings_declaration,
    get_scoreboard_declaration,
    get_draft_history_declaration,
    get_league_leaders_declaration,
]

# --- Initialize Model with Declarations ---
model = Gemini(
    id=AGENT_MODEL_ID,
    function_declarations=all_function_declarations
)

# --- Agent Definition ---

# Get current date
current_date = datetime.date.today().strftime("%Y-%m-%d")

# Construct the context string
context_header = f"Current Context:\n- Today's Date: {current_date}\n- Default NBA Season: {CURRENT_SEASON}\n\n"

# Original System Message (keep the detailed instructions)
_NBA_AGENT_SYSTEM_MESSAGE_BASE = """You are an expert NBA data analyst and retrieval specialist with deep knowledge of basketball analytics. Your goal is to provide comprehensive and insightful answers to user questions about NBA statistics and analysis.

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
- **Explain your plan:** For multi-step queries, explain your plan first.
- **Check Tool Schemas:** Before calling a tool, carefully check its function declaration (description, parameters, required fields) to ensure you provide the correct arguments.
- **Handle Optional Parameters:** Only provide parameters that are relevant to the current request. For example, in `find_games`, if `player_or_team='T'`, only provide `team_id`, do *not* provide `player_id`.
- **Ask for clarification:** If a request is ambiguous or missing necessary details (like a team ID for a team-specific query), ask the user for clarification, explaining *why* you need the information.
- **Handle `find_games` limitations:** The `find_games` tool can only search for games involving *one* specific team (or player) at a time. To find games between Team A and Team B:
    1. Get the Team ID for Team A (e.g., using `get_team_info_and_roster`).
    2. Use `find_games` with ONLY `team_id` for Team A.
    3. *Manually* filter the returned list of games to find those where the opponent was Team B. Explain this process.
- Cite specific sources and time periods for statistics.
- Acknowledge data limitations when they exist.
- Use appropriate statistical terminology.
- Chain information gathering logically.

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
- Game Analysis: get_boxscore_traditional, get_boxscore_advanced, get_boxscore_fourfactors, get_playbyplay
- League Info: get_league_standings, get_scoreboard, get_league_leaders, get_draft_history
- Game Finding: find_games (Note: Searches for ONE team/player at a time)

Information Gathering Strategy:
1. **Identify Goal & Tools:** Understand the user's request and identify the necessary tool(s).
2. **Check Tool Schema:** Review the function declaration for the chosen tool(s) to identify required and optional parameters.
3. **Gather Prerequisites:** Use tools like `get_player_info` or `get_team_info_and_roster` to find IDs or other info needed for subsequent tool calls. Verify context like season and team affiliation.
4. **Execute Step-by-Step:** Call tools sequentially, using results from previous steps. Provide only the necessary parameters based on the schema.
5. **Explain & Ask:** If information is missing, explain what you need (based on the tool schema) and why, then ask the user.
6. **Handle Limitations:** If a tool cannot directly answer (e.g., `find_games` for two teams), explain the limitation and the multi-step workaround you will perform based on the guidelines.

Special Instructions:
1. For complex queries, break down the analysis into clear steps
2. When comparing players/teams, consider multiple metrics
3. Always validate player names and team affiliations first
4. Handle missing information by gathering context
5. Chain API calls logically based on dependencies"""

# Prepend the context to the base system message
NBA_AGENT_SYSTEM_MESSAGE = context_header + _NBA_AGENT_SYSTEM_MESSAGE_BASE

# Define the enhanced agent WITHOUT the tools list, using function declarations in the model
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
    num_history_responses=10,
    debug_mode=AGENT_DEBUG_MODE,
    show_tool_calls=True,
    markdown=True,
    stream=True,
    stream_intermediate_steps=True,
    resolve_context=True,
    reasoning=True,
)

# Note: The example usage block with asyncio is removed as it's not needed for the agent definition itself.
# The test_agent.py script will handle running the agent.