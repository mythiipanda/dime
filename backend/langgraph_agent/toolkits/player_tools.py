from typing import Optional, Dict, Any, List, Union, Tuple
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.api_tools.shot_charts import fetch_player_shot_chart as fetch_player_shot_chart_data
from nba_api.stats.library.parameters import PerModeSimple, PerModeDetailed, SeasonTypeAllStar, SeasonTypePlayoffs, MeasureTypeDetailedDefense, MeasureTypeDetailed, PerModeTime
class PlayerShotChartInput(BaseModel):
    """Input schema for the Player Shot Chart tool."""
    player_name: str = Field(
        ..., description="The full name of the player (e.g., 'LeBron James')."
    )
    season: Optional[str] = Field(
        None, description="The NBA season in YYYY-YY format (e.g., '2023-24'). If None, uses the current season."
    )
    season_type: Optional[str] = Field(
        "Regular Season",
        description="The type of season. Options: 'Regular Season', 'Playoffs', 'Pre Season', 'All Star'."
    )
    context_measure: Optional[str] = Field(
        "FGA",
        description="The statistical measure for the shot chart. Options: 'FGA', 'FGM', 'FG_PCT', etc."
    )
    last_n_games: Optional[int] = Field(
        0,
        description="Number of most recent games to include (0 for all games in the season)."
    )

@tool("get_player_shot_chart", args_schema=PlayerShotChartInput)
def get_player_shot_chart(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    context_measure: str = "FGA",
    last_n_games: int = 0
) -> str:
    """Fetches detailed shot chart data for a specific NBA player, including shot locations, makes/misses, and zone analysis compared to league averages. Useful for understanding a player's shooting tendencies and efficiency from different areas of the court."""
    
    json_response = fetch_player_shot_chart_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        context_measure=context_measure,
        last_n_games=last_n_games,
        return_dataframe=False
    )
    return json_response
from typing import Optional, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from nba_api.stats.library.parameters import SeasonTypeAllStar

from backend.api_tools.player_aggregate_stats import fetch_player_stats_logic as fetch_player_aggregate_stats_data
from backend.api_tools.player_career_by_college import get_player_career_by_college as fetch_player_career_by_college_data
from backend.api_tools.player_career_by_college_rollup import get_player_career_by_college_rollup as fetch_player_career_by_college_rollup_data
from backend.api_tools.player_career_data import fetch_player_career_stats_logic as fetch_player_career_stats_data, fetch_player_awards_logic as fetch_player_awards_data
from backend.api_tools.player_clutch import fetch_player_clutch_stats_logic as fetch_player_clutch_stats_data
from backend.api_tools.player_common_info import fetch_player_info_logic as fetch_player_info_data
from backend.api_tools.player_compare import get_player_compare as fetch_player_compare_data
from backend.api_tools.player_dashboard_by_year_over_year import fetch_player_dashboard_by_year_over_year_logic as fetch_player_dashboard_by_year_over_year_data
from backend.api_tools.player_dashboard_game import fetch_player_dashboard_game_splits_logic as fetch_player_dashboard_game_splits_data
from backend.api_tools.player_dashboard_general import fetch_player_dashboard_general_splits_logic as fetch_player_dashboard_general_splits_data
from backend.api_tools.player_dashboard_lastn import fetch_player_dashboard_lastn_games_logic as fetch_player_dashboard_lastn_games_data
from backend.api_tools.player_dashboard_shooting import fetch_player_dashboard_shooting_splits_logic as fetch_player_dashboard_shooting_splits_data
from backend.api_tools.player_dashboard_stats import fetch_player_profile_logic as fetch_player_profile_data, fetch_player_defense_logic as fetch_player_defense_data, fetch_player_hustle_stats_logic as fetch_player_hustle_stats_data
from backend.api_tools.player_estimated_metrics import fetch_player_estimated_metrics_logic as fetch_player_estimated_metrics_data
from backend.api_tools.player_fantasy_profile import get_player_fantasy_profile as fetch_player_fantasy_profile_data
from backend.api_tools.player_fantasy_profile_bar_graph import get_player_fantasy_profile_bar_graph as fetch_player_fantasy_profile_bar_graph_data
from backend.api_tools.player_gamelogs import fetch_player_gamelog_logic as fetch_player_gamelog_data
from backend.api_tools.player_game_logs import fetch_player_game_logs_logic as fetch_player_game_logs_data
from backend.api_tools.player_game_streak_finder import get_player_game_streak_finder as fetch_player_game_streak_finder_data
from backend.api_tools.player_index import get_player_index as fetch_player_index_data
from backend.api_tools.player_listings import fetch_common_all_players_logic as fetch_common_all_players_data
from backend.api_tools.player_passing import fetch_player_passing_stats_logic as fetch_player_passing_stats_data
from backend.api_tools.player_rebounding import fetch_player_rebounding_stats_logic as fetch_player_rebounding_stats_data
from backend.api_tools.player_shooting_tracking import fetch_player_shots_tracking_logic as fetch_player_shots_tracking_data
from backend.api_tools.player_vs_player import fetch_player_vs_player_stats_logic as fetch_player_vs_player_stats_data
from backend.api_tools.playoff_series import fetch_common_playoff_series_logic as fetch_common_playoff_series_data


class PlayerAggregateStatsInput(BaseModel):
    """Input schema for the Player Aggregate Stats tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default=None,
        description="The season for which to fetch game logs (YYYY-YY format). Defaults to the current NBA season if None."
    )
    season_type: str = Field(
        default=SeasonTypeAllStar.regular,
        description="The type of season for game logs (e.g., 'Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )

@tool("get_player_aggregate_stats", args_schema=PlayerAggregateStatsInput)
def get_player_aggregate_stats(
    player_name: str,
    season: Optional[str] = None,
    season_type: str = SeasonTypeAllStar.regular
) -> str:
    """Aggregates various player statistics including common info, career stats, game logs for a specified season, and awards history.
    Returns a JSON string containing the aggregated player statistics."""
    
    json_response = fetch_player_aggregate_stats_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        return_dataframe=False
    )
    return json_response
class PlayerCareerByCollegeInput(BaseModel):
    """Input schema for the Player Career By College tool."""
    college: str = Field(description="The name of the college (e.g., 'Duke', 'Kentucky').")
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    per_mode_simple: Optional[str] = Field(
        default=PerModeSimple.totals,
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season_type_all_star: Optional[str] = Field(
        default=SeasonTypeAllStar.regular,
        description="Season type ('Regular Season', 'Playoffs', 'All-Star')."
    )
    season_nullable: Optional[str] = Field(
        default="",
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). Leave empty for all seasons."
    )

@tool("get_player_career_by_college_stats", args_schema=PlayerCareerByCollegeInput)
def get_player_career_by_college_stats(
    college: str,
    league_id: str = "00",
    per_mode_simple: str = PerModeSimple.totals,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    season_nullable: str = ""
) -> str:
    """Fetches career statistics for players from a specific college.
    Allows filtering by league, per mode (totals or per game), season type, and specific season.
    Returns a JSON string containing the player career by college data."""
    
    json_response = fetch_player_career_by_college_data(
        college=college,
        league_id=league_id,
        per_mode_simple=per_mode_simple,
        season_type_all_star=season_type_all_star,
        season_nullable=season_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerCareerByCollegeRollupInput(BaseModel):
    """Input schema for the Player Career By College Rollup tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    per_mode_simple: Optional[str] = Field(
        default=PerModeSimple.totals,
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season_type_all_star: Optional[str] = Field(
        default=SeasonTypeAllStar.regular,
        description="Season type ('Regular Season', 'Playoffs', 'All-Star')."
    )
    season_nullable: Optional[str] = Field(
        default="",
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). Leave empty for all seasons."
    )

@tool("get_player_career_by_college_rollup_stats", args_schema=PlayerCareerByCollegeRollupInput)
def get_player_career_by_college_rollup_stats(
    league_id: str = "00",
    per_mode_simple: str = PerModeSimple.totals,
    season_type_all_star: str = SeasonTypeAllStar.regular,
    season_nullable: str = ""
) -> str:
    """Fetches aggregated career statistics for players by college, providing rollup data for different regions.
    Allows filtering by league, per mode (totals or per game), season type, and specific season.
    Returns a JSON string containing the player career by college rollup data."""
    
    json_response = fetch_player_career_by_college_rollup_data(
        league_id=league_id,
        per_mode_simple=per_mode_simple,
        season_type_all_star=season_type_all_star,
        season_nullable=season_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerCareerStatsInput(BaseModel):
    """Input schema for the Player Career Stats tool."""
    player_name: str = Field(description="The name or ID of the player.")
    per_mode: Optional[str] = Field(
        default=PerModeDetailed.per_game,
        description="The statistical mode ('PerGame', 'Totals', 'Per36', 'Per48', 'MinutesPer', 'PerPlay', 'PerPossession', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    league_id_nullable: Optional[str] = Field(
        default=None,
        description="The league ID to filter results (e.g., '00' for NBA). Optional."
    )

@tool("get_player_career_stats", args_schema=PlayerCareerStatsInput)
def get_player_career_stats(
    player_name: str,
    per_mode: str = PerModeDetailed.per_game,
    league_id_nullable: Optional[str] = None
) -> str:
    """Fetches player career statistics including regular season and postseason totals.
    Returns a JSON string containing player career statistics."""
    
    json_response = fetch_player_career_stats_data(
        player_name=player_name,
        per_mode=per_mode,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

class PlayerAwardsInput(BaseModel):
    """Input schema for the Player Awards tool."""
    player_name: str = Field(description="The name or ID of the player.")

@tool("get_player_awards", args_schema=PlayerAwardsInput)
def get_player_awards(
    player_name: str
) -> str:
    """Fetches a list of awards received by the player.
    Returns a JSON string containing a list of player awards."""
    
    json_response = fetch_player_awards_data(
        player_name=player_name,
        return_dataframe=False
    )
    return json_response
class PlayerClutchStatsInput(BaseModel):
    """Input schema for the Player Clutch Stats tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default=None,
        description="Season in YYYY-YY format. Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default=SeasonTypeAllStar.regular,
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season'). Defaults to 'Regular Season'."
    )
    measure_type: Optional[str] = Field(
        default=MeasureTypeDetailed.base,
        description="Type of stats ('Base', 'Advanced', 'Misc', 'Usage', 'FourFactors', 'Scoring', 'Opponent', 'Defense', 'Hustle', 'Tracking'). Defaults to 'Base'."
    )
    per_mode: Optional[str] = Field(
        default=PerModeDetailed.totals,
        description="Statistical mode ('Totals', 'PerGame', 'Per36', 'Per48', 'MinutesPer', 'PerPlay', 'PerPossession', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID. Defaults to '00' (NBA)."
    )
    plus_minus: Optional[str] = Field(
        default="N",
        description="Flag for plus-minus stats ('Y' or 'N'). Defaults to 'N'."
    )
    pace_adjust: Optional[str] = Field(
        default="N",
        description="Flag for pace adjustment ('Y' or 'N'). Defaults to 'N'."
    )
    rank: Optional[str] = Field(
        default="N",
        description="Flag for ranking ('Y' or 'N'). Defaults to 'N'."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Filter by last N games. Defaults to 0 (all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Filter by month (1-12). Defaults to 0 (all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID. Defaults to 0 (all opponents)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Filter by period (e.g., 1, 2, 3, 4 for quarters, 0 for all). Defaults to 0."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range (e.g., '24-22', '4-0 Very Late'). Optional."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment (e.g., 'First Half', 'Overtime'). Optional."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home' or 'Road'). Optional."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome ('W' or 'L'). Optional."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference (e.g., 'East', 'West'). Optional."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division (e.g., 'Atlantic', 'Pacific'). Optional."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment (e.g., 'Post All-Star'). Optional."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter (YYYY-MM-DD). Optional."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter (YYYY-MM-DD). Optional."
    )

@tool("get_player_clutch_stats", args_schema=PlayerClutchStatsInput)
def get_player_clutch_stats(
    player_name: str,
    season: str = "2023-24",
    season_type: str = SeasonTypeAllStar.regular,
    measure_type: str = MeasureTypeDetailed.base,
    per_mode: str = PerModeDetailed.totals,
    league_id: Optional[str] = "00",
    plus_minus: str = "N",
    pace_adjust: str = "N",
    rank: str = "N",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    shot_clock_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """Fetches player clutch performance statistics, which are stats from critical moments in games.
    Allows extensive filtering by season, season type, measure type, per mode, league, plus/minus, pace adjustment, ranking,
    number of last games, month, opponent, period, shot clock range, game segment, location, outcome,
    opponent conference/division, season segment, and date range.
    Returns a JSON string with clutch stats dashboards."""
    
    json_response = fetch_player_clutch_stats_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        league_id=league_id,
        plus_minus=plus_minus,
        pace_adjust=pace_adjust,
        rank=rank,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        shot_clock_range_nullable=shot_clock_range_nullable,
        game_segment_nullable=game_segment_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        season_segment_nullable=season_segment_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerInfoInput(BaseModel):
    """Input schema for the Player Info tool."""
    player_name: str = Field(description="The name or ID of the player.")
    league_id_nullable: Optional[str] = Field(
        default=None,
        description="The league ID to filter results (e.g., '00' for NBA). Optional."
    )

@tool("get_player_info", args_schema=PlayerInfoInput)
def get_player_info(
    player_name: str,
    league_id_nullable: Optional[str] = None
) -> str:
    """Fetches common player information, headline stats, and available seasons for a given player.
    Returns a JSON string containing player information, headline stats, and available seasons."""
    
    json_response = fetch_player_info_data(
        player_name=player_name,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerCompareInput(BaseModel):
    """Input schema for the Player Compare tool."""
    vs_player_id_list: List[str] = Field(
        description="A list of player IDs to compare against (e.g., ['2544'] for LeBron James)."
    )
    player_id_list: List[str] = Field(
        description="A list of player IDs to compare (e.g., ['201939'] for Stephen Curry)."
    )
    season: Optional[str] = Field(
        default="2023-24",
        description="The NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to the current NBA season."
    )
    season_type_playoffs: Optional[str] = Field(
        default=SeasonTypePlayoffs.regular,
        description="Season type ('Regular Season' or 'Playoffs'). Defaults to 'Regular Season'."
    )
    per_mode_detailed: Optional[str] = Field(
        default=PerModeDetailed.totals,
        description="Statistical mode ('Totals', 'PerGame', 'Per36', 'Per48', 'MinutesPer', 'PerPlay', 'PerPossession', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )
    measure_type_detailed_defense: Optional[str] = Field(
        default=MeasureTypeDetailedDefense.base,
        description="Measure type ('Base', 'Advanced', 'Misc', 'Usage', 'FourFactors', 'Scoring', 'Opponent', 'Defense', 'Hustle', 'Tracking'). Defaults to 'Base'."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="League ID ('00' for NBA, '10' for WNBA, or empty for all). Defaults to empty."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of most recent games to include (0 for all games in the season). Defaults to 0."
    )
    pace_adjust: Optional[str] = Field(
        default="N",
        description="Flag for pace adjustment ('Y' or 'N'). Defaults to 'N'."
    )
    plus_minus: Optional[str] = Field(
        default="N",
        description="Flag for plus-minus stats ('Y' or 'N'). Defaults to 'N'."
    )
    rank: Optional[str] = Field(
        default="N",
        description="Flag for ranking ('Y' or 'N'). Defaults to 'N'."
    )

@tool("get_player_compare_stats", args_schema=PlayerCompareInput)
def get_player_compare_stats(
    vs_player_id_list: List[str],
    player_id_list: List[str],
    season: str = "2023-24",
    season_type_playoffs: str = SeasonTypePlayoffs.regular,
    per_mode_detailed: str = PerModeDetailed.totals,
    measure_type_detailed_defense: str = MeasureTypeDetailedDefense.base,
    league_id_nullable: str = "",
    last_n_games: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N"
) -> str:
    """Fetches player comparison data, allowing for head-to-head statistical analysis between two or more players.
    Allows extensive filtering by season, season type, per mode, measure type, league, last N games, pace adjustment, plus/minus, and ranking.
    Returns a JSON string with player comparison data."""
    
    json_response = fetch_player_compare_data(
        vs_player_id_list=vs_player_id_list,
        player_id_list=player_id_list,
        season=season,
        season_type_playoffs=season_type_playoffs,
        per_mode_detailed=per_mode_detailed,
        measure_type_detailed_defense=measure_type_detailed_defense,
        league_id_nullable=league_id_nullable,
        last_n_games=last_n_games,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        return_dataframe=False
    )
    return json_response
class PlayerDashboardByYearOverYearInput(BaseModel):
    """Input schema for the Player Dashboard By Year Over Year tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="The season in YYYY-YY format. Defaults to current NBA season."
    )

@tool("get_player_dashboard_by_year_over_year", args_schema=PlayerDashboardByYearOverYearInput)
def get_player_dashboard_by_year_over_year(
    player_name: str,
    season: str = "2023-24"
) -> str:
    """Fetches player dashboard statistics broken down by year over year.
    Returns a JSON string containing the player's dashboard data."""
    
    json_response = fetch_player_dashboard_by_year_over_year_data(
        player_name=player_name,
        season=season,
        return_dataframe=False
    )
    return json_response
class PlayerDashboardGameSplitsInput(BaseModel):
    """Input schema for the Player Dashboard Game Splits tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage'). Defaults to 'Base'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )

@tool("get_player_dashboard_game_splits", args_schema=PlayerDashboardGameSplitsInput)
def get_player_dashboard_game_splits(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """Fetches player dashboard statistics broken down by various game-related splits, including overall, by half, by period, by score margin, and by actual margin.
    Allows filtering by season, season type, measure type, and per mode.
    Returns a JSON string with dashboard data."""
    
    json_response = fetch_player_dashboard_game_splits_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=False
    )
    return json_response
class PlayerDashboardGeneralSplitsInput(BaseModel):
    """Input schema for the Player Dashboard General Splits tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage'). Defaults to 'Base'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )

@tool("get_player_dashboard_general_splits", args_schema=PlayerDashboardGeneralSplitsInput)
def get_player_dashboard_general_splits(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """Fetches player dashboard statistics broken down by general splits, including overall, location (home/away), wins/losses, month, pre/post All-Star break, starting position, and days rest.
    Allows filtering by season, season type, measure type, and per mode.
    Returns a JSON string with dashboard data."""
    
    json_response = fetch_player_dashboard_general_splits_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=False
    )
    return json_response
class PlayerDashboardLastNGamesInput(BaseModel):
    """Input schema for the Player Dashboard Last N Games tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage'). Defaults to 'Base'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )

@tool("get_player_dashboard_last_n_games", args_schema=PlayerDashboardLastNGamesInput)
def get_player_dashboard_last_n_games(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """Fetches player dashboard statistics broken down by the last N games, including overall, last 5, last 10, last 15, last 20 games, and by game number.
    Allows filtering by season, season type, measure type, and per mode.
    Returns a JSON string with dashboard data."""
    
    json_response = fetch_player_dashboard_lastn_games_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=False
    )
    return json_response
class PlayerDashboardShootingSplitsInput(BaseModel):
    """Input schema for the Player Dashboard Shooting Splits tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage'). Defaults to 'Base'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )

@tool("get_player_dashboard_shooting_splits", args_schema=PlayerDashboardShootingSplitsInput)
def get_player_dashboard_shooting_splits(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals"
) -> str:
    """Fetches player dashboard statistics broken down by shooting splits, including overall, shot type, shot area, shot distance, and assisted/unassisted shots.
    Allows filtering by season, season type, measure type, and per mode.
    Returns a JSON string with dashboard data."""
    
    json_response = fetch_player_dashboard_shooting_splits_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        return_dataframe=False
    )
    return json_response
class PlayerProfileInput(BaseModel):
    """Input schema for the Player Profile tool."""
    player_name: str = Field(description="The name or ID of the player.")
    per_mode: Optional[str] = Field(
        default=PerModeDetailed.per_game,
        description="Statistical mode for career/season stats ('PerGame', 'Totals', 'Per36', 'Per48', 'MinutesPer', 'PerPlay', 'PerPossession', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    league_id: Optional[str] = Field(
        default=None,
        description="League ID to filter data (e.g., '00' for NBA). Optional."
    )

@tool("get_player_profile", args_schema=PlayerProfileInput)
def get_player_profile(
    player_name: str,
    per_mode: Optional[str] = PerModeDetailed.per_game,
    league_id: Optional[str] = None
) -> str:
    """Fetches comprehensive player profile information including career stats, season stats, highs, and next game details.
    Returns a JSON string containing the player's profile data."""
    
    json_response = fetch_player_profile_data(
        player_name=player_name,
        per_mode=per_mode,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

class PlayerDefenseInput(BaseModel):
    """Input schema for the Player Defense tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="The season in YYYY-YY format. Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default=SeasonTypeAllStar.regular,
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default=PerModeDetailed.per_game,
        description="Statistical mode ('Totals', 'PerGame', 'MinutesPer', 'Per36', 'Per48', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent's team ID. Defaults to 0 (all opponents)."
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD). Optional."
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD). Optional."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of most recent games to include. Defaults to 0 (all games)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID. Defaults to '00' (NBA)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month number (1-12). Defaults to 0 (all months)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period number (1-4, 0 for all). Defaults to 0 (all periods)."
    )
    team_id: Optional[int] = Field(
        default=0,
        description="Team ID of the player. Defaults to 0 (all teams)."
    )
    vs_conference: Optional[str] = Field(
        default=None,
        description="Conference filter ('East', 'West'). Optional."
    )
    vs_division: Optional[str] = Field(
        default=None,
        description="Division filter. Optional."
    )
    season_segment: Optional[str] = Field(
        default=None,
        description="Season segment filter (e.g., 'Post All-Star'). Optional."
    )
    outcome: Optional[str] = Field(
        default=None,
        description="Game outcome filter ('W', 'L'). Optional."
    )
    location: Optional[str] = Field(
        default=None,
        description="Game location filter ('Home', 'Road'). Optional."
    )
    game_segment: Optional[str] = Field(
        default=None,
        description="Game segment filter (e.g., 'First Half'). Optional."
    )

@tool("get_player_defense_stats", args_schema=PlayerDefenseInput)
def get_player_defense_stats(
    player_name: str,
    season: str = "2023-24",
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeDetailed.per_game,
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    period: int = 0,
    team_id: int = 0,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    season_segment: Optional[str] = None,
    outcome: Optional[str] = None,
    location: Optional[str] = None,
    game_segment: Optional[str] = None
) -> str:
    """Fetches player defensive statistics, including defended shots and opponent shooting percentages.
    Allows extensive filtering by season, season type, per mode, opponent team, date range, last N games, league, month, period, player's team, opponent conference/division, season segment, outcome, location, and game segment.
    Returns a JSON string with defensive stats."""
    
    json_response = fetch_player_defense_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        opponent_team_id=opponent_team_id,
        date_from=date_from,
        date_to=date_to,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        period=period,
        team_id=team_id,
        vs_conference=vs_conference,
        vs_division=vs_division,
        season_segment=season_segment,
        outcome=outcome,
        location=location,
        game_segment=game_segment,
        return_dataframe=False
    )
    return json_response

class PlayerHustleStatsInput(BaseModel):
    """Input schema for the Player Hustle Stats tool."""
    season: Optional[str] = Field(
        default="2023-24",
        description="The season in YYYY-YY format. Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default=SeasonTypeAllStar.regular,
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default=PerModeTime.per_game,
        description="Statistical mode ('PerGame', 'Totals', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    player_name: Optional[str] = Field(
        default=None,
        description="Name or ID of the player. Defaults to None (league-wide)."
    )
    team_id: Optional[int] = Field(
        default=None,
        description="Team ID. Defaults to None. If player_name is None and team_id is None, fetches league-wide stats. Use 0 for all teams when player_name is None."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID. Defaults to '00' (NBA)."
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD). Optional."
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD). Optional."
    )
    college: Optional[str] = Field(
        default=None,
        description="College filter. Optional."
    )
    conference: Optional[str] = Field(
        default=None,
        description="Conference filter. Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country filter. Optional."
    )
    division: Optional[str] = Field(
        default=None,
        description="Division filter. Optional."
    )
    draft_pick: Optional[str] = Field(
        default=None,
        description="Draft pick filter. Optional."
    )
    draft_year: Optional[str] = Field(
        default=None,
        description="Draft year filter. Optional."
    )
    height: Optional[str] = Field(
        default=None,
        description="Height filter. Optional."
    )
    location: Optional[str] = Field(
        default=None,
        description="Game location filter ('Home' or 'Road'). Optional."
    )
    month: Optional[int] = Field(
        default=None,
        description="Month number (1-12). Optional."
    )
    opponent_team_id: Optional[int] = Field(
        default=None,
        description="Opponent team ID filter. Optional."
    )
    outcome: Optional[str] = Field(
        default=None,
        description="Game outcome filter ('W' or 'L'). Optional."
    )
    po_round: Optional[str] = Field(
        default=None,
        description="Playoff round filter. Optional."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Player experience filter. Optional."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Player position filter. Optional."
    )
    season_segment: Optional[str] = Field(
        default=None,
        description="Season segment filter (e.g., 'Post All-Star'). Optional."
    )
    vs_conference: Optional[str] = Field(
        default=None,
        description="Conference filter ('East', 'West'). Optional."
    )
    vs_division: Optional[str] = Field(
        default=None,
        description="Division filter. Optional."
    )
    weight: Optional[str] = Field(
        default=None,
        description="Weight filter. Optional."
    )

@tool("get_player_hustle_stats", args_schema=PlayerHustleStatsInput)
def get_player_hustle_stats(
    season: str = "2023-24",
    season_type: str = SeasonTypeAllStar.regular,
    per_mode: str = PerModeTime.per_game,
    player_name: Optional[str] = None,
    team_id: Optional[int] = None,
    league_id: str = "00",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    college: Optional[str] = None,
    conference: Optional[str] = None,
    country: Optional[str] = None,
    division: Optional[str] = None,
    draft_pick: Optional[str] = None,
    draft_year: Optional[str] = None,
    height: Optional[str] = None,
    location: Optional[str] = None,
    month: Optional[int] = None,
    opponent_team_id: Optional[int] = None,
    outcome: Optional[str] = None,
    po_round: Optional[str] = None,
    player_experience: Optional[str] = None,
    player_position: Optional[str] = None,
    season_segment: Optional[str] = None,
    vs_conference: Optional[str] = None,
    vs_division: Optional[str] = None,
    weight: Optional[str] = None
) -> str:
    """Fetches player or team hustle statistics (e.g., screen assists, deflections).
    Can fetch for a specific player, a specific team, or league-wide.
    Allows extensive filtering by season, season type, per mode, player name, team ID, league, date range,
    college, conference, country, division, draft pick/year, height, location, month, opponent team,
    outcome, playoff round, player experience/position, season segment, opponent conference/division, and weight.
    Returns a JSON string with hustle stats."""
    
    json_response = fetch_player_hustle_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_name=player_name,
        team_id=team_id,
        league_id=league_id,
        date_from=date_from,
        date_to=date_to,
        college=college,
        conference=conference,
        country=country,
        division=division,
        draft_pick=draft_pick,
        draft_year=draft_year,
        height=height,
        location=location,
        month=month,
        opponent_team_id=opponent_team_id,
        outcome=outcome,
        po_round=po_round,
        player_experience=player_experience,
        player_position=player_position,
        season_segment=season_segment,
        vs_conference=vs_conference,
        vs_division=vs_division,
        weight=weight,
        return_dataframe=False
    )
    return json_response
class PlayerEstimatedMetricsInput(BaseModel):
    """Input schema for the Player Estimated Metrics tool."""
    season: Optional[str] = Field(
        default="2023-24",
        description="NBA season in 'YYYY-YY' format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID ('00' for NBA, '10' for WNBA, '20' for G-League)."
    )

@tool("get_player_estimated_metrics", args_schema=PlayerEstimatedMetricsInput)
def get_player_estimated_metrics(
    season: str = "2023-24",
    season_type: str = "Regular Season",
    league_id: str = "00"
) -> str:
    """Fetches player estimated metrics (e.g., E_OFF_RATING, E_DEF_RATING, E_NET_RATING) for a given season and season type.
    Returns a JSON-formatted string with estimated metrics."""
    
    json_response = fetch_player_estimated_metrics_data(
        season=season,
        season_type=season_type,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response
class PlayerFantasyProfileInput(BaseModel):
    """Input schema for the Player Fantasy Profile tool."""
    player_id: str = Field(description="The ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type_playoffs: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs'). Defaults to 'Regular Season'."
    )
    measure_type_base: Optional[str] = Field(
        default="Base",
        description="Measure type ('Base'). Defaults to 'Base'."
    )
    per_mode36: Optional[str] = Field(
        default="Totals",
        description="Per mode ('Totals', 'PerGame', 'Per36', 'Per48', 'MinutesPer', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="League ID ('00' for NBA, '10' for WNBA, or empty for all). Defaults to empty."
    )
    pace_adjust_no: Optional[str] = Field(
        default="N",
        description="Flag for pace adjustment ('Y' or 'N'). Defaults to 'N'."
    )
    plus_minus_no: Optional[str] = Field(
        default="N",
        description="Flag for plus-minus stats ('Y' or 'N'). Defaults to 'N'."
    )
    rank_no: Optional[str] = Field(
        default="N",
        description="Flag for ranking ('Y' or 'N'). Defaults to 'N'."
    )

@tool("get_player_fantasy_profile", args_schema=PlayerFantasyProfileInput)
def get_player_fantasy_profile(
    player_id: str,
    season: str = "2023-24",
    season_type_playoffs: str = "Regular Season",
    measure_type_base: str = "Base",
    per_mode36: str = "Totals",
    league_id_nullable: str = "",
    pace_adjust_no: str = "N",
    plus_minus_no: str = "N",
    rank_no: str = "N"
) -> str:
    """Fetches comprehensive player fantasy profile data, including overall, location, last N games, days rest, and vs. opponent splits.
    Allows filtering by player ID, season, season type, measure type, per mode, league, pace adjustment, plus/minus, and ranking.
    Returns a JSON string with player fantasy profile data."""
    
    json_response = fetch_player_fantasy_profile_data(
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type_playoffs,
        measure_type_base=measure_type_base,
        per_mode36=per_mode36,
        league_id_nullable=league_id_nullable,
        pace_adjust_no=pace_adjust_no,
        plus_minus_no=plus_minus_no,
        rank_no=rank_no,
        return_dataframe=False
    )
    return json_response
class PlayerFantasyProfileBarGraphInput(BaseModel):
    """Input schema for the Player Fantasy Profile Bar Graph tool."""
    player_id: str = Field(description="The ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="League ID ('00' for NBA, '10' for WNBA, or empty for all). Defaults to empty."
    )
    season_type_all_star_nullable: Optional[str] = Field(
        default="",
        description="Season type ('Regular Season', 'Playoffs', 'All Star', or empty for all). Defaults to empty."
    )

@tool("get_player_fantasy_profile_bar_graph", args_schema=PlayerFantasyProfileBarGraphInput)
def get_player_fantasy_profile_bar_graph(
    player_id: str,
    season: str = "2023-24",
    league_id_nullable: str = "",
    season_type_all_star_nullable: str = ""
) -> str:
    """Fetches player fantasy profile data optimized for bar graph visualization, including season and recent stats.
    Allows filtering by player ID, season, league, and season type.
    Returns a JSON string with player fantasy profile bar graph data."""
    
    json_response = fetch_player_fantasy_profile_bar_graph_data(
        player_id=player_id,
        season=season,
        league_id_nullable=league_id_nullable,
        season_type_all_star_nullable=season_type_all_star_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerGameLogsInput(BaseModel):
    """Input schema for the Player Game Logs tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: str = Field(description="The NBA season in YYYY-YY format (e.g., '2023-24').")
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="The type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )

@tool("get_player_game_logs", args_schema=PlayerGameLogsInput)
def get_player_game_logs(
    player_name: str,
    season: str,
    season_type: str = "Regular Season"
) -> str:
    """Fetches game-by-game statistics for a specific player, season, and season type.
    Returns a JSON string containing a list of game logs."""
    
    json_response = fetch_player_gamelog_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        return_dataframe=False
    )
    return json_response
class PlayerGameStreakFinderInput(BaseModel):
    """Input schema for the Player Game Streak Finder tool."""
    player_id_nullable: Optional[str] = Field(
        default="",
        description="Player ID. Leave empty for all players."
    )
    season_nullable: Optional[str] = Field(
        default="",
        description="Season in YYYY-YY format (e.g., '2023-24'). Leave empty for all seasons."
    )
    season_type_nullable: Optional[str] = Field(
        default="",
        description="Season type ('Regular Season', 'Playoffs', or empty for all). Defaults to empty."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="League ID ('00' for NBA, '10' for WNBA, or empty for all). Defaults to empty."
    )
    active_streaks_only_nullable: Optional[str] = Field(
        default="",
        description="Filter for active streaks only ('Y' or 'N'). Defaults to empty (all streaks)."
    )
    location_nullable: Optional[str] = Field(
        default="",
        description="Filter by game location ('Home', 'Road', or empty for all). Defaults to empty."
    )
    outcome_nullable: Optional[str] = Field(
        default="",
        description="Filter by game outcome ('W', 'L', or empty for all). Defaults to empty."
    )
    gt_pts_nullable: Optional[str] = Field(
        default="",
        description="Filter for games with points greater than this value. Must be a number or empty. Defaults to empty."
    )

@tool("get_player_game_streak_finder", args_schema=PlayerGameStreakFinderInput)
def get_player_game_streak_finder(
    player_id_nullable: str = "",
    season_nullable: str = "",
    season_type_nullable: str = "",
    league_id_nullable: str = "",
    active_streaks_only_nullable: str = "",
    location_nullable: str = "",
    outcome_nullable: str = "",
    gt_pts_nullable: str = ""
) -> str:
    """Fetches player game streak data, allowing you to find streaks based on various criteria like points, wins, or losses.
    Allows filtering by player ID, season, season type, league, active streaks, location, outcome, and points threshold.
    Returns a JSON string with player game streak finder data."""
    
    json_response = fetch_player_game_streak_finder_data(
        player_id_nullable=player_id_nullable,
        season_nullable=season_nullable,
        season_type_nullable=season_type_nullable,
        league_id_nullable=league_id_nullable,
        active_streaks_only_nullable=active_streaks_only_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        gt_pts_nullable=gt_pts_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerIndexInput(BaseModel):
    """Input schema for the Player Index tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="League ID ('00' for NBA, '10' for WNBA, '20' for G-League). Defaults to '00'."
    )
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )
    active: Optional[str] = Field(
        default=None,
        description="Filter for active players only ('Y' or 'N'). Optional."
    )
    allstar: Optional[str] = Field(
        default=None,
        description="Filter for All-Star players only ('Y' or 'N'). Optional."
    )
    historical: Optional[str] = Field(
        default=None,
        description="Filter for historical players ('Y' or 'N'). Optional."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="Team ID filter. Optional."
    )
    position: Optional[str] = Field(
        default=None,
        description="Position filter ('F', 'C', 'G', 'F-C', 'F-G', 'G-F', 'C-F'). Optional."
    )
    college: Optional[str] = Field(
        default=None,
        description="College filter. Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country filter. Optional."
    )

@tool("get_player_index", args_schema=PlayerIndexInput)
def get_player_index(
    league_id: str = "00",
    season: str = "2023-24",
    active: Optional[str] = None,
    allstar: Optional[str] = None,
    historical: Optional[str] = None,
    team_id: Optional[str] = None,
    position: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None
) -> str:
    """Fetches a comprehensive index of all NBA players, including their details, team info, physical stats, background, and career span.
    Allows extensive filtering by league, season, active status, All-Star status, historical status, team, position, college, and country.
    Returns a JSON string with player index data."""
    
    json_response = fetch_player_index_data(
        league_id=league_id,
        season=season,
        active=active,
        allstar=allstar,
        historical=historical,
        team_id=team_id,
        position=position,
        college=college,
        country=country,
        return_dataframe=False
    )
    return json_response
class PlayerListingsInput(BaseModel):
    """Input schema for the Player Listings tool."""
    season: str = Field(
        description="The NBA season identifier in YYYY-YY format (e.g., '2023-24')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="The league ID ('00' for NBA, '10' for WNBA, '20' for G-League). Defaults to '00'."
    )
    is_only_current_season: Optional[int] = Field(
        default=1,
        description="Flag to filter for only the current season's active players (1) or all players historically associated with that season context (0). Defaults to 1."
    )

@tool("get_player_listings", args_schema=PlayerListingsInput)
def get_player_listings(
    season: str,
    league_id: str = "00",
    is_only_current_season: int = 1
) -> str:
    """Fetches a list of all players for a given league and season, or all players historically if is_only_current_season is set to 0.
    Returns a JSON string containing a list of players."""
    
    json_response = fetch_common_all_players_data(
        season=season,
        league_id=league_id,
        is_only_current_season=is_only_current_season,
        return_dataframe=False
    )
    return json_response
class PlayerPassingStatsInput(BaseModel):
    """Input schema for the Player Passing Stats tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="NBA season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Statistical mode ('Totals', 'PerGame', 'MinutesPer', 'Per36', 'Per48', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of games to include (0 for all games). Defaults to 0."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID ('00' for NBA). Defaults to '00'."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month number (0 for all months). Defaults to 0."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID (0 for all teams). Defaults to 0."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division (e.g., 'Atlantic', 'Central'). Optional."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference (e.g., 'East', 'West'). Optional."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment (e.g., 'Post All-Star', 'Pre All-Star'). Optional."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome (e.g., 'W', 'L'). Optional."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game location (e.g., 'Home', 'Road'). Optional."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in format YYYY-MM-DD. Optional."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in format YYYY-MM-DD. Optional."
    )

@tool("get_player_passing_stats", args_schema=PlayerPassingStatsInput)
def get_player_passing_stats(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None
) -> str:
    """Fetches player passing statistics, including passes made and passes received.
    Allows extensive filtering by player name, season, season type, per mode, last N games, league, month, opponent team,
    division, conference, season segment, outcome, location, and date range.
    Returns a JSON string containing player passing stats."""
    
    json_response = fetch_player_passing_stats_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        opponent_team_id=opponent_team_id,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerReboundingStatsInput(BaseModel):
    """Input schema for the Player Rebounding Stats tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="NBA season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Statistical mode ('Totals', 'PerGame', 'MinutesPer', 'Per36', 'Per48', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of games to include (0 for all games). Defaults to 0."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID ('00' for NBA). Defaults to '00'."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month number (0 for all months). Defaults to 0."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID (0 for all teams). Defaults to 0."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period number (0 for all periods). Defaults to 0."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division (e.g., 'Atlantic', 'Central'). Optional."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference (e.g., 'East', 'West'). Optional."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment (e.g., 'Post All-Star', 'Pre All-Star'). Optional."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome (e.g., 'W', 'L'). Optional."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game location (e.g., 'Home', 'Road'). Optional."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment (e.g., 'First Half', 'Second Half'). Optional."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in format YYYY-MM-DD. Optional."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in format YYYY-MM-DD. Optional."
    )

@tool("get_player_rebounding_stats", args_schema=PlayerReboundingStatsInput)
def get_player_rebounding_stats(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None
) -> str:
    """Fetches player rebounding statistics, categorized by overall, shot type, contest level, shot distance, and rebound distance.
    Allows extensive filtering by player name, season, season type, per mode, last N games, league, month, opponent team, period,
    division, conference, season segment, outcome, location, game segment, and date range.
    Returns a JSON string containing player rebounding stats."""
    
    json_response = fetch_player_rebounding_stats_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        game_segment_nullable=game_segment_nullable,
        date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerShotsTrackingInput(BaseModel):
    """Input schema for the Player Shots Tracking tool."""
    player_name: str = Field(description="The name or ID of the player.")
    season: Optional[str] = Field(
        default="2023-24",
        description="NBA season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Playoffs', 'Pre Season', 'All Star'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Statistical mode ('Totals', 'PerGame', 'MinutesPer', 'Per36', 'Per48', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'Totals'."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID. Defaults to 0 (all)."
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Start date filter (YYYY-MM-DD). Optional."
    )
    date_to: Optional[str] = Field(
        default=None,
        description="End date filter (YYYY-MM-DD). Optional."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of games to include (0 for all games). Defaults to 0."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID ('00' for NBA). Defaults to '00'."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month number (0 for all months). Defaults to 0."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period number (0 for all periods). Defaults to 0."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division (e.g., 'Atlantic', 'Central'). Optional."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference (e.g., 'East', 'West'). Optional."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment (e.g., 'Post All-Star', 'Pre All-Star'). Optional."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome (e.g., 'W', 'L'). Optional."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game location (e.g., 'Home', 'Road'). Optional."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment (e.g., 'First Half', 'Second Half'). Optional."
    )

@tool("get_player_shots_tracking_stats", args_schema=PlayerShotsTrackingInput)
def get_player_shots_tracking_stats(
    player_name: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    opponent_team_id: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    last_n_games: int = 0,
    league_id: str = "00",
    month: int = 0,
    period: int = 0,
    vs_division_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None
) -> str:
    """Fetches player shooting tracking statistics, categorized by general, shot clock, dribbles, touch time, and defender distance.
    Allows extensive filtering by player name, season, season type, per mode, opponent team, date range, last N games, league, month, period,
    division, conference, season segment, outcome, location, and game segment.
    Returns a JSON string containing player shooting tracking stats."""
    
    json_response = fetch_player_shots_tracking_data(
        player_name=player_name,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        opponent_team_id=opponent_team_id,
        date_from=date_from,
        date_to=date_to,
        last_n_games=last_n_games,
        league_id=league_id,
        month=month,
        period=period,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        game_segment_nullable=game_segment_nullable,
        return_dataframe=False
    )
    return json_response
class PlayerVsPlayerStatsInput(BaseModel):
    """Input schema for the Player Vs Player Stats tool."""
    player_id: str = Field(description="The ID of the first player.")
    vs_player_id: str = Field(description="The ID of the second player (comparison player).")
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format. Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season'). Defaults to 'Regular Season'."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays'). Defaults to 'PerGame'."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense'). Defaults to 'Base'."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter. Defaults to 0 (all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (0-12). Defaults to 0 (all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter. Defaults to 0 (all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period filter (0-4). Defaults to 0 (all periods)."
    )
    date_from: Optional[str] = Field(
        default="",
        description="Start date filter (MM/DD/YYYY). Defaults to empty."
    )
    date_to: Optional[str] = Field(
        default="",
        description="End date filter (MM/DD/YYYY). Defaults to empty."
    )
    game_segment: Optional[str] = Field(
        default="",
        description="Game segment filter. Defaults to empty."
    )
    location: Optional[str] = Field(
        default="",
        description="Location filter (Home/Road). Defaults to empty."
    )
    outcome: Optional[str] = Field(
        default="",
        description="Outcome filter (W/L). Defaults to empty."
    )
    season_segment: Optional[str] = Field(
        default="",
        description="Season segment filter. Defaults to empty."
    )
    vs_conference: Optional[str] = Field(
        default="",
        description="Conference filter. Defaults to empty."
    )
    vs_division: Optional[str] = Field(
        default="",
        description="Division filter. Defaults to empty."
    )
    league_id: Optional[str] = Field(
        default="",
        description="League ID filter. Defaults to empty."
    )

@tool("get_player_vs_player_stats", args_schema=PlayerVsPlayerStatsInput)
def get_player_vs_player_stats(
    player_id: str,
    vs_player_id: str,
    season: str = "2023-24",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0,
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    location: str = "",
    outcome: str = "",
    season_segment: str = "",
    vs_conference: str = "",
    vs_division: str = "",
    league_id: str = ""
) -> str:
    """Fetches player vs player comparison statistics, including head-to-head performance, on/off court stats, and shot breakdowns.
    Allows extensive filtering by player IDs, season, season type, per mode, measure type, last N games, month, opponent team, period,
    date range, game segment, location, outcome, season segment, opponent conference/division, and league.
    Returns a JSON string with player vs player stats data."""
    
    json_response = fetch_player_vs_player_stats_data(
        player_id=player_id,
        vs_player_id=vs_player_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        game_segment=game_segment,
        location=location,
        outcome=outcome,
        season_segment=season_segment,
        vs_conference=vs_conference,
        vs_division=vs_division,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response