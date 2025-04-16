from nba_api.stats.library.parameters import SeasonTypeAllStar, PerModeDetailed, PerMode36, LeagueID, PerMode48
from config import CURRENT_SEASON

# Helper function for enum descriptions
def get_enum_description(enum_class, default_value):
    valid_options = [getattr(enum_class, attr) for attr in dir(enum_class) if not attr.startswith('_') and isinstance(getattr(enum_class, attr), str)]
    return f"Options: {', '.join(valid_options)}. Defaults to '{default_value}'."

# Player Tools Declarations
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
    "description": "Fetches player shot tracking stats using the player's ID.", # Updated description
    "parameters": {
        "type": "object",
        "properties": {
            "player_id": {
                "type": "string",
                "description": "The NBA player ID.",
            },
        },
        "required": ["player_id"],
    },
}

get_player_shotchart_declaration = {
    "name": "get_player_shotchart",
    "description": "Fetches a player's shot chart data for detailed shooting analysis.",
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

get_player_defense_stats_declaration = {
    "name": "get_player_defense_stats",
    "description": "Fetches detailed defensive statistics for a player.",
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

get_player_hustle_stats_declaration = {
    "name": "get_player_hustle_stats",
    "description": "Fetches players' hustle stats like deflections, loose balls recovered, screen assists etc.",
    "parameters": {
        "type": "object",
        "properties": {
            "season": {
                "type": "string",
                "description": f"Season identifier (e.g., '2023-24'). Defaults to current ({CURRENT_SEASON}).",
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
        "required": [],
    },
}

# Team Tools Declarations
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

get_team_shooting_stats_declaration = {
    "name": "get_team_shooting_stats",
    "description": "Fetches team shooting tracking stats.",
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

get_team_rebounding_stats_declaration = {
    "name": "get_team_rebounding_stats",
    "description": "Fetches team rebounding tracking stats.",
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

get_team_lineups_declaration = {
    "name": "get_team_lineups",
    "description": "Fetches detailed lineup statistics with various filtering options.",
    "parameters": {
        "type": "object",
        "properties": {
            "team_id": {
                "type": ["integer", "null"],
                "description": "NBA team ID. If None, returns all team lineups."
            },
            "season": {
                "type": "string",
                "description": f"Season identifier (e.g., '2023-24'). Defaults to current ({CURRENT_SEASON})."
            },
            "season_type": {
                "type": "string",
                "description": get_enum_description(SeasonTypeAllStar, SeasonTypeAllStar.regular)
            },
            "per_mode": {
                "type": "string",
                "description": get_enum_description(PerModeDetailed, PerModeDetailed.per_game)
            },
            "month": {
                "type": "integer",
                "description": "Filter by month (0 for all). Defaults to 0."
            },
            "date_from": {
                "type": ["string", "null"],
                "description": "Start date filter (YYYY-MM-DD)."
            },
            "date_to": {
                "type": ["string", "null"],
                "description": "End date filter (YYYY-MM-DD)."
            },
            "opponent_team_id": {
                "type": "integer",
                "description": "Filter by opponent (0 for all). Defaults to 0."
            },
            "vs_conference": {
                "type": ["string", "null"],
                "description": "Filter by conference."
            },
            "vs_division": {
                "type": ["string", "null"],
                "description": "Filter by division."
            },
            "game_segment": {
                "type": ["string", "null"],
                "description": "Filter by game segment."
            },
            "period": {
                "type": "integer",
                "description": "Filter by period (0 for all). Defaults to 0."
            },
            "last_n_games": {
                "type": "integer",
                "description": "Filter by last N games (0 for all). Defaults to 0."
            }
        },
        "required": ["season"]
    }
}

# Game Tools Declarations
find_games_declaration = {
    "name": "find_games",
    "description": "Finds games based on Player/Team ID and optional filters (season, type, league, date range).", # Updated description
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
                "description": "Player ID. Required if player_or_team='P'. Omit or pass null otherwise.",
            },
            "team_id": {
                "type": "integer",
                "description": "Team ID. Required if player_or_team='T'. Omit or pass null otherwise.",
            },
            "season": { # Added parameter
                "type": "string",
                "description": "Optional season identifier (e.g., '2023-24').",
            },
            "season_type": { # Added parameter
                "type": "string",
                "description": "Optional season type (e.g., 'Regular Season', 'Playoffs').",
            },
            "league_id": { # Added parameter
                "type": "string",
                "description": "Optional league ID (e.g., '00' for NBA).",
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
        # Note: player_id/team_id are conditionally required based on player_or_team,
        # but the schema doesn't easily support this. Agent instructions handle it.
        "required": [], # Removed explicit requirement here, handled by logic/instructions
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

# Note: get_boxscore_advanced_declaration removed as tool is disabled.
# Note: get_boxscore_fourfactors_declaration removed as tool is disabled.

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

# League Tools Declarations
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
        "required": [],
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

get_player_profile_declaration = {
    "name": "get_player_profile",
    "description": "Fetches a comprehensive player profile including career totals, season totals, highs, and next game info.",
    "parameters": {
        "type": "object",
        "properties": {
            "player_name": {
                "type": "string",
                "description": "Full name of the player.",
            },
            "per_mode": {
                "type": "string",
                "description": get_enum_description(PerModeDetailed, PerModeDetailed.per_game),
            },
        },
        "required": ["player_name"],
    },
}

# Combined declarations list
all_function_declarations = [
    get_player_info_declaration,
    get_player_hustle_stats_declaration,
    get_team_lineups_declaration,
    get_player_profile_declaration,
    get_player_gamelog_declaration,
    get_player_career_stats_declaration,
    get_player_awards_declaration,
    get_player_clutch_stats_declaration,
    get_player_passing_stats_declaration,
    get_player_rebounding_stats_declaration,
    get_player_shots_tracking_declaration,
    get_player_shotchart_declaration,
    get_player_defense_stats_declaration,
    get_team_info_and_roster_declaration,
    find_games_declaration,
    get_boxscore_traditional_declaration,
    # get_boxscore_advanced_declaration removed
    # get_boxscore_fourfactors_declaration removed
    get_playbyplay_declaration,
    get_league_standings_declaration,
    get_scoreboard_declaration,
    get_draft_history_declaration,
    get_league_leaders_declaration,
]