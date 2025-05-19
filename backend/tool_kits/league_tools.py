"""
This module provides a toolkit of league-wide functions exposed as agent tools.
These tools wrap specific logic functions from `backend.api_tools` to fetch
various NBA league-level statistics and information.
"""
import logging
import json
from typing import Optional
# import datetime # Unused import
from agno.tools import tool
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID, PerMode48, Scope, PerModeSimple,
    PlayerOrTeamAbbreviation, PerModeDetailed, MeasureTypeDetailedDefense # Added MeasureTypeDetailedDefense
)
from backend.config import settings

# Import specific logic functions for league tools
from backend.api_tools.league_standings import fetch_league_standings_logic
from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic
from backend.api_tools.league_draft import fetch_draft_history_logic
from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from backend.api_tools.league_player_on_details import fetch_league_player_on_details_logic
from backend.api_tools.player_listings import fetch_common_all_players_logic
from backend.api_tools.playoff_series import fetch_common_playoff_series_logic
from backend.api_tools.team_history import fetch_common_team_years_logic
from backend.api_tools.league_lineups import fetch_league_dash_lineups_logic
from backend.api_tools.trending_tools import fetch_top_performers_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic

logger = logging.getLogger(__name__)

@tool
def get_league_standings(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba, # Added league_id to match underlying logic
    as_dataframe: bool = False
) -> str:
    """
    Fetches league standings for a specified season, season type, and league.
    Provides DataFrame output capabilities.

    Args:
        season (str, optional): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
            Defaults to the current season from settings.
        season_type (str, optional): The type of season (e.g., "Regular Season", "Playoffs").
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`. Defaults to "Regular Season".
        league_id (str, optional): The league ID (e.g., "00" for NBA).
            Valid values from `nba_api.stats.library.parameters.LeagueID`. Defaults to "00".
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string containing league standings data, typically a list of team objects
             with fields like TeamID, TeamName, Conference, WINS, LOSSES, WinPct, etc.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_league_standings' called for season '{season}', type '{season_type}', league '{league_id}', as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_league_standings_logic(
            season=season,
            season_type=season_type,
            league_id=league_id,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "League standings have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                # Clean season type for filename
                clean_season_type = season_type.replace(" ", "_").lower()

                csv_path = f"backend/cache/league_standings/standings_{season}_{clean_season_type}_{league_id}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
                    "sample_data": df.head(5).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        result = fetch_league_standings_logic(season=season, season_type=season_type, league_id=league_id)
        return result

@tool
def get_scoreboard(
    game_date: Optional[str] = None, # YYYY-MM-DD format
    league_id: str = LeagueID.nba, # Added league_id
    day_offset: int = 0, # Added day_offset
    bypass_cache: bool = False # Added bypass_cache
) -> str:
    """
    Fetches the scoreboard for a specific date, league, and day offset.
    If game_date is not provided, it defaults to the current date.

    Args:
        game_date (Optional[str], optional): The date for the scoreboard in YYYY-MM-DD format.
            Defaults to the current date if None.
        league_id (str, optional): The league ID (e.g., "00" for NBA). Defaults to "00".
        day_offset (int, optional): Offset from the game_date (e.g., -1 for previous day). Defaults to 0.
        bypass_cache (bool, optional): If True, bypasses any caching for live data. Defaults to False.


    Returns:
        str: JSON string with scoreboard data, including game headers, line scores, and series standings.
    """
    # The logic function fetch_scoreboard_data_logic handles defaulting game_date if None.
    logger.debug(f"Tool 'get_scoreboard' called for date '{game_date}', league '{league_id}', offset '{day_offset}'")
    result = fetch_scoreboard_data_logic(
        game_date=game_date,
        league_id=league_id,
        day_offset=day_offset,
        bypass_cache=bypass_cache
    )
    return result

@tool(cache_results=True, cache_ttl=86400) # Cache for 1 day
def get_draft_history(
    season_year_nullable: Optional[str] = None, # YYYY format
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None
) -> str:
    """
    Fetches NBA draft history, optionally filtered by season year, league, team, round, or overall pick.

    Args:
        season_year_nullable (Optional[str], optional): The draft season year in YYYY format (e.g., "2023").
        league_id_nullable (str, optional): League ID. Defaults to "00" (NBA).
        team_id_nullable (Optional[int], optional): Team ID to filter by.
        round_num_nullable (Optional[int], optional): Draft round number.
        overall_pick_nullable (Optional[int], optional): Overall pick number.

    Returns:
        str: JSON string containing a list of draft picks with details like PlayerName, TeamID, PickOverall, etc.
    """
    logger.debug(
        f"Tool 'get_draft_history' called for Year: {season_year_nullable}, League: {league_id_nullable}, "
        f"Round: {round_num_nullable}, Team: {team_id_nullable}, Pick: {overall_pick_nullable}"
    )
    result = fetch_draft_history_logic(
        season_year_nullable=season_year_nullable,
        league_id_nullable=league_id_nullable,
        round_num_nullable=round_num_nullable,
        team_id_nullable=team_id_nullable,
        overall_pick_nullable=overall_pick_nullable
    )
    return result

@tool
def get_league_leaders(
    stat_category: str, # e.g., StatCategoryAbbreviation.pts
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s, # 'S' for Season, 'RS' for Rookies
    top_n: int = 10
) -> str:
    """
    Fetches league leaders for a specific statistical category.

    Args:
        stat_category (str): The statistical category abbreviation (e.g., "PTS", "REB", "AST").
            Valid values from `nba_api.stats.library.parameters.StatCategoryAbbreviation`.
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        per_mode (str, optional): Statistical mode (e.g., "PerGame", "Totals").
            Valid values from `nba_api.stats.library.parameters.PerMode48`. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        scope (str, optional): Scope of leaders (e.g., "S" for all players, "RS" for rookies).
            Valid values from `nba_api.stats.library.parameters.Scope`. Defaults to "S".
        top_n (int, optional): Number of top leaders to return. Defaults to 10.

    Returns:
        str: JSON string containing a list of league leaders with their stats.
    """
    logger.debug(
        f"Tool 'get_league_leaders' called for Cat: {stat_category}, Season: {season}, Type: {season_type}, "
        f"Mode: {per_mode}, League: {league_id}, Scope: {scope}, TopN: {top_n}"
    )
    result = fetch_league_leaders_logic(
        season=season,
        stat_category=stat_category,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        scope=scope,
        top_n=top_n
    )
    return result

@tool
def get_synergy_play_types(
    play_type: str, # This is REQUIRED by the underlying logic, moved to front
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    player_or_team_abbreviation: str = PlayerOrTeamAbbreviation.team, # 'T' or 'P'
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    type_grouping: str = "Offensive", # "Offensive" or "Defensive"
    player_id_nullable: Optional[int] = None,
    team_id_nullable: Optional[int] = None
) -> str:
    """
    Fetches Synergy Sports play type statistics for players or teams.
    A specific 'play_type' (e.g., "Isolation", "Transition") is REQUIRED.
    The 'type_grouping' (context: "Offensive" or "Defensive") defaults to "Offensive".
    Results include 'POSS_PCT' (frequency of possessions) and 'PPP' (Points Per Possession).

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Season phase. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        player_or_team_abbreviation (str, optional): "P" for players or "T" for teams. Defaults to "T".
            Valid values from `nba_api.stats.library.parameters.PlayerOrTeamAbbreviation`.
        play_type (str): Specific play type (e.g., "Isolation", "PostUp", "Transition"). This is REQUIRED.
            Valid values from `nba_api.stats.library.parameters.PlayType`.
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
            Valid values from `nba_api.stats.library.parameters.PerModeSimple`.
        type_grouping (str, optional): Context filter ("Offensive" or "Defensive"). Defaults to "Offensive".
            Valid values from `nba_api.stats.library.parameters.TypeGrouping`.
        player_id_nullable (Optional[int], optional): Player ID (if player_or_team_abbreviation="P").
        team_id_nullable (Optional[int], optional): Team ID (if player_or_team_abbreviation="T").

    Returns:
        str: JSON string with Synergy play type statistics.
    """
    # Ensure type_grouping is one of the valid options, default if not.
    effective_type_grouping = type_grouping if type_grouping in ["Offensive", "Defensive"] else "Offensive"

    logger.debug(
        f"Tool 'get_synergy_play_types' called for League: {league_id}, Mode: {per_mode}, "
        f"P/T: {player_or_team_abbreviation}, Season: {season}, PlayType: {play_type}, "
        f"TypeGrouping: {effective_type_grouping}, PlayerID: {player_id_nullable}, TeamID: {team_id_nullable}"
    )

    # Validate player_id and team_id match the player_or_team_abbreviation mode
    if player_id_nullable is not None and player_or_team_abbreviation != PlayerOrTeamAbbreviation.player:
        logger.warning("player_id provided but player_or_team_abbreviation is not 'P'. player_id will be ignored by API.")
        # player_id_nullable = None # Logic function handles this
    if team_id_nullable is not None and player_or_team_abbreviation != PlayerOrTeamAbbreviation.team:
        logger.warning("team_id provided but player_or_team_abbreviation is not 'T'. team_id will be ignored by API.")
        # team_id_nullable = None

    return fetch_synergy_play_types_logic(
        league_id=league_id,
        per_mode=per_mode,
        player_or_team=player_or_team_abbreviation, # Parameter name for logic function
        season_type=season_type,
        season=season,
        play_type_nullable=play_type, # Parameter name for logic function
        type_grouping_nullable=effective_type_grouping, # Parameter name for logic function
        player_id_nullable=player_id_nullable,
        team_id_nullable=team_id_nullable
    )

@tool
def get_league_player_on_details(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailedDefense.base, # Corrected default
    per_mode: str = PerModeDetailed.totals,
    team_id: int = 0, # 0 for all teams
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = LeagueID.nba,
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None
) -> str:
    """
    Fetches league-wide player on/off court details with extensive filtering options.

    Args:
        season (str, optional): Season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        measure_type (str, optional): Statistical measure type (e.g., "Base", "Advanced"). Defaults to "Base".
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`.
        per_mode (str, optional): Statistical mode (e.g., "Totals", "PerGame"). Defaults to "Totals".
        team_id (int, optional): Filter by a specific team ID. Defaults to 0 (all teams).
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        month (int, optional): Filter by month (1-12). Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        pace_adjust (str, optional): Pace adjust ("Y" or "N"). Defaults to "N".
        plus_minus (str, optional): Plus/Minus ("Y" or "N"). Defaults to "N".
        rank (str, optional): Rank ("Y" or "N"). Defaults to "N".
        period (int, optional): Filter by period. Defaults to 0.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        season_segment_nullable (Optional[str], optional): Filter by season segment (e.g., "Pre All-Star").
        outcome_nullable (Optional[str], optional): Filter by game outcome ("W" or "L").
        location_nullable (Optional[str], optional): Filter by game location ("Home" or "Road").
        league_id_nullable (Optional[str], optional): League ID. Defaults to "00" (NBA).
        game_segment_nullable (Optional[str], optional): Filter by game segment (e.g., "First Half").
        date_to_nullable (Optional[str], optional): End date filter (YYYY-MM-DD).
        date_from_nullable (Optional[str], optional): Start date filter (YYYY-MM-DD).

    Returns:
        str: JSON string with league player on/off court details.
    """
    logger.debug(f"Tool 'get_league_player_on_details' called for Season: {season}, TeamID: {team_id}, Measure: {measure_type}")
    return fetch_league_player_on_details_logic(
        season=season, season_type=season_type, measure_type=measure_type, per_mode=per_mode,
        team_id=team_id, last_n_games=last_n_games, month=month, opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust, plus_minus=plus_minus, rank=rank, period=period,
        vs_division_nullable=vs_division_nullable, vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable, outcome_nullable=outcome_nullable,
        location_nullable=location_nullable, league_id_nullable=league_id_nullable,
        game_segment_nullable=game_segment_nullable, date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable
    )

@tool(cache_results=True, cache_ttl=86400) # Cache for 1 day
def get_common_all_players(
    season: str, # YYYY-YY format
    league_id: str = LeagueID.nba,
    is_only_current_season: int = 1, # 1 for current, 0 for all historical in that season
    as_dataframe: bool = False
) -> str:
    """
    Fetches a list of all players for a given league and season using CommonAllPlayers endpoint.
    Provides DataFrame output capabilities.

    Args:
        season (str): The NBA season identifier in YYYY-YY format (e.g., "2023-24").
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        is_only_current_season (int, optional): Flag to fetch only currently active players (1)
            or all players historically associated with that season (0). Defaults to 1.
        as_dataframe (bool, optional): If True, returns a pandas DataFrame representation of the data
            and saves it to CSV files in the cache directory. Defaults to False.

    Returns:
        str: JSON string with a list of players, including fields like PERSON_ID, DISPLAY_LAST_COMMA_FIRST, TEAM_ID, etc.
             If as_dataframe=True, the JSON response will include additional information about
             the DataFrames and CSV files.
    """
    logger.debug(f"Tool 'get_common_all_players' called for Season: {season}, LeagueID: {league_id}, IsOnlyCurrentSeason: {is_only_current_season}, as_dataframe={as_dataframe}")

    if as_dataframe:
        # Get both JSON response and DataFrames
        json_response, dataframes = fetch_common_all_players_logic(
            season=season,
            league_id=league_id,
            is_only_current_season=is_only_current_season,
            return_dataframe=True
        )

        # Parse the original JSON response
        data = json.loads(json_response)

        # Add DataFrame info
        df_info = {
            "message": "Player listings have been converted to DataFrames and saved as CSV files",
            "dataframes": {}
        }

        for key, df in dataframes.items():
            if not df.empty:
                csv_path = f"backend/cache/player_listings/players_{season}_{league_id}_{is_only_current_season}.csv"

                df_info["dataframes"][key] = {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "csv_path": csv_path,
                    "sample_data": df.head(5).to_dict(orient="records") if not df.empty else []
                }

        # Add DataFrame info to the response
        if "error" in data:
            # If there was an error, keep it and add DataFrame info
            data["dataframe_info"] = df_info
        else:
            # If successful, add DataFrame info
            data["dataframe_info"] = df_info

        # Return the enhanced JSON response
        return json.dumps(data)
    else:
        # Return the standard JSON response
        return fetch_common_all_players_logic(
            season=season,
            league_id=league_id,
            is_only_current_season=is_only_current_season
        )

@tool(cache_results=True, cache_ttl=86400) # Cache for 1 day
def get_common_playoff_series(
    season: str, # YYYY format for this endpoint (e.g., "2023" for 2023-24 playoffs)
    league_id: str = LeagueID.nba,
    series_id: Optional[str] = None # e.g., "0042300201"
) -> str:
    """
    Fetches information about playoff series for a given league and season using CommonPlayoffSeries.

    Args:
        season (str): The NBA season year in YYYY format (e.g., "2023" for the playoffs concluding in 2024).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        series_id (Optional[str], optional): Specific series ID to filter for.

    Returns:
        str: JSON string with playoff series game details, including GAME_ID, HOME_TEAM_ID, VISITOR_TEAM_ID, SERIES_ID.
    """
    logger.debug(f"Tool 'get_common_playoff_series' called for Season: {season}, League: {league_id}, SeriesID: {series_id}")
    return fetch_common_playoff_series_logic(season=season, league_id=league_id, series_id=series_id)

@tool(cache_results=True, cache_ttl=86400) # Cache for 1 day
def get_common_team_years(league_id: str = LeagueID.nba) -> str:
    """
    Fetches a list of all team years for a given league, indicating the range of seasons each team existed.

    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).

    Returns:
        str: JSON string with team year details, including TEAM_ID, MIN_YEAR, MAX_YEAR, ABBREVIATION.
    """
    logger.debug(f"Tool 'get_common_team_years' called for League: {league_id}")
    return fetch_common_team_years_logic(league_id=league_id)

@tool
def get_league_dash_lineups(
    season: str, # YYYY-YY format
    group_quantity: int = 5, # 2, 3, 4, or 5 for lineup size
    last_n_games: int = 0,
    measure_type: str = MeasureTypeDetailedDefense.base, # Corrected default
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    per_mode: str = PerModeDetailed.totals, # Corrected default
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    season_type: str = SeasonTypeAllStar.regular, # Corrected default
    conference_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = LeagueID.nba,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None, # API doc says string, e.g. "1", "2"
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None
) -> str:
    """
    Fetches league-wide lineup statistics with extensive filtering options.

    Args:
        season (str): Season in YYYY-YY format.
        group_quantity (int, optional): Size of the lineup (2-5). Defaults to 5.
        last_n_games (int, optional): Filter by last N games. Defaults to 0.
        measure_type (str, optional): Statistical measure type. Defaults to "Base".
            Valid values from `nba_api.stats.library.parameters.MeasureTypeDetailedDefense`.
        month (int, optional): Filter by month (1-12). Defaults to 0.
        opponent_team_id (int, optional): Filter by opponent team ID. Defaults to 0.
        pace_adjust (str, optional): Pace adjust ("Y" or "N"). Defaults to "N".
        per_mode (str, optional): Statistical mode. Defaults to "Totals".
            Valid values from `nba_api.stats.library.parameters.PerModeDetailed`.
        period (int, optional): Filter by period. Defaults to 0.
        plus_minus (str, optional): Plus/Minus ("Y" or "N"). Defaults to "N".
        rank (str, optional): Rank ("Y" or "N"). Defaults to "N".
        season_type (str, optional): Type of season. Defaults to "Regular Season".
            Valid values from `nba_api.stats.library.parameters.SeasonTypeAllStar`.
        conference_nullable (Optional[str], optional): Filter by conference.
        date_from_nullable (Optional[str], optional): Start date filter (YYYY-MM-DD).
        date_to_nullable (Optional[str], optional): End date filter (YYYY-MM-DD).
        division_nullable (Optional[str], optional): Filter by division.
        game_segment_nullable (Optional[str], optional): Filter by game segment.
        league_id_nullable (Optional[str], optional): League ID. Defaults to "00" (NBA).
        location_nullable (Optional[str], optional): Filter by game location.
        outcome_nullable (Optional[str], optional): Filter by game outcome.
        po_round_nullable (Optional[str], optional): Filter by playoff round (e.g., "1", "2").
        season_segment_nullable (Optional[str], optional): Filter by season segment.
        shot_clock_range_nullable (Optional[str], optional): Filter by shot clock range.
        team_id_nullable (Optional[int], optional): Filter by team ID.
        vs_conference_nullable (Optional[str], optional): Filter by opponent's conference.
        vs_division_nullable (Optional[str], optional): Filter by opponent's division.

    Returns:
        str: JSON string with lineup statistics, typically including fields like GROUP_ID, GROUP_NAME, TEAM_ID, GP, MIN, FGM, FGA, FG_PCT, etc.
    """
    logger.debug(f"Tool 'get_league_dash_lineups' called for Season: {season}, GroupQty: {group_quantity}")
    return fetch_league_dash_lineups_logic(
        season=season, group_quantity=group_quantity, last_n_games=last_n_games, measure_type=measure_type,
        month=month, opponent_team_id=opponent_team_id, pace_adjust=pace_adjust, per_mode=per_mode,
        period=period, plus_minus=plus_minus, rank=rank, season_type=season_type,
        conference_nullable=conference_nullable, date_from_nullable=date_from_nullable, date_to_nullable=date_to_nullable,
        division_nullable=division_nullable, game_segment_nullable=game_segment_nullable, league_id_nullable=league_id_nullable,
        location_nullable=location_nullable, outcome_nullable=outcome_nullable, po_round_nullable=po_round_nullable,
        season_segment_nullable=season_segment_nullable, shot_clock_range_nullable=shot_clock_range_nullable,
        team_id_nullable=team_id_nullable, vs_conference_nullable=vs_conference_nullable, vs_division_nullable=vs_division_nullable
    )

@tool
def get_top_performers(
    category: str = "PTS", # Default to Points
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game, # Consistent with fetch_top_performers_logic
    scope: str = Scope.s, # Added scope to match underlying logic
    league_id: str = LeagueID.nba, # Added league_id to match underlying logic
    top_n: int = 5
) -> str:
    """
    Gets the top N players for a specific statistical category.

    Args:
        category (str, optional): Statistical category abbreviation (e.g., "PTS", "REB", "AST"). Defaults to "PTS".
            Valid values from `nba_api.stats.library.parameters.StatCategoryAbbreviation`.
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        per_mode (str, optional): Statistical mode. Defaults to "PerGame".
        scope (str, optional): Scope of leaders (e.g., "S" for all players, "RS" for rookies). Defaults to "S".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        top_n (int, optional): Number of top performers to return. Defaults to 5.

    Returns:
        str: JSON string with top performers, including fields like PLAYER_ID, RANK, PLAYER, TEAM, GP, MIN, and the stat category.
    """
    logger.debug(f"Tool 'get_top_performers' called for Cat: {category}, Season: {season}, Type: {season_type}, Mode: {per_mode}, Scope: {scope}, League: {league_id}, Top: {top_n}")
    result = fetch_top_performers_logic(
        category=category, season=season, season_type=season_type, per_mode=per_mode, scope=scope, league_id=league_id, top_n=top_n
    )
    return result

@tool
def get_top_teams(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba, # Added league_id to match underlying logic
    top_n: int = 5
) -> str:
    """
    Gets the top N teams based on league standings (win percentage).

    Args:
        season (str, optional): NBA season in YYYY-YY format. Defaults to current season.
        season_type (str, optional): Type of season. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        top_n (int, optional): Number of top teams to return. Defaults to 5.

    Returns:
        str: JSON string with top teams, including fields like TeamID, TeamName, Conference, WinPct, WINS, LOSSES.
    """
    logger.debug(f"Tool 'get_top_teams' called for Season: {season}, Type: {season_type}, League: {league_id}, Top: {top_n}")
    result = fetch_top_teams_logic(season=season, season_type=season_type, league_id=league_id, top_n=top_n)
    return result