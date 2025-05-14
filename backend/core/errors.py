# --- Error Message Constants ---
class Errors:
    # Generic Errors
    INVALID_SEASON_FORMAT = "Invalid season format: '{season}'. Expected YYYY-YY (e.g., 2023-24)."
    REQUEST_TIMEOUT = "Request timed out after {timeout} seconds."
    API_ERROR = "NBA API request failed: {error}" # General NBA API error
    PROCESSING_ERROR = "Failed to process data: {error}"
    UNEXPECTED_ERROR = "An unexpected error occurred: {error}"
    DATA_NOT_FOUND = "No data found for the specified criteria."
    INVALID_DATE_FORMAT = "Invalid date format: '{date}'. Expected YYYY-MM-DD."
    MISSING_REQUIRED_PARAMS = "Missing required parameters for the request: {missing_params}"
    TEAM_ID_NOT_FOUND = "Could not determine Team ID for identifier '{identifier}'."
    EMPTY_SEARCH_QUERY = "Search query cannot be empty."
    SEARCH_QUERY_TOO_SHORT = "Search query must be at least {min_length} characters long."
    JSON_PROCESSING_ERROR = "Internal server error: Invalid data format from an underlying service."
    SSE_GENERATION_ERROR = "Error during SSE stream generation: {error_details}"
    TOPIC_EMPTY = "Research topic cannot be empty."
    PROMPT_SUGGESTION_ERROR = "Failed to generate prompt suggestions due to an internal error."
    UNSUPPORTED_FETCH_TARGET = "Unsupported fetch target: '{target}'. Supported targets are: {supported_targets}."
    UNSUPPORTED_SEARCH_TARGET = "Unsupported search target: '{target}'. Supported targets are: {supported_targets}."

    # Player Errors
    PLAYER_NAME_EMPTY = "Player name cannot be empty."
    PLAYER_ID_EMPTY = "Player ID cannot be empty."
    INVALID_PLAYER_ID_FORMAT = "Invalid player ID format: '{player_id}'. Expected digits only."
    PLAYER_NOT_FOUND = "Player '{identifier}' not found."
    PLAYER_INFO_API = "API error fetching player info for {identifier}: {error}"
    PLAYER_INFO_PROCESSING = "Failed to process player info for {identifier}."
    PLAYER_INFO_UNEXPECTED = "Unexpected error fetching player info for {identifier}: {error}"
    PLAYER_GAMELOG_API = "API error fetching gamelog for {identifier} (Season: {season}): {error}"
    PLAYER_GAMELOG_PROCESSING = "Failed to process gamelog for {identifier} (Season: {season})."
    PLAYER_GAMELOG_UNEXPECTED = "Unexpected error fetching gamelog for {identifier} (Season: {season}): {error}"
    PLAYER_CAREER_STATS_API = "API error fetching career stats for {identifier}: {error}"
    PLAYER_CAREER_STATS_PROCESSING = "Failed to process career stats for {identifier}."
    PLAYER_CAREER_STATS_UNEXPECTED = "Unexpected error fetching career stats for {identifier}: {error}"
    PLAYER_AWARDS_API = "API error fetching awards for {identifier}: {error}"
    PLAYER_AWARDS_PROCESSING = "Failed to process awards for {identifier}."
    PLAYER_AWARDS_UNEXPECTED = "Unexpected error fetching awards for {identifier}: {error}"
    PLAYER_SHOTCHART_API = "API error fetching shot chart for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTCHART_PROCESSING = "Failed to process shot chart data for {identifier} (Season: {season})."
    PLAYER_SHOTCHART_UNEXPECTED = "Unexpected error fetching shot chart for {identifier} (Season: {season}): {error}"
    PLAYER_DEFENSE_API = "API error fetching defense stats for {identifier} (Season: {season}): {error}"
    PLAYER_DEFENSE_PROCESSING = "Failed to process defense stats for {identifier} (Season: {season})."
    PLAYER_DEFENSE_UNEXPECTED = "Unexpected error fetching defense stats for {identifier} (Season: {season}): {error}"
    PLAYER_CLUTCH_API = "API error fetching clutch stats for {identifier} (Season: {season}): {error}"
    PLAYER_CLUTCH_PROCESSING = "Failed to process clutch stats for {identifier} (Season: {season})."
    PLAYER_CLUTCH_UNEXPECTED = "Unexpected error fetching clutch stats for {identifier} (Season: {season}): {error}" # Already exists, ensure it's correct
    PLAYER_PASSING_API = "API error fetching passing stats for {identifier} (Season: {season}): {error}"
    PLAYER_PASSING_PROCESSING = "Failed to process passing stats for {identifier} (Season: {season})."
    PLAYER_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for {identifier} (Season: {season}): {error}"
    PLAYER_REBOUNDING_API = "API error fetching rebounding stats for {identifier} (Season: {season}): {error}"
    PLAYER_REBOUNDING_PROCESSING = "Failed to process rebounding stats for {identifier} (Season: {season})."
    PLAYER_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTS_TRACKING_API = "API error fetching shot tracking stats for {identifier} (Season: {season}): {error}"
    PLAYER_SHOTS_TRACKING_PROCESSING = "Failed to process shot tracking stats for {identifier} (Season: {season})."
    PLAYER_SHOTS_TRACKING_UNEXPECTED = "Unexpected error fetching shot tracking stats for {identifier} (Season: {season}): {error}"
    PLAYER_ID_REQUIRED = "player_id is required when searching by player."

    PLAYER_PROFILE_API = "API error fetching player profile for {identifier}: {error}"
    PLAYER_PROFILE_PROCESSING = "Failed to process essential profile data for {identifier}"
    PLAYER_PROFILE_UNEXPECTED = "Unexpected error fetching player profile for {identifier}: {error}"
    PLAYER_HUSTLE_API = "API error fetching hustle stats: {error}"
    PLAYER_HUSTLE_PROCESSING = "Data processing error for hustle stats."
    PLAYER_HUSTLE_UNEXPECTED = "Unexpected error fetching hustle stats: {error}"

    PLAYER_ANALYSIS_API = "API error analyzing stats for player {identifier}: {error}"
    PLAYER_ANALYSIS_PROCESSING = "Failed to process analysis stats for player {identifier}."
    PLAYER_ANALYSIS_UNEXPECTED = "Unexpected error analyzing stats for player {identifier}: {error}"
    PLAYER_SEARCH_UNEXPECTED = "Unexpected error searching for players: {error}"

    # Team Errors
    TEAM_IDENTIFIER_EMPTY = "Team identifier (name, abbreviation, or ID) cannot be empty."
    TEAM_NOT_FOUND = "Team '{identifier}' not found."
    TEAM_API = "API error fetching {data_type} for team {identifier} (Season: {season}): {error}"
    TEAM_PROCESSING = "Failed to process {data_type} for team {identifier} (Season: {season})."
    TEAM_UNEXPECTED = "Unexpected error fetching team data for {identifier} (Season: {season}): {error}"
    TEAM_ALL_FAILED = "Failed to fetch any data (info, ranks, roster, coaches) for team {identifier} (Season: {season}). Errors: {errors_list}"
    TEAM_ID_REQUIRED = "team_id is required when searching by team."
    TEAM_PASSING_API = "API error fetching passing stats for team {identifier} (Season: {season}): {error}"
    TEAM_PASSING_PROCESSING = "Failed to process passing stats for team {identifier} (Season: {season})."
    TEAM_PASSING_UNEXPECTED = "Unexpected error fetching passing stats for team {identifier} (Season: {season}): {error}"
    TEAM_SHOOTING_API = "API error fetching shooting stats for team {identifier} (Season: {season}): {error}"
    TEAM_SHOOTING_PROCESSING = "Failed to process shooting stats for team {identifier} (Season: {season})."
    TEAM_SHOOTING_UNEXPECTED = "Unexpected error fetching shooting stats for team {identifier} (Season: {season}): {error}"
    TEAM_REBOUNDING_API = "API error fetching rebounding stats for team {identifier} (Season: {season}): {error}"
    TEAM_REBOUNDING_PROCESSING = "Failed to process rebounding stats for team {identifier} (Season: {season})."
    TEAM_REBOUNDING_UNEXPECTED = "Unexpected error fetching rebounding stats for team {identifier} (Season: {season}): {error}"
    TEAM_SEARCH_UNEXPECTED = "Unexpected error searching for teams: {error}"
    TEAM_IDENTIFIER_OR_ID_REQUIRED = "Either team_identifier or team_id must be provided."
    INVALID_TEAM_IDENTIFIER = "Invalid team identifier: '{identifier}'. Must be a valid team name, abbreviation, or ID." # Added
    INVALID_TEAM_ID_VALUE = "Invalid Team ID: '{team_id}'. Team ID must be a valid positive integer."

    # Game Errors
    GAME_ID_EMPTY = "Game ID cannot be empty."
    INVALID_GAME_ID_FORMAT = "Invalid game ID format: '{game_id}'. Expected 10 digits."
    GAME_NOT_FOUND = "Game with ID '{game_id}' not found."
    BOXSCORE_API = "API error fetching boxscore for game {game_id}: {error}"
    BOXSCORE_TRADITIONAL_API = "API error fetching traditional boxscore for game {game_id}: {error}"
    BOXSCORE_ADVANCED_API = "API error fetching advanced boxscore for game {game_id}: {error}"
    BOXSCORE_FOURFACTORS_API = "Error fetching BoxScoreFourFactorsV3 for game {game_id}: {error}"
    BOXSCORE_USAGE_API = "Error fetching BoxScoreUsageV3 for game {game_id}: {error}"
    BOXSCORE_DEFENSIVE_API = "Error fetching BoxScoreDefensiveV2 for game {game_id}: {error}"
    BOXSCORE_SUMMARY_API = "Error fetching BoxScoreSummaryV2 for game {game_id}: {error}"
    WINPROBABILITY_API = "API error fetching win probability for game {game_id}: {error}"
    PLAYBYPLAY_API = "API error fetching play-by-play for game {game_id}: {error}"
    SHOTCHART_API = "API error fetching shot chart for game {game_id}: {error}"
    GAME_UNEXPECTED = "Unexpected error fetching data for game {game_id}: {error}"
    SHOTCHART_PROCESSING = "Failed to process shot chart data for game {game_id}."
    INVALID_SEASON_FOR_GAME_SEARCH = "Invalid season provided for game search: {season}."
    DATE_ONLY_GAME_FINDER_UNSUPPORTED = "Searching games by date range only is not supported for leaguegamefinder. Please also provide a season, team ID, or player ID for a more stable query."
    GAME_SEARCH_UNEXPECTED = "Unexpected error searching for games: {error}"

    # Synergy Errors
    SYNERGY_API = "API error fetching synergy play types: {error}"
    SYNERGY_PROCESSING = "Failed to process synergy play types data."
    SYNERGY_UNEXPECTED = "Unexpected error fetching synergy play types: {error}"
    INVALID_PLAY_TYPE = "Invalid play type: '{play_type}'. Valid options: {options}"
    INVALID_TYPE_GROUPING = "Invalid type grouping: '{type_grouping}'. Valid options: {options}"

    # League Errors
    LEAGUE_STANDINGS_API = "API error fetching league standings for Season {season} (Type: {season_type}): {error}" # Added season_type, removed date
    LEAGUE_STANDINGS_PROCESSING = "Failed to process league standings for Season {season} (Type: {season_type})." # Added season_type, removed date
    LEAGUE_STANDINGS_UNEXPECTED = "Unexpected error fetching league standings for Season {season} (Type: {season_type}): {error}" # Added season_type, removed date
    LEAGUE_SCOREBOARD_API = "API error fetching scoreboard for date {game_date}: {error}"
    LEAGUE_SCOREBOARD_UNEXPECTED = "Unexpected error fetching scoreboard for date {game_date}: {error}"
    DRAFT_HISTORY_API = "API error fetching draft history for year {year}: {error}"
    DRAFT_HISTORY_UNEXPECTED = "Unexpected error fetching draft history for year {year}: {error}"
    LEAGUE_LEADERS_API = "API error fetching league leaders for {stat_category} (Season: {season}): {error}"
    LEAGUE_LEADERS_PROCESSING = "Failed to process league leaders data for {stat_category} (Season: {season})." # Added
    LEAGUE_LEADERS_UNEXPECTED = "Unexpected error fetching league leaders for {stat_category} (Season: {season}): {error}"
    INVALID_DRAFT_YEAR_FORMAT = "Invalid draft year format: '{year}'. Expected YYYY."
    DRAFT_HISTORY_PROCESSING = "Failed to process draft history for year {year}."
    LEAGUE_GAMES_API = "API error fetching league games: {error}"
    LEAGUE_GAMES_UNEXPECTED = "Unexpected error fetching league games: {error}"

    # Trending Stats Errors
    INVALID_TOP_N = "Invalid top_n parameter: must be a positive integer > 0, got {value}"
    TRENDING_UNEXPECTED = "Unexpected error fetching trending player data: {error}"
    TRENDING_TEAMS_UNEXPECTED = "Unexpected error fetching trending teams data: {error}"

    # Matchup Errors
    MISSING_PLAYER_IDENTIFIER = "Player identifier (name or ID) cannot be empty."
    MATCHUPS_API = "Error fetching matchup data: {error}"
    MATCHUPS_ROLLUP_API = "Error fetching matchup rollup data: {error}"
    MATCHUPS_PROCESSING = "Failed to process matchup data."
    MATCHUPS_UNEXPECTED = "Unexpected error fetching matchup data: {error}"
    MATCHUPS_ROLLUP_PROCESSING = "Failed to process matchup rollup data."
    MATCHUPS_ROLLUP_UNEXPECTED = "Unexpected error fetching matchup rollup data: {error}"

    # Odds Errors
    ODDS_API_UNEXPECTED = "Unexpected error fetching odds data: {error}"

    # Parameter Validation Errors
    INVALID_SEASON_TYPE = "Invalid season_type: '{value}'. Valid options: {options}"
    INVALID_STAT_CATEGORY = "Invalid stat_category: '{value}'. Valid options: {options}"
    INVALID_PER_MODE = "Invalid per_mode: '{value}'. Valid options: {options}"
    INVALID_LEAGUE_ID = "Invalid league_id: '{value}'. Valid options: {options}"
    INVALID_MEASURE_TYPE = "Invalid measure_type: '{value}'. Valid options: {options}"
    INVALID_SCOPE = "Invalid scope: '{value}'. Valid options: {options}"
    INVALID_PLAYER_OR_TEAM_ABBREVIATION = "Invalid player_or_team_abbreviation: '{value}'. Must be 'P' or 'T'."
    INVALID_DEFENSE_CATEGORY = "Invalid defense_category: '{value}'. Valid options: {options}"
    INVALID_SHOT_CLOCK_RANGE = "Invalid shot_clock_range: '{value}'. Valid options: {options}"
    INVALID_PLUS_MINUS = "Invalid plus_minus: '{value}'. Must be 'Y' or 'N'."
    INVALID_PACE_ADJUST = "Invalid pace_adjust: '{value}'. Must be 'Y' or 'N'."
    INVALID_RANK = "Invalid rank: '{value}'. Must be 'Y' or 'N'."
    INVALID_GAME_SEGMENT = "Invalid game_segment: '{value}'. Valid options: {options}"
    INVALID_LOCATION = "Invalid location: '{value}'. Valid options: {options}"
    INVALID_OUTCOME = "Invalid outcome: '{value}'. Valid options: {options}"
    INVALID_CONFERENCE = "Invalid vs_conference: '{value}'. Valid options: {options}"
    INVALID_DIVISION = "Invalid vs_division: '{value}'. Valid options: {options}"
    INVALID_SEASON_SEGMENT = "Invalid season_segment: '{value}'. Valid options: {options}"
    INVALID_RUN_TYPE = "Invalid RunType: '{value}'. Valid options: {options}"
    INVALID_PARAMETER_FORMAT = "Invalid format for parameter '{param_name}': '{param_value}'. Expected format: {expected_format}"
    INVALID_CONTEXT_MEASURE = "Invalid context_measure: '{value}'. Valid options: {options}" # Added

    # League Player On Details Errors
    LEAGUE_PLAYER_ON_DETAILS_PROCESSING = "Processing failed for league player on details (TeamID: {team_id}, Season: {season})."
    LEAGUE_PLAYER_ON_DETAILS_UNEXPECTED = "Unexpected error fetching league player on details for TeamID {team_id}, Season {season}: {error}"

    # Specific NBA API interaction errors
    NBA_API_TIMEOUT = "NBA API request to endpoint '{endpoint_name}' timed out. Details: {details}"
    NBA_API_CONNECTION_ERROR = "NBA API request to endpoint '{endpoint_name}' failed due to a connection error. Details: {details}"
    NBA_API_GENERAL_ERROR = "NBA API request to endpoint '{endpoint_name}' failed with an unexpected error. Details: {details}"

    # Scoreboard specific
    UNEXPECTED_ERROR_SCOREBOARD = "Unexpected error fetching/formatting scoreboard data for date {date}: {error_details}"

    # Advanced Player Stats (PlayerEstimatedMetrics, TeamEstimatedMetrics, TeamPlayerOnOffDetails)
    PLAYER_ESTIMATED_METRICS_API = "API error fetching player estimated metrics (Season: {season}, Type: {season_type}): {error}"

    PLAYER_SHOT_CHART_API = "Error fetching shot chart data for player {player_id} in season {season}: {error}"
    PLAYER_SHOT_CHART_NO_DATA = "No shot chart data found for player {player_id} in season {season}."
    TEAM_SHOT_CHART_API = "Error fetching shot chart data for game {game_id}: {error}"
    TEAM_SHOT_CHART_NO_DATA = "No shot chart data found for game {game_id}."
    COMMON_ALL_PLAYERS_API_ERROR = "Error fetching data from CommonAllPlayers endpoint: {error}"
    COMMON_PLAYOFF_SERIES_API_ERROR = "Error fetching data from CommonPlayoffSeries endpoint: {error}"
    COMMON_TEAM_YEARS_API_ERROR = "Error fetching data from CommonTeamYears endpoint: {error}"
    LEAGUE_DASH_LINEUPS_API_ERROR = "Error fetching data from LeagueDashLineups endpoint: {error}"
    LEAGUE_DASH_OPP_PT_SHOT_API_ERROR = "Error fetching data from LeagueDashOppPtShot endpoint: {error}"