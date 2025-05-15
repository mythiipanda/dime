import logging
from typing import Optional
import datetime
from agno.tools import tool
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, LeagueID, PerMode48, Scope, PerModeSimple, 
    PlayerOrTeamAbbreviation, PerModeDetailed
)
from backend.config import settings

# Import specific logic functions for league tools
from backend.api_tools.league_standings import fetch_league_standings_logic
from backend.api_tools.scoreboard_tools import fetch_scoreboard_data_logic
from backend.api_tools.league_draft import fetch_draft_history_logic
from backend.api_tools.league_leaders_data import fetch_league_leaders_logic
from backend.api_tools.synergy_tools import fetch_synergy_play_types_logic
from backend.api_tools.league_player_on_details import fetch_league_player_on_details_logic
from backend.api_tools.player_listings import fetch_common_all_players_logic # Renamed from common_player_info in some contexts
from backend.api_tools.playoff_series import fetch_common_playoff_series_logic
from backend.api_tools.team_history import fetch_common_team_years_logic
from backend.api_tools.league_lineups import fetch_league_dash_lineups_logic
from backend.api_tools.trending_tools import fetch_top_performers_logic
from backend.api_tools.trending_team_tools import fetch_top_teams_logic

logger = logging.getLogger(__name__)

@tool
def get_league_standings(season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular) -> str:
    """
    Fetches league standings.
    Args: season, season_type.
    Returns: JSON string with league standings.
    """
    logger.debug(f"Tool 'get_league_standings' called for season '{season}', type '{season_type}'")
    result = fetch_league_standings_logic(season=season, season_type=season_type)
    return result

@tool
def get_scoreboard(game_date: Optional[str] = None) -> str:
    """
    Fetches the scoreboard for a specific date.
    Args: game_date (YYYY-MM-DD).
    Returns: JSON string with scoreboard data.
    """
    final_game_date = game_date or datetime.date.today().strftime('%Y-%m-%d')
    logger.debug(f"Tool 'get_scoreboard' called for date '{final_game_date}'")
    result = fetch_scoreboard_data_logic(game_date=final_game_date)
    return result

@tool(cache_results=True, cache_ttl=86400)
def get_draft_history(
    season_year: Optional[str] = None,
    league_id: str = LeagueID.nba,
    round_num: Optional[int] = None,
    team_id: Optional[int] = None,
    overall_pick: Optional[int] = None
) -> str:
    """
    Fetches NBA draft history.
    Args: season_year, league_id, round_num, team_id, overall_pick.
    Returns: JSON string with draft picks.
    """
    logger.debug(
        f"Tool 'get_draft_history' called for Year: {season_year}, League: {league_id}, "
        f"Round: {round_num}, Team: {team_id}, Pick: {overall_pick}"
    )
    result = fetch_draft_history_logic(
        season_year_nullable=season_year,
        league_id_nullable=league_id,
        round_num_nullable=round_num,
        team_id_nullable=team_id,
        overall_pick_nullable=overall_pick
    )
    return result

@tool
def get_league_leaders(
    stat_category: str,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    league_id: str = LeagueID.nba,
    scope: str = Scope.s,
    top_n: int = 10
) -> str:
    """
    Fetches league leaders for a specific statistical category.
    Args: stat_category, season, season_type, per_mode, league_id, scope, top_n.
    Returns: JSON string with league leaders.
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
    league_id: str = LeagueID.nba,
    per_mode: str = PerModeSimple.per_game,
    player_or_team_abbreviation: str = PlayerOrTeamAbbreviation.team,
    season_type: str = SeasonTypeAllStar.regular,
    season: str = settings.CURRENT_NBA_SEASON,
    play_type: Optional[str] = None, # This is made required by the logic function
    type_grouping: Optional[str] = "offensive", # Default to "offensive" if not specified
    player_id: Optional[int] = None,
    team_id: Optional[int] = None
) -> str:
    """
    Fetches Synergy Sports play type statistics with optional player/team filtering.
    A specific 'play_type' (e.g., "Isolation", "Transition") is REQUIRED.
    The 'type_grouping' (context: "offensive" or "defensive") defaults to "offensive" if not provided.
    The results include 'POSS_PCT', which represents the frequency (percentage) of possessions for that play type,
    not a raw count of possessions. For example, a POSS_PCT of 0.1 means 10% of the player's/team's
    possessions in the given context were of this play type.

    Args:
        league_id: League ID (default: NBA "00").
        per_mode: Statistical mode ("PerGame", "Totals", etc.).
        player_or_team_abbreviation: "P" for players or "T" for teams.
        season_type: Season phase ("Regular Season", "Playoffs", etc.).
        season: Season in YYYY-YY format (e.g., "2023-24").
        play_type: Specific play type (e.g., "Isolation", "PostUp"). This is REQUIRED.
        type_grouping: Context filter ("offensive" or "defensive"). Defaults to "offensive".
        player_id: Optional player ID to filter results (used only if player_or_team_abbreviation="P").
        team_id: Optional team ID to filter results (used only if player_or_team_abbreviation="T").

    Returns:
        JSON string with Synergy play type statistics. Key fields include PLAY_TYPE, PPP (Points Per Possession),
        and POSS_PCT (Frequency/Percentage of Possessions).
    """
    effective_type_grouping = type_grouping if type_grouping in ["offensive", "defensive"] else "offensive"
    
    logger.debug(
        f"Tool 'get_synergy_play_types' called for League: {league_id}, Mode: {per_mode}, "
        f"P/T: {player_or_team_abbreviation}, Season: {season}, PlayType: {play_type}, "
        f"TypeGrouping: {effective_type_grouping}, PlayerID: {player_id}, TeamID: {team_id}"
    )

    # Validate player_id and team_id match the player_or_team_abbreviation mode
    if player_id is not None and player_or_team_abbreviation != PlayerOrTeamAbbreviation.player:
        logger.warning("player_id provided but player_or_team_abbreviation is not 'P'. player_id will be ignored.")
        player_id = None # Effectively ignored by logic if mode doesn't match, but good to be explicit
    if team_id is not None and player_or_team_abbreviation != PlayerOrTeamAbbreviation.team:
        logger.warning("team_id provided but player_or_team_abbreviation is not 'T'. team_id will be ignored.")
        team_id = None # ""

    return fetch_synergy_play_types_logic(
        league_id=league_id,
        per_mode=per_mode,
        player_or_team=player_or_team_abbreviation,
        season_type=season_type,
        season=season,
        play_type_nullable=play_type,
        type_grouping_nullable=effective_type_grouping,
        player_id_nullable=player_id,
        team_id_nullable=team_id
    )

@tool
def get_league_player_on_details(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = "Base",
    per_mode: str = PerModeDetailed.totals,
    team_id: int = 0,
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
    Fetches league-wide player on/off court details.
    Args: Many, see original docstring.
    Returns: JSON string with league player on/off details.
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

@tool(cache_results=True, cache_ttl=86400)
def get_common_all_players(
    season: str,
    league_id: str = LeagueID.nba,
    is_only_current_season: int = 1
) -> str:
    """
    Fetches a list of all players for a given league and season.
    Args: season, league_id, is_only_current_season.
    Returns: JSON string with a list of players.
    """
    logger.debug(f"Tool 'get_common_all_players' called for Season: {season}, LeagueID: {league_id}, IsOnlyCurrentSeason: {is_only_current_season}")
    return fetch_common_all_players_logic(season=season, league_id=league_id, is_only_current_season=is_only_current_season)

@tool(cache_results=True, cache_ttl=86400)
def get_common_playoff_series(
    season: str,
    league_id: str = LeagueID.nba,
    series_id: Optional[str] = None
) -> str:
    """
    Fetches information about playoff series.
    Args: season, league_id, series_id.
    Returns: JSON string with playoff series game details.
    """
    return fetch_common_playoff_series_logic(season=season, league_id=league_id, series_id=series_id)

@tool(cache_results=True, cache_ttl=86400)
def get_common_team_years(league_id: str = LeagueID.nba) -> str:
    """
    Fetches a list of all team years for a given league.
    Args: league_id.
    Returns: JSON string with team year details.
    """
    return fetch_common_team_years_logic(league_id=league_id)

@tool
def get_league_dash_lineups(
    season: str,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type: str = "Base",
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    per_mode: str = "Totals",
    period: int = 0,
    plus_minus: str = "N",
    rank: str = "N",
    season_type: str = "Regular Season",
    conference_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = LeagueID.nba,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None
) -> str:
    """
    Fetches league-wide lineup statistics.
    Args: Many, see original docstring.
    Returns: JSON string with lineup statistics.
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
def get_top_performers(category: str = "PTS", season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, per_mode: str = PerMode48.per_game, top_n: int = 5) -> str:
    """
    Gets the top N players for a specific statistical category.
    Args: category, season, season_type, per_mode, top_n.
    Returns: JSON string with top performers.
    """
    logger.debug(f"Tool 'get_top_performers' called for Cat: {category}, Season: {season}, Type: {season_type}, Mode: {per_mode}, Top: {top_n}")
    result = fetch_top_performers_logic(
        category=category, season=season, season_type=season_type, per_mode=per_mode, top_n=top_n
    )
    return result

@tool
def get_top_teams(season: str = settings.CURRENT_NBA_SEASON, season_type: str = SeasonTypeAllStar.regular, top_n: int = 5) -> str:
    """
    Gets the top N teams based on league standings.
    Args: season, season_type, top_n.
    Returns: JSON string with top teams.
    """
    logger.debug(f"Tool 'get_top_teams' called for Season: {season}, Type: {season_type}, Top: {top_n}")
    result = fetch_top_teams_logic(season=season, season_type=season_type, top_n=top_n)
    return result 