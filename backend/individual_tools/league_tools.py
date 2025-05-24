from typing import Optional, Dict, Any, Union, Tuple, List
import pandas as pd
from agno.tools import tool
from agno.utils.log import logger

# League-wide stats logic functions
from ..api_tools.all_time_leaders_grids import fetch_all_time_leaders_logic
from ..api_tools.assist_leaders import fetch_assist_leaders_logic
from ..api_tools.homepage_leaders import fetch_homepage_leaders_logic
from ..api_tools.homepage_v2 import fetch_homepage_v2_logic
from ..api_tools.ist_standings import fetch_ist_standings_logic
from ..api_tools.leaders_tiles import fetch_leaders_tiles_logic
from ..api_tools.league_dash_player_bio import fetch_league_player_bio_stats_logic
from ..api_tools.league_dash_player_clutch import fetch_league_player_clutch_stats_logic
from ..api_tools.league_dash_player_pt_shot import fetch_league_dash_player_pt_shot_logic
from ..api_tools.league_dash_player_shot_locations import fetch_league_dash_player_shot_locations_logic
from ..api_tools.league_dash_player_stats import fetch_league_player_stats_logic
from ..api_tools.league_dash_pt_defend import fetch_league_dash_pt_defend_logic
from ..api_tools.league_dash_pt_stats import fetch_league_dash_pt_stats_logic
# fetch_league_dash_pt_team_defend_logic is used in team_tools.py
from ..api_tools.league_dash_team_clutch import fetch_league_team_clutch_stats_logic
from ..api_tools.league_dash_team_pt_shot import fetch_league_dash_team_pt_shot_logic
from ..api_tools.league_dash_team_shot_locations import fetch_league_team_shot_locations_logic
from ..api_tools.league_dash_team_stats import fetch_league_team_stats_logic
from ..api_tools.league_draft import fetch_draft_history_logic
from ..api_tools.league_game_log import fetch_league_game_log_logic
from ..api_tools.league_hustle_stats_team import fetch_league_hustle_stats_team_logic
from ..api_tools.league_leaders_data import fetch_league_leaders_logic
from ..api_tools.league_lineups import fetch_league_dash_lineups_logic as fetch_league_lineups_data_logic
from ..api_tools.league_lineup_viz import fetch_league_lineup_viz_logic
from ..api_tools.league_standings import fetch_league_standings_logic
from ..api_tools.player_index import fetch_player_index_logic
from ..api_tools.player_listings import fetch_common_all_players_logic
from ..api_tools.playoff_picture import fetch_playoff_picture_logic
from ..api_tools.playoff_series import fetch_common_playoff_series_logic
from ..api_tools.schedule_league_v2_int import fetch_schedule_league_v2_int_logic
from ..api_tools.shot_chart_league_wide import fetch_shot_chart_league_wide_logic
from ..api_tools.trending_team_tools import fetch_top_teams_logic
from ..api_tools.trending_tools import fetch_top_performers_logic
from ..api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic as fetch_league_player_estimated_metrics_logic


from ..config import settings
from nba_api.stats.library.parameters import (
    SeasonTypeAllStar, PerModeDetailed, LeagueID, MeasureTypeDetailedDefense,
    PerModeSimple, PerModeTime, PlayerOrTeam, PlayerScope, StatCategory, GameScopeDetailed,
    Direction, Sorter, PlayerOrTeamAbbreviation, StatCategoryAbbreviation, PerMode48, Scope,
    DefenseCategory, PtMeasureType, DistanceRange, MeasureTypeSimple # SeasonTypeAllStar imported twice, remove one
)

@tool
def get_all_time_leaders_grids(
    league_id: str = "00",
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    topx: int = 10,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches all-time statistical leaders data grids.
    Args:
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        per_mode (str, optional): Per mode. Defaults to "Totals".
        season_type (str, optional): Season type. Defaults to "Regular Season".
        topx (int, optional): Number of top players. Defaults to 10.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_all_time_leaders_grids for League: {league_id}, PerMode: {per_mode}, TopX: {topx}")
    return fetch_all_time_leaders_logic(
        league_id=league_id,
        per_mode=per_mode,
        season_type=season_type,
        topx=topx,
        return_dataframe=return_dataframe
    )

@tool
def get_assist_leaders(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = "Totals",
    player_or_team: str = "Team", # API uses PlayerOrTeamAbbreviation.team by default
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches assist leaders for players or teams.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "Totals".
        player_or_team (str, optional): Filter by Player or Team. Defaults to "Team".
        return_dataframe (bool, optional): If True, returns (JSON, {'AssistLeaders': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_assist_leaders for League: {league_id}, Season: {season}")
    return fetch_assist_leaders_logic(
        league_id=league_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_or_team=player_or_team,
        return_dataframe=return_dataframe
    )

@tool
def get_homepage_leaders(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypeAllStar.regular, # Parameter for logic function
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    stat_category: str = StatCategory.points,
    game_scope_detailed: str = GameScopeDetailed.season,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches homepage leaders data (team/player leaders, league averages, highs).
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season. Defaults to current season.
        season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
        player_or_team (str, optional): Player or Team. Defaults to "Team".
        player_scope (str, optional): Player scope. Defaults to "All Players".
        stat_category (str, optional): Stat category. Defaults to "Points".
        game_scope_detailed (str, optional): Game scope. Defaults to "Season".
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_homepage_leaders for League: {league_id}, Season: {season}, Stat: {stat_category}")
    return fetch_homepage_leaders_logic(
        league_id=league_id, season=season, season_type_playoffs=season_type_playoffs,
        player_or_team=player_or_team, player_scope=player_scope, stat_category=stat_category,
        game_scope_detailed=game_scope_detailed, return_dataframe=return_dataframe
    )

@tool
def get_homepage_v2_leaders(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypeAllStar.regular,
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    stat_type: str = "Traditional", # API parameter name is StatType
    game_scope_detailed: str = GameScopeDetailed.season,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches V2 homepage leaders data.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season. Defaults to current season.
        season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
        player_or_team (str, optional): Player or Team. Defaults to "Team".
        player_scope (str, optional): Player scope. Defaults to "All Players".
        stat_type (str, optional): Stat type (e.g. "Traditional", "Advanced"). Defaults to "Traditional".
        game_scope_detailed (str, optional): Game scope. Defaults to "Season".
        return_dataframe (bool, optional): If True, returns DataFrames. Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_homepage_v2_leaders for League: {league_id}, Season: {season}, StatType: {stat_type}")
    return fetch_homepage_v2_logic(
        league_id=league_id, season=season, season_type_playoffs=season_type_playoffs,
        player_or_team=player_or_team, player_scope=player_scope, stat_type=stat_type, # Ensure logic uses stat_type
        game_scope_detailed=game_scope_detailed, return_dataframe=return_dataframe
    )

@tool
def get_in_season_tournament_standings(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON,
    section: str = "group", # "group" or "conference"
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches In-Season Tournament standings.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season (YYYY-YY format). Defaults to current season.
        section (str, optional): Standings section ("group" or "conference"). Defaults to "group".
        return_dataframe (bool, optional): If True, returns (JSON, {'standings': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_in_season_tournament_standings for League: {league_id}, Season: {season}, Section: {section}")
    return fetch_ist_standings_logic(
        league_id=league_id,
        season=season,
        section=section,
        return_dataframe=return_dataframe
    )

@tool
def get_leaders_tiles(
    game_scope_detailed: str = GameScopeDetailed.season,
    league_id: str = "00",
    player_or_team: str = PlayerOrTeam.team,
    player_scope: str = PlayerScope.all_players,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_playoffs: str = SeasonTypeAllStar.regular, # Logic function uses season_type
    stat: str = "PTS", # API param is 'stat', not 'stat_category' for this endpoint
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches leaders tiles data, typically for homepage display.
    Args:
        game_scope_detailed (str, optional): Game scope. Defaults to "Season".
        league_id (str, optional): League ID. Defaults to "00".
        player_or_team (str, optional): Player or Team. Defaults to "Team".
        player_scope (str, optional): Player scope. Defaults to "All Players".
        season (str, optional): Season. Defaults to current season.
        season_type_playoffs (str, optional): Season type. Defaults to "Regular Season".
        stat (str, optional): Statistical abbreviation (e.g., "PTS", "REB"). Defaults to "PTS".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeadersTiles': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_leaders_tiles for League: {league_id}, Season: {season}, Stat: {stat}")
    return fetch_leaders_tiles_logic(
        game_scope=game_scope_detailed, # Map to logic param name
        league_id=league_id,
        player_or_team=player_or_team,
        player_scope=player_scope,
        season=season,
        season_type=season_type_playoffs, # Map to logic param name
        stat=stat,
        return_dataframe=return_dataframe
    )

@tool
def get_league_player_bio_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    team_id_nullable: Optional[str] = None, # Changed from team_id to team_id_nullable for clarity
    player_position_nullable: Optional[str] = None,
    player_experience_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide player biographical and statistical data with multiple filter options.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00".
        team_id_nullable (Optional[str], optional): Filter by team ID.
        player_position_nullable (Optional[str], optional): Filter by player position.
        player_experience_nullable (Optional[str], optional): Filter by player experience.
        starter_bench_nullable (Optional[str], optional): Filter by starter/bench role.
        college_nullable (Optional[str], optional): Filter by college.
        country_nullable (Optional[str], optional): Filter by country.
        draft_year_nullable (Optional[str], optional): Filter by draft year.
        height_nullable (Optional[str], optional): Filter by height.
        weight_nullable (Optional[str], optional): Filter by weight.
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerBioStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_bio_stats for Season: {season}")
    return fetch_league_player_bio_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode, league_id=league_id,
        team_id_nullable=team_id_nullable, player_position_nullable=player_position_nullable,
        player_experience_nullable=player_experience_nullable, starter_bench_nullable=starter_bench_nullable,
        college_nullable=college_nullable, country_nullable=country_nullable, draft_year_nullable=draft_year_nullable,
        height_nullable=height_nullable, weight_nullable=weight_nullable, return_dataframe=return_dataframe
    )

@tool
def get_league_player_clutch_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time_nullable: Optional[str] = "Last 5 Minutes", # Mapped from clutch_time
    ahead_behind_nullable: Optional[str] = "Ahead or Behind", # Mapped from ahead_behind
    point_diff_nullable: Optional[int] = 5, # Mapped from point_diff
    league_id: str = "00",
    # Include other relevant filters from LeagueDashPlayerClutch endpoint if needed
    # e.g. outcome_nullable, location_nullable, month_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches clutch statistics for all players in the league.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        measure_type (str, optional): Measure type. Defaults to "Base".
        clutch_time_nullable (Optional[str], optional): Clutch time definition. Defaults to "Last 5 Minutes".
        ahead_behind_nullable (Optional[str], optional): Game situation. Defaults to "Ahead or Behind".
        point_diff_nullable (Optional[int], optional): Point differential. Defaults to 5.
        league_id (str, optional): League ID. Defaults to "00".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerClutchStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_clutch_stats for Season: {season}")
    return fetch_league_player_clutch_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        clutch_time_nullable=clutch_time_nullable, ahead_behind_nullable=ahead_behind_nullable,
        point_diff_nullable=point_diff_nullable, league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_league_player_shooting_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    league_id: str = LeagueID.nba,
    # Add other relevant filters from LeagueDashPlayerPtShot endpoint
    # e.g., player_position_abbreviation_nullable, team_id_nullable, etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide player shooting statistics (catch and shoot, pull-ups, etc.).
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerShootingStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_shooting_stats for Season: {season}")
    return fetch_league_dash_player_pt_shot_logic(
        season=season, season_type_all_star=season_type, # Map to logic param
        per_mode_simple=per_mode, league_id=league_id, # Map to logic params
        return_dataframe=return_dataframe
    )

@tool
def get_league_player_shot_locations(
    distance_range: str = "By Zone", # Default from endpoint, not toolkit
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    # Add other relevant filters like player_id_nullable, team_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide player shot location data.
    Args:
        distance_range (str, optional): Distance range for shots. Defaults to "By Zone".
        season (str, optional): Season. Defaults to current season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        league_id_nullable (str, optional): League ID. Defaults to "".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerShotLocations': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_shot_locations for Season: {season}")
    return fetch_league_dash_player_shot_locations_logic(
        distance_range=distance_range, season=season,
        season_type_all_star=season_type_all_star, league_id_nullable=league_id_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_league_player_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    league_id: str = "00",
    # Add other filters: team_id_nullable, player_position_abbreviation_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches general league-wide player statistics.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        measure_type (str, optional): Measure type. Defaults to "Base".
        league_id (str, optional): League ID. Defaults to "00".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_stats for Season: {season}")
    return fetch_league_player_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_league_player_tracking_defense_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    defense_category: str = DefenseCategory.overall,
    league_id: str = LeagueID.nba,
    # Add player_id_nullable, team_id_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide player defensive tracking statistics.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        defense_category (str, optional): Defense category. Defaults to "Overall".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerDefenseStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_tracking_defense_stats for Season: {season}")
    return fetch_league_dash_pt_defend_logic(
        season=season, season_type=season_type, per_mode=per_mode,
        defense_category=defense_category, league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_league_player_tracking_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    player_or_team: str = PlayerOrTeam.player, # Changed default from Team to Player for player tracking
    pt_measure_type: str = PtMeasureType.speed_distance,
    league_id_nullable: Optional[str] = None,
    # Add team_id_nullable, player_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide player tracking data (speed, distance, etc.).
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        player_or_team (str, optional): Filter by Player or Team. Defaults to "Player".
        pt_measure_type (str, optional): Player tracking measure type. Defaults to "SpeedDistance".
        league_id_nullable (Optional[str], optional): League ID. Defaults to None.
        return_dataframe (bool, optional): If True, returns (JSON, {'LeaguePlayerTrackingStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_tracking_stats for Season: {season}")
    return fetch_league_dash_pt_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode,
        player_or_team=player_or_team, pt_measure_type=pt_measure_type,
        league_id_nullable=league_id_nullable, return_dataframe=return_dataframe
    )

@tool
def get_league_team_tracking_defense_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeSimple.per_game,
    defense_category: str = DefenseCategory.overall,
    league_id: str = LeagueID.nba,
    # Add team_id_nullable to filter by specific team if desired, though this is league-wide focus
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide team defensive tracking statistics.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        defense_category (str, optional): Defense category. Defaults to "Overall".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueTeamDefenseStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_tracking_defense_stats for Season: {season}")
    # This uses fetch_league_dash_pt_team_defend_logic, also used in team_tools but there it has team_id_nullable
    return fetch_league_dash_pt_team_defend_logic(
        season=season, season_type=season_type, per_mode=per_mode,
        defense_category=defense_category, league_id=league_id, 
        # team_id_nullable=None, # Explicitly None for league-wide context
        return_dataframe=return_dataframe
    )

@tool
def get_league_team_clutch_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time_nullable: Optional[str] = "Last 5 Minutes",
    ahead_behind_nullable: Optional[str] = "Ahead or Behind",
    point_diff_nullable: Optional[int] = 5,
    league_id: str = "00",
    # Add other filters like team_id_nullable for specific team, outcome_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches clutch statistics for all teams in the league.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        measure_type (str, optional): Measure type. Defaults to "Base".
        clutch_time_nullable (Optional[str], optional): Clutch time definition. Defaults to "Last 5 Minutes".
        ahead_behind_nullable (Optional[str], optional): Game situation. Defaults to "Ahead or Behind".
        point_diff_nullable (Optional[int], optional): Point differential. Defaults to 5.
        league_id (str, optional): League ID. Defaults to "00".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueTeamClutchStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_clutch_stats for Season: {season}")
    return fetch_league_team_clutch_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        clutch_time_nullable=clutch_time_nullable, ahead_behind_nullable=ahead_behind_nullable,
        point_diff_nullable=point_diff_nullable, league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_league_team_player_tracking_shot_stats(
    league_id: str = "00",
    per_mode_simple: str = PerModeSimple.totals,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    # Add team_id_nullable to filter by specific team if desired
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide team shooting stats from player tracking data.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        per_mode_simple (str, optional): Per mode. Defaults to "Totals".
        season (str, optional): Season. Defaults to current season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueTeamShootingStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_player_tracking_shot_stats for League: {league_id}, Season: {season}")
    return fetch_league_dash_team_pt_shot_logic(
        league_id=league_id, per_mode_simple=per_mode_simple, season=season,
        season_type_all_star=season_type_all_star, return_dataframe=return_dataframe
    )

@tool
def get_league_team_shot_locations(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    measure_type: str = MeasureTypeSimple.base,
    distance_range: str = DistanceRange.by_zone,
    # Add team_id_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide team shot location data.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        measure_type (str, optional): Measure type. Defaults to "Base".
        distance_range (str, optional): Distance range. Defaults to "By Zone".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueTeamShotLocations': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_shot_locations for Season: {season}")
    return fetch_league_dash_team_shot_locations_logic(
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        distance_range=distance_range, return_dataframe=return_dataframe
    )

@tool
def get_league_team_stats(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    league_id: str = "00",
    # Add team_id_nullable, date_from_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches general league-wide team statistics.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        measure_type (str, optional): Measure type. Defaults to "Base".
        league_id (str, optional): League ID. Defaults to "00".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueTeamStats': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_team_stats for Season: {season}")
    return fetch_league_team_stats_logic(
        season=season, season_type=season_type, per_mode=per_mode, measure_type=measure_type,
        league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_draft_history(
    season_year_nullable: Optional[str] = None, # YYYY format, e.g., "2023"
    league_id_nullable: str = LeagueID.nba,
    team_id_nullable: Optional[int] = None,
    round_num_nullable: Optional[int] = None,
    overall_pick_nullable: Optional[int] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches NBA draft history.
    Args:
        season_year_nullable (Optional[str], optional): Draft season year (YYYY). Defaults to None (all years).
        league_id_nullable (str, optional): League ID. Defaults to "00" (NBA).
        team_id_nullable (Optional[int], optional): Filter by team ID. Defaults to None.
        round_num_nullable (Optional[int], optional): Filter by draft round. Defaults to None.
        overall_pick_nullable (Optional[int], optional): Filter by overall pick number. Defaults to None.
        return_dataframe (bool, optional): If True, returns (JSON, {'DraftHistory': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_draft_history for Season Year: {season_year_nullable or 'All'}")
    return fetch_draft_history_logic(
        season_year_nullable=season_year_nullable, league_id_nullable=league_id_nullable,
        team_id_nullable=team_id_nullable, round_num_nullable=round_num_nullable,
        overall_pick_nullable=overall_pick_nullable, return_dataframe=return_dataframe
    )

@tool
def get_league_game_log(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    player_or_team: str = PlayerOrTeamAbbreviation.team,
    league_id: str = LeagueID.nba,
    direction: str = Direction.asc,
    sorter: str = Sorter.date,
    # Add date_from_nullable, date_to_nullable, team_id_nullable, player_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league game logs for players or teams.
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        player_or_team (str, optional): Player or Team abbreviation. Defaults to "T" (Team).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        direction (str, optional): Sort direction. Defaults to "ASC".
        sorter (str, optional): Sort criteria. Defaults to "DATE".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueGameLog': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_game_log for Season: {season}, Entity: {player_or_team}")
    return fetch_league_game_log_logic(
        season=season, season_type_all_star=season_type, # Map to logic param
        player_or_team_abbreviation=player_or_team, league_id=league_id,
        direction=direction, sorter=sorter, return_dataframe=return_dataframe
    )

@tool
def get_league_hustle_stats_team(
    per_mode_time: str = PerModeTime.totals,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    # Add date_from, date_to, team_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide team hustle statistics.
    Args:
        per_mode_time (str, optional): Per mode for time. Defaults to "Totals".
        season (str, optional): Season. Defaults to current season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        league_id_nullable (str, optional): League ID. Defaults to "".
        return_dataframe (bool, optional): If True, returns (JSON, {'HustleStatsTeam': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_hustle_stats_team for Season: {season}")
    return fetch_league_hustle_stats_team_logic(
        per_mode_time=per_mode_time, season=season, season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable, return_dataframe=return_dataframe
    )

@tool
def get_league_leaders(
    season: str, # Non-optional as per logic function
    stat_category: str = StatCategoryAbbreviation.pts,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game, # API uses PerMode48
    league_id: str = LeagueID.nba,
    scope: str = Scope.s, # Scope.s = Season, Scope.rs = Regular Season + Playoffs
    top_n: int = 10, # Custom parameter for controlling output size
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league leaders for a specific statistical category.
    Args:
        season (str): Season (YYYY-YY format).
        stat_category (str, optional): Stat category abbreviation (e.g., "PTS", "REB"). Defaults to "PTS".
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        scope (str, optional): Scope of stats (e.g., "S" for season). Defaults to "S".
        top_n (int, optional): Number of leaders to return. Defaults to 10.
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueLeaders': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_leaders for Season: {season}, Stat: {stat_category}, TopN: {top_n}")
    return fetch_league_leaders_logic(
        season=season, stat_category_abbreviation=stat_category, season_type_all_star=season_type,
        per_mode48=per_mode, league_id=league_id, scope=scope, top_n=top_n, # Ensure logic uses top_n
        return_dataframe=return_dataframe
    )

@tool
def get_league_lineups_data(
    season: str, # Made non-optional as it's key for lineups
    group_quantity: int = 5,
    measure_type: str = MeasureTypeDetailedDefense.base,
    per_mode: str = PerModeDetailed.totals,
    season_type: str = SeasonTypeAllStar.regular, # Logic uses season_type_all_star
    # Add team_id_nullable if filtering by team is desired for league-wide lineup endpoint
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide lineup data.
    Args:
        season (str): Season (YYYY-YY format).
        group_quantity (int, optional): Number of players in lineup. Defaults to 5.
        measure_type (str, optional): Measure type. Defaults to "Base".
        per_mode (str, optional): Per mode. Defaults to "Totals".
        season_type (str, optional): Season type. Defaults to "Regular Season".
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    logger.info(f"Tool: get_league_lineups_data for Season: {season}")
    return fetch_league_lineups_data_logic(
        season=season, group_quantity=group_quantity, measure_type_detailed_defense=measure_type,
        per_mode_detailed=per_mode, season_type_all_star=season_type, return_dataframe=return_dataframe
    )

@tool
def get_league_lineup_viz_data(
    minutes_min: int = 5,
    group_quantity: int = 5,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    league_id_nullable: str = "",
    # Add other filters like team_id_nullable
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches data for league lineup visualizations.
    Args:
        minutes_min (int, optional): Minimum minutes played for lineup. Defaults to 5.
        group_quantity (int, optional): Number of players in lineup. Defaults to 5.
        season (str, optional): Season. Defaults to current season.
        season_type_all_star (str, optional): Season type. Defaults to "Regular Season".
        league_id_nullable (str, optional): League ID. Defaults to "".
        return_dataframe (bool, optional): If True, returns (JSON, {'LeagueLineupViz': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_lineup_viz_data for Season: {season}")
    return fetch_league_lineup_viz_logic(
        minutes_min=minutes_min, group_quantity=group_quantity, season=season,
        season_type_all_star=season_type_all_star, league_id_nullable=league_id_nullable,
        return_dataframe=return_dataframe
    )

@tool
def get_league_standings(
    season: Optional[str] = None, # YYYY-YY format
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league standings.
    Args:
        season (Optional[str], optional): Season (YYYY-YY). Defaults to current season if None.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'Standings': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    effective_season = season if season is not None else settings.CURRENT_NBA_SEASON
    logger.info(f"Tool: get_league_standings for Season: {effective_season}")
    return fetch_league_standings_logic(
        season=effective_season, season_type=season_type, league_id=league_id, return_dataframe=return_dataframe
    )

@tool
def get_player_index(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON,
    player_id_nullable: Optional[str] = None, # Added to allow lookup for specific player by ID
    player_name_nullable: Optional[str] = None, # Added to allow lookup for specific player by name
    active_nullable: Optional[str] = None, # "YES" or "NO"
    allstar_nullable: Optional[str] = None, # "YES" or "NO"
    historical_nullable: Optional[str] = None, # "YES" or "NO"
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the player index, a list of players with basic info.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season. Defaults to current season.
        player_id_nullable (Optional[str], optional): Filter by player ID.
        player_name_nullable (Optional[str], optional): Filter by player name (partial match).
        active_nullable (Optional[str], optional): Filter by active status ("YES" or "NO").
        allstar_nullable (Optional[str], optional): Filter by All-Star status ("YES" or "NO").
        historical_nullable (Optional[str], optional): Filter by historical status ("YES" or "NO").
        return_dataframe (bool, optional): If True, returns (JSON, {'PlayerIndex': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_player_index for League: {league_id}, Season: {season}")
    # Pass all specific filters to the logic function
    return fetch_player_index_logic(
        league_id=league_id, season=season, 
        player_id_nullable=player_id_nullable, player_name_nullable=player_name_nullable,
        active_nullable=active_nullable, allstar_nullable=allstar_nullable,
        historical_nullable=historical_nullable, return_dataframe=return_dataframe
    )

@tool
def get_common_all_players(
    season: str, # YYYY-YY format, made non-optional as it's usually specific for "all players" lists
    league_id: str = LeagueID.nba,
    is_only_current_season: int = 1, # 1 for current, 0 for all-time associated with season
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches a list of all common players for a given season or historically.
    Args:
        season (str): Season (YYYY-YY format).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        is_only_current_season (int, optional): 1 for current season players, 0 for historical. Defaults to 1.
        return_dataframe (bool, optional): If True, returns (JSON, {'CommonAllPlayers': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_common_all_players for Season: {season}, League: {league_id}")
    return fetch_common_all_players_logic(
        season=season, league_id=league_id, is_only_current_season=is_only_current_season, return_dataframe=return_dataframe
    )

@tool
def get_playoff_picture(
    league_id: str = "00",
    season_id: str = "22023", # Uses NNNNYY format e.g. 22023 for 2023-24 season
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the playoff picture for a given season.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season_id (str, optional): Season ID (NNNNYY format, e.g., 22023 for 2023-24). Defaults to current NBA season format.
        return_dataframe (bool, optional): If True, returns (JSON, Dict of DataFrames for East/West). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrames dict).
    """
    # Logic for CURRENT_NBA_SEASON_ID might be specific, e.g., f"2{settings.CURRENT_NBA_SEASON[:2]}{settings.CURRENT_NBA_SEASON[-2:]}"
    # For simplicity, using the default from toolkit, but this might need adjustment if settings.CURRENT_NBA_SEASON is YYYY-YY
    effective_season_id = season_id 
    # Example: if settings.CURRENT_NBA_SEASON is "2023-24", season_id might be "22023"
    # This logic needs to be robust based on how season_id is truly derived for the API.
    if season_id == "22023" and settings.CURRENT_NBA_SEASON != "2023-24": # Basic check
        logger.warning(f"Default season_id {season_id} might not match current settings season {settings.CURRENT_NBA_SEASON}")

    logger.info(f"Tool: get_playoff_picture for League: {league_id}, SeasonID: {effective_season_id}")
    return fetch_playoff_picture_logic(
        league_id=league_id, season_id=effective_season_id, return_dataframe=return_dataframe
    )

@tool
def get_common_playoff_series(
    season: str, # YYYY-YY format
    league_id: str = LeagueID.nba,
    series_id_nullable: Optional[str] = None,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches common playoff series information for a season.
    Args:
        season (str): Season (YYYY-YY format).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        series_id_nullable (Optional[str], optional): Specific series ID to filter. Defaults to None.
        return_dataframe (bool, optional): If True, returns (JSON, {'PlayoffSeries': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_common_playoff_series for Season: {season}, League: {league_id}")
    return fetch_common_playoff_series_logic(
        season=season, league_id=league_id, series_id_nullable=series_id_nullable, return_dataframe=return_dataframe
    )

@tool
def get_league_schedule(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON, # YYYY format for this endpoint logic
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches the league schedule for a given season.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season (YYYY format, e.g., "2023" for 2023-24 season). Defaults to current season's year.
        return_dataframe (bool, optional): If True, returns (JSON, {'Schedule': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    # Assuming settings.CURRENT_NBA_SEASON is YYYY-YY, extract YYYY
    effective_season_year = season
    if len(season) == 7 and season[4] == '-': # YYYY-YY format
        effective_season_year = season[:4]
    elif len(season) != 4 or not season.isdigit():
        logger.warning(f"Season format for get_league_schedule should be YYYY. Received: {season}. Attempting to use first 4 digits if applicable.")
        if len(settings.CURRENT_NBA_SEASON) >= 4:
             effective_season_year = settings.CURRENT_NBA_SEASON[:4]
        else: # Fallback, though likely to fail API side
            effective_season_year = "2023" 

    logger.info(f"Tool: get_league_schedule for League: {league_id}, Season Year: {effective_season_year}")
    return fetch_schedule_league_v2_int_logic(
        league_id=league_id, season=effective_season_year, return_dataframe=return_dataframe
    )

@tool
def get_shot_chart_league_wide(
    league_id: str = "00",
    season: str = settings.CURRENT_NBA_SEASON, # YYYY-YY format
    # Add other filters: player_id_nullable, team_id_nullable, game_id_nullable etc.
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches league-wide shot chart data.
    Args:
        league_id (str, optional): League ID. Defaults to "00".
        season (str, optional): Season (YYYY-YY format). Defaults to current season.
        return_dataframe (bool, optional): If True, returns (JSON, {'ShotChartLeagueWide': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_shot_chart_league_wide for League: {league_id}, Season: {season}")
    return fetch_shot_chart_league_wide_logic(
        league_id=league_id, season=season, return_dataframe=return_dataframe
    )

@tool
def get_top_performing_teams(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    top_n: int = 5,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches top performing teams based on various criteria (implementation specific).
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        top_n (int, optional): Number of teams to return. Defaults to 5.
        return_dataframe (bool, optional): If True, returns (JSON, {'TopTeams': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_top_performing_teams for Season: {season}, TopN: {top_n}")
    return fetch_top_teams_logic(
        season=season, season_type=season_type, league_id=league_id,
        top_n=top_n, return_dataframe=return_dataframe
    )

@tool
def get_top_performing_players(
    category: str = StatCategoryAbbreviation.pts,
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerMode48.per_game,
    scope: str = Scope.s,
    league_id: str = LeagueID.nba,
    top_n: int = 5,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]:
    """
    Fetches top performing players in a given statistical category.
    Args:
        category (str, optional): Stat category abbreviation (e.g., "PTS", "REB"). Defaults to "PTS".
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        per_mode (str, optional): Per mode. Defaults to "PerGame".
        scope (str, optional): Scope. Defaults to "S" (Season).
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        top_n (int, optional): Number of players to return. Defaults to 5.
        return_dataframe (bool, optional): If True, returns (JSON, {'TopPlayers': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_top_performing_players for Category: {category}, Season: {season}, TopN: {top_n}")
    return fetch_top_performers_logic(
        category=category, season=season, season_type=season_type, per_mode=per_mode,
        scope=scope, league_id=league_id, top_n=top_n, return_dataframe=return_dataframe
    )

@tool
def get_league_player_estimated_metrics(
    season: str = settings.CURRENT_NBA_SEASON,
    season_type: str = SeasonTypeAllStar.regular,
    league_id: str = LeagueID.nba,
    return_dataframe: bool = False
) -> Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: # Adapted return type for tool
    """
    Fetches league-wide player estimated metrics (e.g., PIE).
    Args:
        season (str, optional): Season. Defaults to current season.
        season_type (str, optional): Season type. Defaults to "Regular Season".
        league_id (str, optional): League ID. Defaults to "00" (NBA).
        return_dataframe (bool, optional): If True, returns (JSON, {'PlayerEstimatedMetrics': DataFrame}). Defaults to False.
    Returns:
        Union[str, Tuple[str, Dict[str, pd.DataFrame]]]: JSON string or (JSON, DataFrame dict).
    """
    logger.info(f"Tool: get_league_player_estimated_metrics for Season: {season}")
    # The original logic function might return a DataFrame directly or a more complex structure.
    # This tool wrapper standardizes it to (JSON_string, Dict[str, pd.DataFrame]) if return_dataframe is True.
    return fetch_league_player_estimated_metrics_logic(
        season=season, season_type=season_type, league_id=league_id, return_dataframe=return_dataframe
    ) 