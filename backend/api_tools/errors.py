"""
Error message definitions for the NBA Analytics API.

This module contains all error messages used throughout the application, organized by category.
Each category of errors (player, team, game, etc.) is grouped together for better organization
and maintainability.
"""

class Errors:
    """
    A comprehensive collection of error messages used throughout the NBA Analytics API.
    
    The messages are organized into logical categories:
    - Player-related errors
    - Team-related errors
    - Game-related errors
    - League-related errors
    - General validation errors
    - Clutch stats-related errors
    
    Each error message can include placeholders (in {curly braces}) that will be
    filled in with specific values when the error is used.
    """
    
    # Player-related errors
    PLAYER_NAME_EMPTY = "Player name cannot be empty"
    PLAYER_NOT_FOUND = "Player '{name}' not found"
    PLAYER_ID_EMPTY = "Player ID cannot be empty"
    INVALID_PLAYER_ID_FORMAT = "Invalid player ID format: {player_id}"
    PLAYER_LIST_EMPTY = "No players found in NBA API"
    PLAYER_INFO_API = "Error fetching player info for {name}: {error}"
    PLAYER_INFO_PROCESSING = "Error processing player info for {name}"
    PLAYER_INFO_UNEXPECTED = "Unexpected error fetching player info for {name}: {error}"
    PLAYER_GAMELOG_API = "Error fetching game log for {name} ({season}): {error}"
    PLAYER_GAMELOG_PROCESSING = "Error processing game log for {name} ({season})"
    PLAYER_GAMELOG_UNEXPECTED = "Unexpected error fetching game log for {name} ({season}): {error}"
    PLAYER_CAREER_STATS_API = "Error fetching career stats for {name}: {error}"
    PLAYER_CAREER_STATS_PROCESSING = "Error processing career stats for {name}"
    PLAYER_CAREER_STATS_UNEXPECTED = "Unexpected error fetching career stats for {name}: {error}"
    MISSING_PLAYER_OR_SEASON = "Player name and season are required"
    
    # Team-related errors
    TEAM_NOT_FOUND = "Team '{identifier}' not found."
    TEAM_IDENTIFIER_EMPTY = "Team identifier cannot be empty."
    TEAM_API = "API error fetching {data_type} for team ID {identifier}: {error}"
    TEAM_PROCESSING = "DataFrame processing failed for {data_type}, Team ID {identifier}"
    TEAM_ALL_FAILED = "Failed to fetch any data for team '{identifier}' ({season}). Errors: {errors}"
    TEAM_UNEXPECTED = "Unexpected error processing team info/roster request for {identifier} ({season}): {error}"
    
    # Game-related errors
    FIND_GAMES_API = "API error fetching games: {error}"
    FIND_GAMES_PROCESSING = "Failed to process game data from API."
    FIND_GAMES_UNEXPECTED = "Unexpected error processing find games request: {error}"
    GAME_ID_EMPTY = "Game ID cannot be empty."
    INVALID_GAME_ID_FORMAT = "Invalid Game ID format: {game_id}. Expected 10 digits."
    BOXSCORE_API = "API error fetching box score for game ID {game_id}: {error}"
    BOXSCORE_PROCESSING = "Failed to process box score data from API for game ID {game_id}."
    BOXSCORE_UNEXPECTED = "Unexpected error processing box score request for game ID {game_id}: {error}"
    PLAYBYPLAY_API = "API error fetching play-by-play for game ID {game_id}: {error}"
    PLAYBYPLAY_PROCESSING = "Failed to process play-by-play data from API for game ID {game_id}."
    PLAYBYPLAY_UNEXPECTED = "Unexpected error processing play-by-play request for game ID {game_id}: {error}"
    BOXSCORE_ADVANCED_API = "API error fetching advanced box score for game ID {game_id}: {error}"
    BOXSCORE_ADVANCED_PROCESSING = "Failed to process advanced box score data from API for game ID {game_id}."
    BOXSCORE_ADVANCED_UNEXPECTED = "Unexpected error processing advanced box score request for game ID {game_id}: {error}"
    BOXSCORE_FOURFACTORS_API = "API error fetching Four Factors box score for game ID {game_id}: {error}"
    BOXSCORE_FOURFACTORS_PROCESSING = "Failed to process Four Factors box score data from API for game ID {game_id}."
    BOXSCORE_FOURFACTORS_UNEXPECTED = "Unexpected error processing Four Factors box score request for game ID {game_id}: {error}"
    
    # League-related errors
    STANDINGS_API = "API error fetching standings for season {season}: {error}"
    STANDINGS_PROCESSING = "Failed to process standings data from API for season {season}."
    STANDINGS_UNEXPECTED = "Unexpected error processing standings request for season {season}: {error}"
    INVALID_DATE_FORMAT = "Invalid date format: {date}. Expected YYYY-MM-DD."
    SCOREBOARD_API = "API error fetching scoreboard for date {date}: {error}"
    SCOREBOARD_PROCESSING = "Failed to process scoreboard data from API for date {date}."
    SCOREBOARD_UNEXPECTED = "Unexpected error processing scoreboard request for date {date}: {error}"
    INVALID_DRAFT_YEAR_FORMAT = "Invalid draft year format: {year}. Expected YYYY."
    DRAFT_HISTORY_API = "API error fetching draft history for year {year}: {error}"
    DRAFT_HISTORY_PROCESSING = "Failed to process draft history data from API for year {year}."
    DRAFT_HISTORY_UNEXPECTED = "Unexpected error processing draft history request for year {year}: {error}"
    INVALID_STAT_CATEGORY = "Invalid stat category provided: {stat}."
    LEAGUE_LEADERS_API = "API error fetching league leaders for {stat}, season {season}: {error}"
    LEAGUE_LEADERS_PROCESSING = "Failed to process league leaders data from API for {stat}, season {season}."
    LEAGUE_LEADERS_UNEXPECTED = "Unexpected error processing league leaders request for {stat}, season {season}: {error}"
    
    # General validation errors
    INVALID_SEASON_FORMAT = "Invalid season format: {season}. Expected YYYY-YY."
    INVALID_PLAYER_OR_TEAM = "Invalid player_or_team value. Must be 'P' for Player or 'T' for Team."
    MISSING_PLAYER_ID = "player_id is required when player_or_team='P'."
    MISSING_TEAM_ID = "team_id is required when player_or_team='T'."
    EMPTY_SEARCH_QUERY = "Search query cannot be empty."
    INVALID_SEARCH_TARGET = "Invalid search target. Must be one of: {targets}"
    INVALID_SEARCH_LENGTH = "Search query must be at least {min_length} characters long."
    INVALID_SEARCH_LIMIT = "Search limit must be between 1 and {max_limit}."
    
    # Clutch stats-related errors
    CLUTCH_STATS_API = "API error fetching clutch stats for player ID {player_id}: {error}"
    CLUTCH_STATS_PROCESSING = "Failed to process clutch stats data for player ID {player_id}"
    CLUTCH_STATS_UNEXPECTED = "Unexpected error processing clutch stats request for player ID {player_id}: {error}"
    INVALID_MEASURE_TYPE = "Invalid measure type. Must be one of: Base, Advanced, Misc, Four Factors, Scoring, Opponent, Usage"
    INVALID_PER_MODE = "Invalid per mode. Must be one of: Totals, PerGame, MinutesPer, Per48, Per40, Per36, PerMinute, PerPossession, PerPlay, Per100Possessions, Per100Plays"
    INVALID_PLUS_MINUS = "Invalid plus/minus parameter. Must be 'Y' or 'N'"
    INVALID_PACE_ADJUST = "Invalid pace adjust parameter. Must be 'Y' or 'N'"
    INVALID_RANK = "Invalid rank parameter. Must be 'Y' or 'N'"
    INVALID_SHOT_CLOCK_RANGE = "Invalid shot clock range. Must be one of: 24-22, 22-18 Very Early, 18-15 Early, 15-7 Average, 7-4 Late, 4-0 Very Late, ShotClock Off"
    INVALID_GAME_SEGMENT = "Invalid game segment. Must be one of: First Half, Overtime, Second Half"
