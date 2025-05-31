from typing import Optional, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Assuming your project structure allows this import path
from backend.api_tools.all_time_leaders_grids import get_all_time_leaders as fetch_all_time_leaders_data
from backend.api_tools.league_dash_pt_defend import fetch_league_dash_pt_defend_logic as fetch_league_dash_pt_defend_data
from backend.api_tools.homepage_leaders import get_homepage_leaders as fetch_homepage_leaders_data
from backend.api_tools.homepage_v2 import get_homepage_v2 as fetch_homepage_v2_data
from backend.api_tools.ist_standings import get_ist_standings as fetch_ist_standings_data
from backend.api_tools.leaders_tiles import get_leaders_tiles as fetch_leaders_tiles_data
from backend.api_tools.assist_leaders import get_assist_leaders as fetch_assist_leaders_data
from backend.api_tools.league_dash_player_bio import fetch_league_player_bio_stats_logic as fetch_league_player_bio_stats_data
from backend.api_tools.league_dash_player_pt_shot import fetch_league_dash_player_pt_shot_logic as fetch_league_player_pt_shot_data
from backend.api_tools.league_dash_player_clutch import fetch_league_player_clutch_stats_logic as fetch_league_player_clutch_stats_data
from backend.api_tools.league_game_log import fetch_league_game_log_logic as fetch_league_game_log_data
from backend.api_tools.league_hustle_stats_team import get_league_hustle_stats_team as fetch_league_hustle_stats_team_data
from backend.api_tools.league_lineups import fetch_league_dash_lineups_logic as fetch_league_lineups_data
from backend.api_tools.league_standings import fetch_league_standings_logic as fetch_league_standings_data
from backend.api_tools.odds_tools import fetch_odds_data_logic as fetch_odds_data
from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic as fetch_league_season_matchups_data
from backend.api_tools.matchup_tools import fetch_matchups_rollup_logic as fetch_matchups_rollup_data
from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic as fetch_league_scoreboard_data
from backend.api_tools.league_lineup_viz import get_league_lineup_viz as fetch_league_lineup_viz_data
from backend.api_tools.league_dash_player_stats import fetch_league_player_stats_logic as fetch_league_player_stats_data
from backend.api_tools.league_dash_player_shot_locations import get_league_dash_player_shot_locations as fetch_player_shot_locations_data
from backend.api_tools.schedule_league_v2_int import get_schedule_league_v2_int as fetch_schedule_league_v2_int_data
from backend.api_tools.shot_chart_league_wide import get_shot_chart_league_wide as fetch_shot_chart_league_wide_data
from backend.api_tools.playoff_picture import get_playoff_picture as fetch_playoff_picture_data

class AllTimeLeadersInput(BaseModel):
    """Input schema for the All-Time NBA Leaders tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Pre Season')."
    )
    topx: Optional[int] = Field(
        default=10,
        description="Number of top players to return (e.g., 5, 10, 25)."
    )

@tool("get_all_time_nba_leaders", args_schema=AllTimeLeadersInput)
def get_all_time_nba_leaders(
    league_id: str = "00",
    per_mode: str = "Totals",
    season_type: str = "Regular Season",
    topx: int = 10
) -> str:
    """Fetches all-time NBA statistical leaders for various categories like points, rebounds, assists, etc. Allows filtering by league, per mode (totals or per game), season type, and the number of top players (TopX)."""
    
    # Call the original function from api_tools
    # We set return_dataframe=False as the LangChain tool should typically return a string (JSON)
    json_response = fetch_all_time_leaders_data(
        league_id=league_id,
        per_mode=per_mode,
        season_type=season_type,
        topx=topx,
        return_dataframe=False  # Important: Ensure the tool returns a string for the LLM
    )
    return json_response

class LeagueTeamClutchInput(BaseModel):
    """Input schema for fetching league-wide team clutch statistics."""
    season: Optional[str] = Field(
        default=None,
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Statistic mode ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    clutch_time: Optional[str] = Field(
        default="Last 5 Minutes",
        description="Clutch time definition ('Last 5 Minutes', 'Last 4 Minutes', 'Last 3 Minutes', 'Last 2 Minutes', 'Last 1 Minute', 'Last 30 Seconds', 'Last 10 Seconds')."
    )
    ahead_behind: Optional[str] = Field(
        default="Ahead or Behind",
        description="Ahead/behind filter ('Ahead or Behind', 'Behind or Tied', 'Ahead or Tied')."
    )
    point_diff: Optional[int] = Field(
        default=5,
        description="Point differential (e.g., 5 for within 5 points)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="Optional: Team ID filter."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Optional: Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Optional: Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Optional: Opponent team ID filter (0 for all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Optional: Period filter (1-4 for quarters, 0 for all periods)."
    )

@tool("get_league_team_clutch_stats", args_schema=LeagueTeamClutchInput)
def get_league_team_clutch_stats(
    season: str = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time: str = "Last 5 Minutes",
    ahead_behind: str = "Ahead or Behind",
    point_diff: int = 5,
    league_id: str = "00",
    team_id: Optional[str] = None,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0
) -> str:
    """Fetches league-wide team statistics in clutch situations.
    This includes performance in close games, statistics in the final minutes,
    and performance when ahead or behind.
    """
    from backend.api_tools.league_dash_team_clutch import fetch_league_team_clutch_stats_logic as fetch_clutch_data
    
    json_response = fetch_clutch_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        clutch_time=clutch_time,
        ahead_behind=ahead_behind,
        point_diff=point_diff,
        league_id=league_id,
        team_id=team_id,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        return_dataframe=False
    )
    return json_response

class LeagueTeamShotLocationsInput(BaseModel):
    """Input schema for fetching league-wide team shot location statistics."""
    season: Optional[str] = Field(
        default=None,
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Statistic mode ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense', 'Defense')."
    )
    distance_range: Optional[str] = Field(
        default="By Zone",
        description="Shot distance range ('By Zone', '5ft Range', '8ft Range')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Optional: Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Optional: Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Optional: Opponent team ID filter (0 for all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Optional: Period filter (1-4 for quarters, 0 for all periods)."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Team ID filter."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Start date filter (YYYY-MM-DD)."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="Optional: End date filter (YYYY-MM-DD)."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Game segment filter (e.g., 'First Half', 'Second Half', 'Overtime')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="Optional: League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Location filter ('Home', 'Road')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Outcome filter ('W', 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Playoff round filter (1-4)."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Season segment filter (e.g., 'Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Shot clock range filter (e.g., '24-22', '22-18', '18-15', '15-7', '7-4', '4-0', 'ShotClockOff')."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Conference filter for opponents ('East', 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Division filter for opponents (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Conference filter for teams ('East', 'West')."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Division filter for teams (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    game_scope_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Game scope filter (e.g., 'Season', 'Playoffs', 'All-Star')."
    )
    player_experience_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Player experience filter (e.g., 'Rookie', 'Sophomore', 'Veteran')."
    )
    player_position_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Player position filter (e.g., 'Guard', 'Forward', 'Center')."
    )
    starter_bench_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Starter/bench filter ('Starter', 'Bench')."
    )

@tool("get_league_team_shot_locations", args_schema=LeagueTeamShotLocationsInput)
def get_league_team_shot_locations(
    season: str = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    distance_range: str = "By Zone",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    period: int = 0,
    team_id_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = "00",
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_scope_nullable: Optional[str] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None
) -> str:
    """Fetches league-wide team shot location statistics.
    This endpoint provides comprehensive shot location statistics for teams,
    including data for Restricted Area, In The Paint (Non-RA), Mid-Range,
    Left Corner 3, Right Corner 3, Above the Break 3, and Backcourt.
    """
    from backend.api_tools.league_dash_team_shot_locations import fetch_league_team_shot_locations_logic as fetch_shot_locations_data
    
    json_response = fetch_shot_locations_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        distance_range=distance_range,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        period=period,
        team_id_nullable=team_id_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        game_segment_nullable=game_segment_nullable,
        league_id_nullable=league_id_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        conference_nullable=conference_nullable,
        division_nullable=division_nullable,
        game_scope_nullable=game_scope_nullable,
        player_experience_nullable=player_experience_nullable,
        player_position_nullable=player_position_nullable,
        starter_bench_nullable=starter_bench_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueDashPtDefendInput(BaseModel):
    """Input schema for the NBA League Player Tracking Defense Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame')."
    )
    defense_category: Optional[str] = Field(
        default="Overall",
        description="Defense category ('Overall', '3 Pointers', '2 Pointers', 'Less Than 6Ft', 'Less Than 10Ft', 'Greater Than 15Ft')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    college_nullable: Optional[str] = Field(
        default=None,
        description="College filter."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for teams (e.g., 'East', 'West')."
    )
    country_nullable: Optional[str] = Field(
        default=None,
        description="Country filter."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in YYYY-MM-DD format."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in YYYY-MM-DD format."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for teams (e.g., 'Atlantic', 'Pacific')."
    )
    draft_pick_nullable: Optional[str] = Field(
        default=None,
        description="Draft pick filter."
    )
    draft_year_nullable: Optional[str] = Field(
        default=None,
        description="Draft year filter."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Game segment filter (e.g., 'First Half', 'Second Half')."
    )
    height_nullable: Optional[str] = Field(
        default=None,
        description="Height filter."
    )
    last_n_games_nullable: Optional[int] = Field(
        default=None,
        description="Last N games filter."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Location filter ('Home' or 'Road')."
    )
    month_nullable: Optional[int] = Field(
        default=None,
        description="Month filter (0-12)."
    )
    opponent_team_id_nullable: Optional[int] = Field(
        default=None,
        description="Opponent team ID filter."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Outcome filter ('W' or 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round filter."
    )
    period_nullable: Optional[int] = Field(
        default=None,
        description="Period filter."
    )
    player_experience_nullable: Optional[str] = Field(
        default=None,
        description="Player experience filter (e.g., 'Rookie', 'Sophomore')."
    )
    player_id_nullable: Optional[str] = Field(
        default=None,
        description="Player ID filter."
    )
    player_position_nullable: Optional[str] = Field(
        default=None,
        description="Player position filter (e.g., 'F', 'C', 'G')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Season segment filter (e.g., 'Pre All-Star', 'Post All-Star')."
    )
    starter_bench_nullable: Optional[str] = Field(
        default=None,
        description="Starter/bench filter (e.g., 'Starters', 'Bench')."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Team ID filter."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for opponents (e.g., 'East', 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for opponents (e.g., 'Atlantic', 'Pacific')."
    )
    weight_nullable: Optional[str] = Field(
        default=None,
        description="Weight filter."
    )

@tool("get_nba_league_player_tracking_defense_stats", args_schema=LeagueDashPtDefendInput)
def get_nba_league_player_tracking_defense_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    defense_category: str = "Overall",
    league_id: str = "00",
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    player_experience_nullable: Optional[str] = None,
    player_id_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None
) -> str:
    """Fetches defensive player tracking statistics across the league, showing how players perform when defending shots in different categories. Includes metrics like defended field goal percentage, normal field goal percentage, and the difference between them (PCT_PLUSMINUS) which indicates defensive impact. Allows extensive filtering."""
    json_response = fetch_league_dash_pt_defend_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        defense_category=defense_category,
        league_id=league_id,
        college_nullable=college_nullable,
        conference_nullable=conference_nullable,
        country_nullable=country_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        draft_pick_nullable=draft_pick_nullable,
        draft_year_nullable=draft_year_nullable,
        game_segment_nullable=game_segment_nullable,
        height_nullable=height_nullable,
        last_n_games_nullable=last_n_games_nullable,
        location_nullable=location_nullable,
        month_nullable=month_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        period_nullable=period_nullable,
        player_experience_nullable=player_experience_nullable,
        player_id_nullable=player_id_nullable,
        player_position_nullable=player_position_nullable,
        season_segment_nullable=season_segment_nullable,
        starter_bench_nullable=starter_bench_nullable,
        team_id_nullable=team_id_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        weight_nullable=weight_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueDashPtStatsInput(BaseModel):
    """Input schema for the NBA League Player Tracking Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    player_or_team: Optional[str] = Field(
        default="Team",
        description="Player or Team filter ('Player' or 'Team')."
    )
    pt_measure_type: Optional[str] = Field(
        default="SpeedDistance",
        description="Player tracking measure type ('SpeedDistance', 'Rebounding', 'Possessions', 'CatchShoot', 'PullUpShot', 'Defense', 'Drives', 'Passing', 'ElbowTouch', 'PostTouch', 'PaintTouch', 'Efficiency')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter (0 for all teams)."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in YYYY-MM-DD format."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in YYYY-MM-DD format."
    )
    game_scope_simple_nullable: Optional[str] = Field(
        default=None,
        description="Game scope filter (e.g., 'Yesterday', 'Last 10')."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Location filter ('Home' or 'Road')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Outcome filter ('W' or 'L')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Season segment filter (e.g., 'Pre All-Star', 'Post All-Star')."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for opponents (e.g., 'East', 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for opponents (e.g., 'Atlantic', 'Pacific')."
    )
    player_experience_nullable: Optional[str] = Field(
        default=None,
        description="Player experience filter (e.g., 'Rookie', 'Sophomore', 'Veteran')."
    )
    player_position_abbreviation_nullable: Optional[str] = Field(
        default=None,
        description="Player position filter (e.g., 'G', 'F', 'C', 'G-F')."
    )
    starter_bench_nullable: Optional[str] = Field(
        default=None,
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Team ID filter."
    )
    college_nullable: Optional[str] = Field(
        default=None,
        description="College filter."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for teams (e.g., 'East', 'West')."
    )
    country_nullable: Optional[str] = Field(
        default=None,
        description="Country filter."
    )
    division_simple_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for teams (e.g., 'Atlantic', 'Pacific')."
    )
    draft_pick_nullable: Optional[str] = Field(
        default=None,
        description="Draft pick filter."
    )
    draft_year_nullable: Optional[str] = Field(
        default=None,
        description="Draft year filter."
    )
    height_nullable: Optional[str] = Field(
        default=None,
        description="Height filter."
    )
    league_id_nullable: Optional[str] = Field(
        default=None,
        description="League ID filter."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round filter."
    )
    weight_nullable: Optional[str] = Field(
        default=None,
        description="Weight filter."
    )

@tool("get_nba_league_player_tracking_stats", args_schema=LeagueDashPtStatsInput)
def get_nba_league_player_tracking_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    player_or_team: str = "Team",
    pt_measure_type: str = "SpeedDistance",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    game_scope_simple_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_abbreviation_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    division_simple_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    league_id_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None
) -> str:
    """Fetches player tracking statistics across the league, including metrics like distance traveled, average speed, and various specialized statistics based on the selected measure type. Allows extensive filtering by season, season type, per mode, player/team, measure type, last N games, month, opponent team, date range, game scope, location, outcome, season segment, opponent conference/division, player experience/position/starter/bench, team, college, conference, country, division, draft pick/year, height, league, playoff round, and weight."""
    json_response = fetch_league_dash_pt_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_or_team=player_or_team,
        pt_measure_type=pt_measure_type,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        game_scope_simple_nullable=game_scope_simple_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        season_segment_nullable=season_segment_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        player_experience_nullable=player_experience_nullable,
        player_position_abbreviation_nullable=player_position_abbreviation_nullable,
        starter_bench_nullable=starter_bench_nullable,
        team_id_nullable=team_id_nullable,
        college_nullable=college_nullable,
        conference_nullable=conference_nullable,
        country_nullable=country_nullable,
        division_simple_nullable=division_simple_nullable,
        draft_pick_nullable=draft_pick_nullable,
        draft_year_nullable=draft_year_nullable,
        height_nullable=height_nullable,
        league_id_nullable=league_id_nullable,
        po_round_nullable=po_round_nullable,
        weight_nullable=weight_nullable,
        return_dataframe=False
    )
    return json_response

class ShotChartLeagueWideInput(BaseModel):
    """Input schema for the League Wide Shot Chart tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )

@tool("get_league_wide_shot_chart", args_schema=ShotChartLeagueWideInput)
def get_league_wide_shot_chart(
    league_id: str = "00",
    season: str = "2024-25"
) -> str:
    """Fetches league-wide shot chart data, providing insights into shooting percentages by zone, area, and range across the entire league. Useful for analyzing league-wide shooting trends and efficiency."""
    
    json_response = fetch_shot_chart_league_wide_data(
        league_id=league_id,
        season=season,
        return_dataframe=False
    )
    return json_response

class HomePageLeadersInput(BaseModel):
    """Input schema for the NBA Homepage Leaders tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type_playoffs: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Playoffs')."
    )
    player_or_team: Optional[str] = Field(
        default="Team",
        description="Specify 'Player' for player leaders or 'Team' for team leaders."
    )
    player_scope: Optional[str] = Field(
        default="All Players",
        description="Player scope ('All Players' or 'Rookies')."
    )
    stat_category: Optional[str] = Field(
        default="Points",
        description="Statistical category ('Points', 'Rebounds', 'Assists')."
    )
    game_scope_detailed: Optional[str] = Field(
        default="Season",
        description="Game scope ('Season' or 'Last 10')."
    )

@tool("get_nba_homepage_leaders", args_schema=HomePageLeadersInput)
def get_nba_homepage_leaders(
    league_id: str = "00",
    season: str = "2024-25",
    season_type_playoffs: str = "Regular Season",
    player_or_team: str = "Team",
    player_scope: str = "All Players",
    stat_category: str = "Points",
    game_scope_detailed: str = "Season"
) -> str:
    """Fetches NBA homepage leaders data, including team leaders, league averages, and league highs. Allows filtering by league, season, season type, player/team scope, statistical category, and game scope."""
    json_response = fetch_homepage_leaders_data(
        league_id=league_id,
        season=season,
        season_type_playoffs=season_type_playoffs,
        player_or_team=player_or_team,
        player_scope=player_scope,
        stat_category=stat_category,
        game_scope_detailed=game_scope_detailed,
        return_dataframe=False
    )
    return json_response

class HomePageV2Input(BaseModel):
    """Input schema for the NBA Homepage V2 tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA)."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type_playoffs: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Playoffs')."
    )
    player_or_team: Optional[str] = Field(
        default="Team",
        description="Specify 'Player' for player leaders or 'Team' for team leaders."
    )
    player_scope: Optional[str] = Field(
        default="All Players",
        description="Player scope ('All Players' or 'Rookies')."
    )
    stat_type: Optional[str] = Field(
        default="Traditional",
        description="Statistical type ('Traditional' or 'Advanced')."
    )
    game_scope_detailed: Optional[str] = Field(
        default="Season",
        description="Game scope ('Season' or 'Last 10')."
    )

@tool("get_nba_homepage_v2_data", args_schema=HomePageV2Input)
def get_nba_homepage_v2_data(
    league_id: str = "00",
    season: str = "2024-25",
    season_type_playoffs: str = "Regular Season",
    player_or_team: str = "Team",
    player_scope: str = "All Players",
    stat_type: str = "Traditional",
    game_scope_detailed: str = "Season"
) -> str:
    """Fetches enhanced NBA homepage data, including category-specific leaders (points, rebounds, assists, etc.). Allows filtering by league, season, season type, player/team scope, statistical type (Traditional/Advanced), and game scope."""
    json_response = fetch_homepage_v2_data(
        league_id=league_id,
        season=season,
        season_type_playoffs=season_type_playoffs,
        player_or_team=player_or_team,
        player_scope=player_scope,
        stat_type=stat_type,
        game_scope_detailed=game_scope_detailed,
        return_dataframe=False
    )
    return json_response

class ISTStandingsInput(BaseModel):
    """Input schema for the NBA In-Season Tournament Standings tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA)."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    section: Optional[str] = Field(
        default="group",
        description="Section type ('group' for group play standings, 'knockout' for knockout stage details)."
    )

@tool("get_nba_ist_standings", args_schema=ISTStandingsInput)
def get_nba_ist_standings(
    league_id: str = "00",
    season: str = "2024-25",
    section: str = "group"
) -> str:
    """Fetches NBA In-Season Tournament standings data, including team info, tournament structure, rankings, record, and game details. Allows filtering by league, season, and section (group/knockout)."""
    json_response = fetch_ist_standings_data(
        league_id=league_id,
        season=season,
        section=section,
        return_dataframe=False
    )
    return json_response

class LeadersTilesInput(BaseModel):
    """Input schema for the NBA Leaders Tiles tool."""
    game_scope_detailed: Optional[str] = Field(
        default="Season",
        description="Game scope ('Season' or 'Last 10')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA)."
    )
    player_or_team: Optional[str] = Field(
        default="Team",
        description="Specify 'Player' for player leaders or 'Team' for team leaders."
    )
    player_scope: Optional[str] = Field(
        default="All Players",
        description="Player scope ('All Players' or 'Rookies')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type_playoffs: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Playoffs')."
    )
    stat: Optional[str] = Field(
        default="PTS",
        description="Statistical category ('PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT')."
    )

@tool("get_nba_leaders_tiles", args_schema=LeadersTilesInput)
def get_nba_leaders_tiles(
    game_scope_detailed: str = "Season",
    league_id: str = "00",
    player_or_team: str = "Team",
    player_scope: str = "All Players",
    season: str = "2024-25",
    season_type_playoffs: str = "Regular Season",
    stat: str = "PTS"
) -> str:
    """Fetches NBA statistical leaders tiles data, including current season leaders, all-time high/low records, and last season leaders. Allows filtering by game scope, league, player/team scope, season, season type, and statistical category."""
    json_response = fetch_leaders_tiles_data(
        game_scope_detailed=game_scope_detailed,
        league_id=league_id,
        player_or_team=player_or_team,
        player_scope=player_scope,
        season=season,
        season_type_playoffs=season_type_playoffs,
        stat=stat,
        return_dataframe=False
    )
    return json_response
    
class AssistLeadersInput(BaseModel):
    """Input schema for the NBA Assist Leaders tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    season: Optional[str] = Field(
        default="2023-24",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    player_or_team: Optional[str] = Field(
        default="Team",
        description="Specify 'Player' for player assist leaders or 'Team' for team assist leaders."
    )

@tool("get_nba_assist_leaders", args_schema=AssistLeadersInput)
def get_nba_assist_leaders(
    league_id: str = "00",
    season: str = "2023-24",
    season_type: str = "Regular Season",
    per_mode: str = "Totals",
    player_or_team: str = "Team"
) -> str:
    """Fetches NBA assist leaders statistics. Allows filtering by league, season, season type, per mode (totals or per game), and whether to retrieve player or team assist leaders."""
    
    json_response = fetch_assist_leaders_data(
        league_id=league_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_or_team=player_or_team,
        return_dataframe=False
    )
    return json_response
 
class LeagueDashPlayerBioStatsInput(BaseModel):
    """Input schema for the NBA League Player Bio Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals' or 'PerGame')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Player position filter ('Forward', 'Center', 'Guard', 'Center-Forward', 'Forward-Center', 'Forward-Guard', 'Guard-Forward')."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default=None,
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    college: Optional[str] = Field(
        default=None,
        description="College filter."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country filter."
    )
    draft_year: Optional[str] = Field(
        default=None,
        description="Draft year filter."
    )
    height: Optional[str] = Field(
        default=None,
        description="Height filter."
    )
    weight: Optional[str] = Field(
        default=None,
        description="Weight filter."
    )

@tool("get_nba_league_player_bio_stats", args_schema=LeagueDashPlayerBioStatsInput)
def get_nba_league_player_bio_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None,
    draft_year: Optional[str] = None,
    height: Optional[str] = None,
    weight: Optional[str] = None
) -> str:
    """Fetches NBA league player biographical statistics, including demographics, college/country info, draft info, and basic/advanced stats. Allows extensive filtering."""
    json_response = fetch_league_player_bio_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        college=college,
        country=country,
        draft_year=draft_year,
        height=height,
        weight=weight,
        return_dataframe=False
    )
    return json_response

class LeagueDashPlayerPtShotInput(BaseModel):
    """Input schema for the NBA League Player Tracking Shot tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    close_def_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by defender distance (e.g., '0-2 Feet', '2-4 Feet', '4-6 Feet', '6+ Feet')."
    )
    college_nullable: Optional[str] = Field(
        default=None,
        description="Filter by college."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference (e.g., 'East', 'West')."
    )
    country_nullable: Optional[str] = Field(
        default=None,
        description="Filter by country."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in 'YYYY-MM-DD' format (e.g., '2023-10-24')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in 'YYYY-MM-DD' format (e.g., '2024-04-14')."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    draft_pick_nullable: Optional[str] = Field(
        default=None,
        description="Filter by draft pick (e.g., '1st Round', '2nd Round', 'Undrafted')."
    )
    draft_year_nullable: Optional[str] = Field(
        default=None,
        description="Filter by draft year."
    )
    dribble_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by dribble range (e.g., '0 Dribbles', '1 Dribble', '2 Dribbles', '3-6 Dribbles', '7+ Dribbles')."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment ('First Half', 'Overtime', 'Second Half')."
    )
    general_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by general range (e.g., 'Less Than 5 FT', '5-9 FT', '10-14 FT', '15-19 FT', '20-24 FT', '25-29 FT', '30-34 FT', '35-39 FT', '40+ FT')."
    )
    height_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player height (e.g., '6-0', '6-5')."
    )
    last_n_games_nullable: Optional[int] = Field(
        default=None,
        description="Filter by last N games."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home' or 'Road')."
    )
    month_nullable: Optional[int] = Field(
        default=None,
        description="Filter by month (1-12)."
    )
    opponent_team_id_nullable: Optional[int] = Field(
        default=None,
        description="Filter by opponent team ID."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome ('W' or 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Filter by playoff round (e.g., '1', '2', '3', '4')."
    )
    period_nullable: Optional[int] = Field(
        default=None,
        description="Filter by period (1-4 for quarters, 5+ for overtime)."
    )
    player_experience_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player experience ('Rookie', 'Sophomore', 'Veteran')."
    )
    player_position_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player position (e.g., 'G', 'F', 'C')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range (e.g., '24-22', '22-18 Very Early', '18-15 Early', '15-7 Average', '7-4 Late', '4-0 Very Late')."
    )
    shot_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot distance range (e.g., '8-16 ft', '16-24 ft', '24+ ft')."
    )
    starter_bench_nullable: Optional[str] = Field(
        default=None,
        description="Filter by starter/bench ('Starters' or 'Bench')."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Filter by team ID."
    )
    touch_time_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by touch time range (e.g., '0-2 Seconds', '2-6 Seconds', '6+ Seconds')."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference ('East' or 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division."
    )
    weight_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player weight."
    )

@tool("get_nba_league_player_tracking_shot_stats", args_schema=LeagueDashPlayerPtShotInput)
def get_nba_league_player_tracking_shot_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    close_def_dist_range_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    dribble_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    general_range_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    touch_time_range_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None
) -> str:
    """Fetches NBA league player shooting statistics, including field goal attempts and percentages, effective field goal percentage, and 2-point/3-point shooting. Allows extensive filtering by various parameters."""
    json_response = fetch_league_player_pt_shot_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        close_def_dist_range_nullable=close_def_dist_range_nullable,
        college_nullable=college_nullable,
        conference_nullable=conference_nullable,
        country_nullable=country_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        draft_pick_nullable=draft_pick_nullable,
        draft_year_nullable=draft_year_nullable,
        dribble_range_nullable=dribble_range_nullable,
        game_segment_nullable=game_segment_nullable,
        general_range_nullable=general_range_nullable,
        height_nullable=height_nullable,
        last_n_games_nullable=last_n_games_nullable,
        location_nullable=location_nullable,
        month_nullable=month_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        period_nullable=period_nullable,
        player_experience_nullable=player_experience_nullable,
        player_position_nullable=player_position_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        shot_dist_range_nullable=shot_dist_range_nullable,
        starter_bench_nullable=starter_bench_nullable,
        team_id_nullable=team_id_nullable,
        touch_time_range_nullable=touch_time_range_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        weight_nullable=weight_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueDashPlayerClutchStatsInput(BaseModel):
    """Input schema for the NBA League Player Clutch Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    clutch_time: Optional[str] = Field(
        default="Last 5 Minutes",
        description="Clutch time definition ('Last 5 Minutes', 'Last 4 Minutes', 'Last 3 Minutes', 'Last 2 Minutes', 'Last 1 Minute', 'Last 30 Seconds', 'Last 10 Seconds')."
    )
    ahead_behind: Optional[str] = Field(
        default="Ahead or Behind",
        description="Ahead/behind filter ('Ahead or Behind', 'Behind or Tied', 'Ahead or Tied')."
    )
    point_diff: Optional[int] = Field(
        default=5,
        description="Point differential (e.g., 5 for +/- 5 points)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Player position filter ('Forward', 'Center', 'Guard', 'Center-Forward', 'Forward-Center', 'Forward-Guard', 'Guard-Forward')."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default=None,
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter (0 for all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period filter (1-4 for quarters, 5+ for overtime, 0 for all periods)."
    )

@tool("get_nba_league_player_clutch_stats", args_schema=LeagueDashPlayerClutchStatsInput)
def get_nba_league_player_clutch_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time: str = "Last 5 Minutes",
    ahead_behind: str = "Ahead or Behind",
    point_diff: int = 5,
    league_id: str = "00",
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0
) -> str:
    """Fetches NBA league player clutch statistics, including performance in close games, final minutes, and when ahead/behind. Allows extensive filtering by season, type, per mode, measure type, clutch time, point differential, league, team, player position/experience, starter/bench, last N games, month, opponent, and period."""
    json_response = fetch_league_player_clutch_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        clutch_time=clutch_time,
        ahead_behind=ahead_behind,
        point_diff=point_diff,
        league_id=league_id,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        return_dataframe=False
    )
    return json_response

class LeagueGameLogInput(BaseModel):
    """Input schema for the NBA League Game Log tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    player_or_team: Optional[str] = Field(
        default="T",
        description="Whether to get player ('P') or team ('T') game logs."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    direction: Optional[str] = Field(
        default="ASC",
        description="Sort direction ('ASC' for ascending, 'DESC' for descending)."
    )
    sorter: Optional[str] = Field(
        default="DATE",
        description="Field to sort by ('DATE', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'PF', 'PLUS_MINUS')."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in YYYY-MM-DD format (e.g., '2023-10-24')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in YYYY-MM-DD format (e.g., '2024-04-14')."
    )

@tool("get_nba_league_game_log", args_schema=LeagueGameLogInput)
def get_nba_league_game_log(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    player_or_team: str = "T",
    league_id: str = "00",
    direction: str = "ASC",
    sorter: str = "DATE",
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """Fetches game logs for the entire league, providing comprehensive game-by-game statistics for all teams or players. Allows filtering by season, season type, player/team, league, sort direction, sort field, and date range."""
    
    json_response = fetch_league_game_log_data(
        season=season,
        season_type=season_type,
        player_or_team=player_or_team,
        league_id=league_id,
        direction=direction,
        sorter=sorter,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueHustleStatsTeamInput(BaseModel):
    """Input schema for the NBA League Hustle Stats Team tool."""
    per_mode_time: Optional[str] = Field(
        default="Totals",
        description="Per mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )

@tool("get_league_hustle_stats_team", args_schema=LeagueHustleStatsTeamInput)
def get_league_hustle_stats_team(
    per_mode_time: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide team hustle statistics, including contested shots, deflections, charges drawn, screen assists, loose balls recovered, and box outs. Allows filtering by per mode, season, season type, and league ID."""
    
    json_response = fetch_league_hustle_stats_team_data(
        per_mode_time=per_mode_time,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueLineupsInput(BaseModel):
    """Input schema for the NBA League Lineups tool."""
    season: str = Field(
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    group_quantity: Optional[int] = Field(
        default=5,
        description="Number of players in the lineup (e.g., 2, 3, 4, 5). Defaults to 5."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Filter by last N games. Defaults to 0 (all games)."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Type of stats ('Base', 'Advanced', 'Misc', etc.). Defaults to 'Base'."
    )
    month: Optional[int] = Field(
        default=0,
        description="Filter by month (1-12). Defaults to 0 (all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID. Defaults to 0 (all opponents)."
    )
    pace_adjust: Optional[str] = Field(
        default="N",
        description="Pace adjust stats ('Y'/'N'). Defaults to 'N'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Stat mode ('Totals', 'PerGame', 'Per100Possessions', etc.). Defaults to 'Totals'."
    )
    period: Optional[int] = Field(
        default=0,
        description="Filter by period (1-4 for quarters, 0 for full game). Defaults to 0."
    )
    plus_minus: Optional[str] = Field(
        default="N",
        description="Include plus/minus ('Y'/'N'). Defaults to 'N'."
    )
    rank: Optional[str] = Field(
        default="N",
        description="Include rank ('Y'/'N'). Defaults to 'N'."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Playoffs', etc.). Defaults to 'Regular Season'."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference ('East', 'West')."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD)."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD)."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment ('First Half', 'Second Half', 'Overtime')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="League ID (e.g., '00' for NBA)."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home', 'Road')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by outcome ('W', 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round (e.g., '1', '2')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range."
    )
    team_id_nullable: Optional[int] = Field(
        default=None,
        description="Filter by a specific team ID."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division."
    )

@tool("get_nba_league_lineups", args_schema=LeagueLineupsInput)
def get_nba_league_lineups(
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
    league_id_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None
) -> str:
    """Fetches league-wide lineup statistics with extensive filtering options, including performance metrics, shooting efficiency, and opponent stats. Allows filtering by season, group quantity, last N games, measure type, month, opponent team, pace adjustment, per mode, period, plus/minus, rank, season type, conference, date range, division, game segment, league, location, outcome, playoff round, season segment, shot clock range, team, and opponent conference/division."""
    
    json_response = fetch_league_lineups_data(
        season=season,
        group_quantity=group_quantity,
        last_n_games=last_n_games,
        measure_type=measure_type,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        per_mode=per_mode,
        period=period,
        plus_minus=plus_minus,
        rank=rank,
        season_type=season_type,
        conference_nullable=conference_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        game_segment_nullable=game_segment_nullable,
        league_id_nullable=league_id_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        team_id_nullable=team_id_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueStandingsInput(BaseModel):
    """Input schema for the NBA League Standings tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Preseason'). Defaults to 'Regular Season'."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (e.g., '00' for NBA, '10' for WNBA). Defaults to NBA."
    )

@tool("get_nba_league_standings", args_schema=LeagueStandingsInput)
def get_nba_league_standings(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    league_id: str = "00"
) -> str:
    """Fetches and processes league standings for a specific season, type, and league. Provides team records, conference/division ranks, and various performance metrics."""
    
    json_response = fetch_league_standings_data(
        season=season,
        season_type=season_type,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

class OddsDataInput(BaseModel):
    """Input schema for the NBA Odds Data tool."""
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_odds_data", args_schema=OddsDataInput)
def get_nba_odds_data(
    bypass_cache: bool = False
) -> str:
    """Fetches live betting odds for today's NBA games, including various markets from different bookmakers. Can optionally bypass cache to get the latest data."""
    
    json_response = fetch_odds_data(
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

class LeagueSeasonMatchupsInput(BaseModel):
    """Input schema for the NBA League Season Matchups tool."""
    def_player_identifier: str = Field(
        description="Name or ID of the defensive player."
    )
    off_player_identifier: str = Field(
        description="Name or ID of the offensive player."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Preseason', 'Playoffs'). Defaults to 'Regular Season'."
    )
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_league_season_matchups", args_schema=LeagueSeasonMatchupsInput)
def get_nba_league_season_matchups(
    def_player_identifier: str,
    off_player_identifier: str,
    season: str = "2024-25",
    season_type: str = "Regular Season",
    bypass_cache: bool = False
) -> str:
    """Fetches season matchup statistics between two specific players, including their head-to-head performance. Allows filtering by defensive player, offensive player, season, season type, and cache bypass."""
    
    json_response = fetch_league_season_matchups_data(
        def_player_identifier=def_player_identifier,
        off_player_identifier=off_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

class MatchupsRollupInput(BaseModel):
    """Input schema for the NBA Matchups Rollup tool."""
    def_player_identifier: str = Field(
        description="Name or ID of the defensive player."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Preseason', 'Playoffs'). Defaults to 'Regular Season'."
    )
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_matchups_rollup", args_schema=MatchupsRollupInput)
def get_nba_matchups_rollup(
    def_player_identifier: str,
    season: str = "2024-25",
    season_type: str = "Regular Season",
    bypass_cache: bool = False
) -> str:
    """Fetches matchup rollup statistics for a defensive player, showing how they perform against all offensive players they guard. Allows filtering by defensive player, season, season type, and cache bypass."""
    
    json_response = fetch_matchups_rollup_data(
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

class LiveScoreboardInput(BaseModel):
    """Input schema for the NBA Live Scoreboard tool."""
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_live_scoreboard", args_schema=LiveScoreboardInput)
def get_nba_live_scoreboard(
    bypass_cache: bool = False
) -> str:
    """Fetches and formats live scoreboard data for current NBA games, including game status, scores, and team information. Can optionally bypass cache to get the latest data."""
    
    json_response = fetch_league_scoreboard_data(
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

class LeagueLineupVizInput(BaseModel):
    """Input schema for the NBA League Lineup Visualization tool."""
    minutes_min: Optional[int] = Field(
        default=5,
        description="Minimum minutes played by the lineup (e.g., 5, 10, 20)."
    )
    group_quantity: Optional[int] = Field(
        default=5,
        description="Number of players in the lineup (2, 3, 4, or 5)."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of last games to consider (e.g., 5, 10, 20). Set to 0 for all games."
    )
    measure_type_detailed_defense: Optional[str] = Field(
        default="Base",
        description="Measure type ('Base')."
    )
    per_mode_detailed: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )

@tool("get_league_lineup_visualization", args_schema=LeagueLineupVizInput)
def get_league_lineup_visualization(
    minutes_min: int = 5,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type_detailed_defense: str = "Base",
    per_mode_detailed: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide lineup visualization data, including performance ratings, shooting efficiency, scoring breakdown, and opponent stats for various lineup combinations. Allows filtering by minimum minutes, group quantity, last N games, measure type, per mode, season, season type, and league ID."""
    
    json_response = fetch_league_lineup_viz_data(
        minutes_min=minutes_min,
        group_quantity=group_quantity,
        last_n_games=last_n_games,
        measure_type_detailed_defense=measure_type_detailed_defense,
        per_mode_detailed=per_mode_detailed,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

class LeagueDashPlayerStatsInput(BaseModel):
    """Input schema for the NBA League Player Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    team_id: Optional[str] = Field(
        default="",
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default="",
        description="Player position filter ('F', 'C', 'G', 'C-F', 'F-C', 'F-G', 'G-F')."
    )
    player_experience: Optional[str] = Field(
        default="",
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default="",
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    date_from: Optional[str] = Field(
        default="",
        description="Start date filter in 'MM/DD/YYYY' format (e.g., '10/24/2023')."
    )
    date_to: Optional[str] = Field(
        default="",
        description="End date filter in 'MM/DD/YYYY' format (e.g., '04/14/2024')."
    )
    game_segment: Optional[str] = Field(
        default="",
        description="Game segment filter ('First Half', 'Second Half', 'Overtime')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter (0 for all games)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    location: Optional[str] = Field(
        default="",
        description="Location filter ('Home' or 'Road')."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter (0 for all teams)."
    )
    outcome: Optional[str] = Field(
        default="",
        description="Outcome filter ('W' or 'L')."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period filter (1-4 for quarters, 5+ for overtime, 0 for all periods)."
    )
    season_segment: Optional[str] = Field(
        default="",
        description="Season segment filter ('Pre All-Star', 'Post All-Star')."
    )
    vs_conference: Optional[str] = Field(
        default="",
        description="Conference filter ('East' or 'West')."
    )
    vs_division: Optional[str] = Field(
        default="",
        description="Division filter (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )

@tool("get_nba_league_player_stats", args_schema=LeagueDashPlayerStatsInput)
def get_nba_league_player_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    team_id: str = "",
    player_position: str = "",
    player_experience: str = "",
    starter_bench: str = "",
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    last_n_games: int = 0,
    league_id: str = "00",
    location: str = "",
    month: int = 0,
    opponent_team_id: int = 0,
    outcome: str = "",
    period: int = 0,
    season_segment: str = "",
    vs_conference: str = "",
    vs_division: str = ""
) -> str:
    """Fetches comprehensive player statistics across the league, including basic and advanced stats, scoring and defensive metrics, and player rankings. Allows extensive filtering by season, season type, per mode, measure type, team, player position, experience, starter/bench status, date range, game segment, last N games, league, location, month, opponent, outcome, period, season segment, and opponent conference/division."""
    
    json_response = fetch_league_player_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        date_from=date_from,
        date_to=date_to,
        game_segment=game_segment,
        last_n_games=last_n_games,
        league_id=league_id,
        location=location,
        month=month,
        opponent_team_id=opponent_team_id,
        outcome=outcome,
        period=period,
        season_segment=season_segment,
        vs_conference=vs_conference,
        vs_division=vs_division,
        return_dataframe=False
    )
    return json_response

class LeagueDashPlayerShotLocationsInput(BaseModel):
    """Input schema for the League Dash Player Shot Locations tool."""
    distance_range: Optional[str] = Field(
        default="By Zone",
        description="Distance range ('5ft Range', '8ft Range', 'By Zone')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of last games to consider (e.g., 5, 10, 20). Set to 0 for all games."
    )
    measure_type_simple: Optional[str] = Field(
        default="Base",
        description="Measure type ('Base')."
    )
    per_mode_detailed: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Pre Season', 'Playoffs', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )
    
@tool("get_league_player_shot_locations", args_schema=LeagueDashPlayerShotLocationsInput)
def get_league_player_shot_locations(
    distance_range: str = "By Zone",
    last_n_games: int = 0,
    measure_type_simple: str = "Base",
    per_mode_detailed: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide player shot locations data, including shooting percentages by various court zones and distances. Allows filtering by distance range, number of last games, measure type, per mode, season, season type, and league ID."""
    
    json_response = fetch_player_shot_locations_data(
        distance_range=distance_range,
        last_n_games=last_n_games,
        measure_type_simple=measure_type_simple,
        per_mode_detailed=per_mode_detailed,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

class ScheduleLeagueV2IntInput(BaseModel):
    """Input schema for the NBA Schedule League V2 International tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )

@tool("get_nba_schedule_league_v2_int", args_schema=ScheduleLeagueV2IntInput)
def get_nba_schedule_league_v2_int(
    league_id: str = "00",
    season: str = "2024-25"
) -> str:
    """Fetches comprehensive league schedule data, including games, weeks, and broadcaster information. Allows filtering by league and season."""
    
    json_response = fetch_schedule_league_v2_int_data(
        league_id=league_id,
        season=season,
        return_dataframe=False
    )
    return json_response

class ShotChartLeagueWideInput(BaseModel):
    """Input schema for the NBA League Wide Shot Chart tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current season."
    )

@tool("get_nba_league_wide_shot_chart", args_schema=ShotChartLeagueWideInput)
def get_nba_league_wide_shot_chart(
    league_id: str = "00",
    season: str = "2024-25"
) -> str:
    """Fetches league-wide shot chart data, including shooting percentages by various court zones and distances. Allows filtering by league and season."""
    
    json_response = fetch_shot_chart_league_wide_data(
        league_id=league_id,
        season=season,
        return_dataframe=False
    )
    return json_response

class PlayoffPictureInput(BaseModel):
    """Input schema for the NBA Playoff Picture tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season_id: Optional[str] = Field(
        default="22024",
        description="Season ID (e.g., '22024' for 2024-25 season). Defaults to current season."
    )

@tool("get_nba_playoff_picture", args_schema=PlayoffPictureInput)
def get_nba_playoff_picture(
    league_id: str = "00",
    season_id: str = "22024"
) -> str:
    """Fetches comprehensive playoff picture data, including series data, standings, and remaining games for both conferences. Allows filtering by league and season ID."""
    
    json_response = fetch_playoff_picture_data(
        league_id=league_id,
        season_id=season_id,
        return_dataframe=False
    )
    return json_response

    json_response = fetch_assist_leaders_data(
        league_id=league_id,
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        player_or_team=player_or_team,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_dash_player_bio import fetch_league_player_bio_stats_logic as fetch_league_player_bio_stats_data

class LeagueDashPlayerBioStatsInput(BaseModel):
    """Input schema for the NBA League Player Bio Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals' or 'PerGame')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Player position filter ('Forward', 'Center', 'Guard', 'Center-Forward', 'Forward-Center', 'Forward-Guard', 'Guard-Forward')."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default=None,
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    college: Optional[str] = Field(
        default=None,
        description="College filter."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country filter."
    )
    draft_year: Optional[str] = Field(
        default=None,
        description="Draft year filter."
    )
    height: Optional[str] = Field(
        default=None,
        description="Height filter."
    )
    weight: Optional[str] = Field(
        default=None,
        description="Weight filter."
    )

@tool("get_nba_league_player_bio_stats", args_schema=LeagueDashPlayerBioStatsInput)
def get_nba_league_player_bio_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    college: Optional[str] = None,
    country: Optional[str] = None,
    draft_year: Optional[str] = None,
    height: Optional[str] = None,
    weight: Optional[str] = None
) -> str:
    """Fetches NBA league player biographical statistics, including demographics, college/country info, draft info, and basic/advanced stats. Allows extensive filtering."""
    json_response = fetch_league_player_bio_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        college=college,
        country=country,
        draft_year=draft_year,
        height=height,
        weight=weight,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_dash_player_pt_shot import fetch_league_dash_player_pt_shot_logic as fetch_league_player_pt_shot_data

class LeagueDashPlayerPtShotInput(BaseModel):
    """Input schema for the NBA League Player Tracking Shot tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    close_def_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by defender distance (e.g., '0-2 Feet', '2-4 Feet', '4-6 Feet', '6+ Feet')."
    )
    college_nullable: Optional[str] = Field(
        default=None,
        description="Filter by college."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference (e.g., 'East', 'West')."
    )
    country_nullable: Optional[str] = Field(
        default=None,
        description="Filter by country."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in 'YYYY-MM-DD' format (e.g., '2023-10-24')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in 'YYYY-MM-DD' format (e.g., '2024-04-14')."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    draft_pick_nullable: Optional[str] = Field(
        default=None,
        description="Filter by draft pick (e.g., '1st Round', '2nd Round', 'Undrafted')."
    )
    draft_year_nullable: Optional[str] = Field(
        default=None,
        description="Filter by draft year."
    )
    dribble_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by dribble range (e.g., '0 Dribbles', '1 Dribble', '2 Dribbles', '3-6 Dribbles', '7+ Dribbles')."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment ('First Half', 'Overtime', 'Second Half')."
    )
    general_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by general range (e.g., 'Less Than 5 FT', '5-9 FT', '10-14 FT', '15-19 FT', '20-24 FT', '25-29 FT', '30-34 FT', '35-39 FT', '40+ FT')."
    )
    height_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player height (e.g., '6-0', '6-5')."
    )
    last_n_games_nullable: Optional[int] = Field(
        default=None,
        description="Filter by last N games."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home' or 'Road')."
    )
    month_nullable: Optional[int] = Field(
        default=None,
        description="Filter by month (1-12)."
    )
    opponent_team_id_nullable: Optional[int] = Field(
        default=None,
        description="Filter by opponent team ID."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game outcome ('W' or 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Filter by playoff round (e.g., '1', '2', '3', '4')."
    )
    period_nullable: Optional[int] = Field(
        default=None,
        description="Filter by period (1-4 for quarters, 5+ for overtime)."
    )
    player_experience_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player experience ('Rookie', 'Sophomore', 'Veteran')."
    )
    player_position_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player position (e.g., 'G', 'F', 'C')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range (e.g., '24-22', '22-18 Very Early', '18-15 Early', '15-7 Average', '7-4 Late', '4-0 Very Late')."
    )
    shot_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot distance range (e.g., '8-16 ft', '16-24 ft', '24+ ft')."
    )
    starter_bench_nullable: Optional[str] = Field(
        default=None,
        description="Filter by starter/bench ('Starters' or 'Bench')."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Filter by team ID."
    )
    touch_time_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by touch time range (e.g., '0-2 Seconds', '2-6 Seconds', '6+ Seconds')."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference ('East' or 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division."
    )
    weight_nullable: Optional[str] = Field(
        default=None,
        description="Filter by player weight."
    )

@tool("get_nba_league_player_tracking_shot_stats", args_schema=LeagueDashPlayerPtShotInput)
def get_nba_league_player_tracking_shot_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    close_def_dist_range_nullable: Optional[str] = None,
    college_nullable: Optional[str] = None,
    conference_nullable: Optional[str] = None,
    country_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    draft_pick_nullable: Optional[str] = None,
    draft_year_nullable: Optional[str] = None,
    dribble_range_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    general_range_nullable: Optional[str] = None,
    height_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    player_experience_nullable: Optional[str] = None,
    player_position_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    starter_bench_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    touch_time_range_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    weight_nullable: Optional[str] = None
) -> str:
    """Fetches NBA league player shooting statistics, including field goal attempts and percentages, effective field goal percentage, and 2-point/3-point shooting. Allows extensive filtering by various parameters."""
    json_response = fetch_league_player_pt_shot_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        close_def_dist_range_nullable=close_def_dist_range_nullable,
        college_nullable=college_nullable,
        conference_nullable=conference_nullable,
        country_nullable=country_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        draft_pick_nullable=draft_pick_nullable,
        draft_year_nullable=draft_year_nullable,
        dribble_range_nullable=dribble_range_nullable,
        game_segment_nullable=game_segment_nullable,
        general_range_nullable=general_range_nullable,
        height_nullable=height_nullable,
        last_n_games_nullable=last_n_games_nullable,
        location_nullable=location_nullable,
        month_nullable=month_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        period_nullable=period_nullable,
        player_experience_nullable=player_experience_nullable,
        player_position_nullable=player_position_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        shot_dist_range_nullable=shot_dist_range_nullable,
        starter_bench_nullable=starter_bench_nullable,
        team_id_nullable=team_id_nullable,
        touch_time_range_nullable=touch_time_range_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        weight_nullable=weight_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_dash_player_clutch import fetch_league_player_clutch_stats_logic as fetch_league_player_clutch_stats_data

class LeagueDashPlayerClutchStatsInput(BaseModel):
    """Input schema for the NBA League Player Clutch Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    clutch_time: Optional[str] = Field(
        default="Last 5 Minutes",
        description="Clutch time definition ('Last 5 Minutes', 'Last 4 Minutes', 'Last 3 Minutes', 'Last 2 Minutes', 'Last 1 Minute', 'Last 30 Seconds', 'Last 10 Seconds')."
    )
    ahead_behind: Optional[str] = Field(
        default="Ahead or Behind",
        description="Ahead/behind filter ('Ahead or Behind', 'Behind or Tied', 'Ahead or Tied')."
    )
    point_diff: Optional[int] = Field(
        default=5,
        description="Point differential (e.g., 5 for +/- 5 points)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Player position filter ('Forward', 'Center', 'Guard', 'Center-Forward', 'Forward-Center', 'Forward-Guard', 'Guard-Forward')."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default=None,
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter (0 for all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period filter (1-4 for quarters, 5+ for overtime, 0 for all periods)."
    )

@tool("get_nba_league_player_clutch_stats", args_schema=LeagueDashPlayerClutchStatsInput)
def get_nba_league_player_clutch_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    clutch_time: str = "Last 5 Minutes",
    ahead_behind: str = "Ahead or Behind",
    point_diff: int = 5,
    league_id: str = "00",
    team_id: Optional[str] = None,
    player_position: Optional[str] = None,
    player_experience: Optional[str] = None,
    starter_bench: Optional[str] = None,
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    period: int = 0
) -> str:
    """Fetches NBA league player clutch statistics, including performance in close games, final minutes, and when ahead/behind. Allows extensive filtering by season, type, per mode, measure type, clutch time, point differential, league, team, player position/experience, starter/bench, last N games, month, opponent, and period."""
    json_response = fetch_league_player_clutch_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        clutch_time=clutch_time,
        ahead_behind=ahead_behind,
        point_diff=point_diff,
        league_id=league_id,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        period=period,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_game_log import fetch_league_game_log_logic as fetch_league_game_log_data

class LeagueGameLogInput(BaseModel):
    """Input schema for the NBA League Game Log tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    player_or_team: Optional[str] = Field(
        default="T",
        description="Whether to get player ('P') or team ('T') game logs."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    direction: Optional[str] = Field(
        default="ASC",
        description="Sort direction ('ASC' for ascending, 'DESC' for descending)."
    )
    sorter: Optional[str] = Field(
        default="DATE",
        description="Field to sort by ('DATE', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'PF', 'PLUS_MINUS')."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in YYYY-MM-DD format (e.g., '2023-10-24')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in YYYY-MM-DD format (e.g., '2024-04-14')."
    )

@tool("get_nba_league_game_log", args_schema=LeagueGameLogInput)
def get_nba_league_game_log(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    player_or_team: str = "T",
    league_id: str = "00",
    direction: str = "ASC",
    sorter: str = "DATE",
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None
) -> str:
    """Fetches game logs for the entire league, providing comprehensive game-by-game statistics for all teams or players. Allows filtering by season, season type, player/team, league, sort direction, sort field, and date range."""
    
    json_response = fetch_league_game_log_data(
        season=season,
        season_type=season_type,
        player_or_team=player_or_team,
        league_id=league_id,
        direction=direction,
        sorter=sorter,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_hustle_stats_team import get_league_hustle_stats_team as fetch_league_hustle_stats_team_data

class LeagueHustleStatsTeamInput(BaseModel):
    """Input schema for the NBA League Hustle Stats Team tool."""
    per_mode_time: Optional[str] = Field(
        default="Totals",
        description="Per mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )

@tool("get_league_hustle_stats_team", args_schema=LeagueHustleStatsTeamInput)
def get_league_hustle_stats_team(
    per_mode_time: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide team hustle statistics, including contested shots, deflections, charges drawn, screen assists, loose balls recovered, and box outs. Allows filtering by per mode, season, season type, and league ID."""
    
    json_response = fetch_league_hustle_stats_team_data(
        per_mode_time=per_mode_time,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_lineups import fetch_league_dash_lineups_logic as fetch_league_lineups_data

class LeagueLineupsInput(BaseModel):
    """Input schema for the NBA League Lineups tool."""
    season: str = Field(
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    group_quantity: Optional[int] = Field(
        default=5,
        description="Number of players in the lineup (e.g., 2, 3, 4, 5). Defaults to 5."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Filter by last N games. Defaults to 0 (all games)."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Type of stats ('Base', 'Advanced', 'Misc', etc.). Defaults to 'Base'."
    )
    month: Optional[int] = Field(
        default=0,
        description="Filter by month (1-12). Defaults to 0 (all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID. Defaults to 0 (all opponents)."
    )
    pace_adjust: Optional[str] = Field(
        default="N",
        description="Pace adjust stats ('Y'/'N'). Defaults to 'N'."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Stat mode ('Totals', 'PerGame', 'Per100Possessions', etc.). Defaults to 'Totals'."
    )
    period: Optional[int] = Field(
        default=0,
        description="Filter by period (1-4 for quarters, 0 for full game). Defaults to 0."
    )
    plus_minus: Optional[str] = Field(
        default="N",
        description="Include plus/minus ('Y'/'N'). Defaults to 'N'."
    )
    rank: Optional[str] = Field(
        default="N",
        description="Include rank ('Y'/'N'). Defaults to 'N'."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Playoffs', etc.). Defaults to 'Regular Season'."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by conference ('East', 'West')."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD)."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD)."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by division."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment ('First Half', 'Second Half', 'Overtime')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="League ID (e.g., '00' for NBA)."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home', 'Road')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by outcome ('W', 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round (e.g., '1', '2')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range."
    )
    team_id_nullable: Optional[int] = Field(
        default=None,
        description="Filter by a specific team ID."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division."
    )

@tool("get_nba_league_lineups", args_schema=LeagueLineupsInput)
def get_nba_league_lineups(
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
    league_id_nullable: Optional[str] = None,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None
) -> str:
    """Fetches league-wide lineup statistics with extensive filtering options, including performance metrics, shooting efficiency, and opponent stats. Allows filtering by season, group quantity, last N games, measure type, month, opponent team, pace adjustment, per mode, period, plus/minus, rank, season type, conference, date range, division, game segment, league, location, outcome, playoff round, season segment, shot clock range, team, and opponent conference/division."""
    
    json_response = fetch_league_lineups_data(
        season=season,
        group_quantity=group_quantity,
        last_n_games=last_n_games,
        measure_type=measure_type,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        per_mode=per_mode,
        period=period,
        plus_minus=plus_minus,
        rank=rank,
        season_type=season_type,
        conference_nullable=conference_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        game_segment_nullable=game_segment_nullable,
        league_id_nullable=league_id_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        team_id_nullable=team_id_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_standings import fetch_league_standings_logic as fetch_league_standings_data

class LeagueStandingsInput(BaseModel):
    """Input schema for the NBA League Standings tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season' or 'Preseason'). Defaults to 'Regular Season'."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (e.g., '00' for NBA, '10' for WNBA). Defaults to NBA."
    )

@tool("get_nba_league_standings", args_schema=LeagueStandingsInput)
def get_nba_league_standings(
    season: Optional[str] = None,
    season_type: str = "Regular Season",
    league_id: str = "00"
) -> str:
    """Fetches and processes league standings for a specific season, type, and league. Provides team records, conference/division ranks, and various performance metrics."""
    
    json_response = fetch_league_standings_data(
        season=season,
        season_type=season_type,
        league_id=league_id,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.odds_tools import fetch_odds_data_logic as fetch_odds_data

class OddsDataInput(BaseModel):
    """Input schema for the NBA Odds Data tool."""
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_odds_data", args_schema=OddsDataInput)
def get_nba_odds_data(
    bypass_cache: bool = False
) -> str:
    """Fetches live betting odds for today's NBA games, including various markets from different bookmakers. Can optionally bypass cache to get the latest data."""
    
    json_response = fetch_odds_data(
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.matchup_tools import fetch_league_season_matchups_logic as fetch_league_season_matchups_data
from backend.api_tools.matchup_tools import fetch_matchups_rollup_logic as fetch_matchups_rollup_data

class LeagueSeasonMatchupsInput(BaseModel):
    """Input schema for the NBA League Season Matchups tool."""
    def_player_identifier: str = Field(
        description="Name or ID of the defensive player."
    )
    off_player_identifier: str = Field(
        description="Name or ID of the offensive player."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Preseason', 'Playoffs'). Defaults to 'Regular Season'."
    )
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_league_season_matchups", args_schema=LeagueSeasonMatchupsInput)
def get_nba_league_season_matchups(
    def_player_identifier: str,
    off_player_identifier: str,
    season: str = "2024-25",
    season_type: str = "Regular Season",
    bypass_cache: bool = False
) -> str:
    """Fetches season matchup statistics between two specific players, including their head-to-head performance. Allows filtering by defensive player, offensive player, season, season type, and cache bypass."""
    
    json_response = fetch_league_season_matchups_data(
        def_player_identifier=def_player_identifier,
        off_player_identifier=off_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

class MatchupsRollupInput(BaseModel):
    """Input schema for the NBA Matchups Rollup tool."""
    def_player_identifier: str = Field(
        description="Name or ID of the defensive player."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="NBA season in YYYY-YY format (e.g., '2023-24'). Defaults to current."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Type of season ('Regular Season', 'Preseason', 'Playoffs'). Defaults to 'Regular Season'."
    )
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_matchups_rollup", args_schema=MatchupsRollupInput)
def get_nba_matchups_rollup(
    def_player_identifier: str,
    season: str = "2024-25",
    season_type: str = "Regular Season",
    bypass_cache: bool = False
) -> str:
    """Fetches matchup rollup statistics for a defensive player, showing how they perform against all offensive players they guard. Allows filtering by defensive player, season, season type, and cache bypass."""
    
    json_response = fetch_matchups_rollup_data(
        def_player_identifier=def_player_identifier,
        season=season,
        season_type=season_type,
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.live_game_tools import fetch_league_scoreboard_logic as fetch_league_scoreboard_data

class LiveScoreboardInput(BaseModel):
    """Input schema for the NBA Live Scoreboard tool."""
    bypass_cache: Optional[bool] = Field(
        default=False,
        description="If True, ignores cached data and fetches fresh data. Defaults to False."
    )

@tool("get_nba_live_scoreboard", args_schema=LiveScoreboardInput)
def get_nba_live_scoreboard(
    bypass_cache: bool = False
) -> str:
    """Fetches and formats live scoreboard data for current NBA games, including game status, scores, and team information. Can optionally bypass cache to get the latest data."""
    
    json_response = fetch_league_scoreboard_data(
        bypass_cache=bypass_cache,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_lineup_viz import get_league_lineup_viz as fetch_league_lineup_viz_data

class LeagueLineupVizInput(BaseModel):
    """Input schema for the NBA League Lineup Visualization tool."""
    minutes_min: Optional[int] = Field(
        default=5,
        description="Minimum minutes played by the lineup (e.g., 5, 10, 20)."
    )
    group_quantity: Optional[int] = Field(
        default=5,
        description="Number of players in the lineup (2, 3, 4, or 5)."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of last games to consider (e.g., 5, 10, 20). Set to 0 for all games."
    )
    measure_type_detailed_defense: Optional[str] = Field(
        default="Base",
        description="Measure type ('Base')."
    )
    per_mode_detailed: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )

@tool("get_league_lineup_visualization", args_schema=LeagueLineupVizInput)
def get_league_lineup_visualization(
    minutes_min: int = 5,
    group_quantity: int = 5,
    last_n_games: int = 0,
    measure_type_detailed_defense: str = "Base",
    per_mode_detailed: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide lineup visualization data, including performance ratings, shooting efficiency, scoring breakdown, and opponent stats for various lineup combinations. Allows filtering by minimum minutes, group quantity, last N games, measure type, per mode, season, season type, and league ID."""
    
    json_response = fetch_league_lineup_viz_data(
        minutes_min=minutes_min,
        group_quantity=group_quantity,
        last_n_games=last_n_games,
        measure_type_detailed_defense=measure_type_detailed_defense,
        per_mode_detailed=per_mode_detailed,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.league_dash_player_stats import fetch_league_player_stats_logic as fetch_league_player_stats_data

class LeagueDashPlayerStatsInput(BaseModel):
    """Input schema for the NBA League Player Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2024-25')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    team_id: Optional[str] = Field(
        default="",
        description="NBA API team ID filter."
    )
    player_position: Optional[str] = Field(
        default="",
        description="Player position filter ('F', 'C', 'G', 'C-F', 'F-C', 'F-G', 'G-F')."
    )
    player_experience: Optional[str] = Field(
        default="",
        description="Player experience filter ('Rookie', 'Sophomore', 'Veteran')."
    )
    starter_bench: Optional[str] = Field(
        default="",
        description="Starter/bench filter ('Starters' or 'Bench')."
    )
    date_from: Optional[str] = Field(
        default="",
        description="Start date filter in 'MM/DD/YYYY' format (e.g., '10/24/2023')."
    )
    date_to: Optional[str] = Field(
        default="",
        description="End date filter in 'MM/DD/YYYY' format (e.g., '04/14/2024')."
    )
    game_segment: Optional[str] = Field(
        default="",
        description="Game segment filter ('First Half', 'Second Half', 'Overtime')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Last N games filter (0 for all games)."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    location: Optional[str] = Field(
        default="",
        description="Location filter ('Home' or 'Road')."
    )
    month: Optional[int] = Field(
        default=0,
        description="Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Opponent team ID filter (0 for all teams)."
    )
    outcome: Optional[str] = Field(
        default="",
        description="Outcome filter ('W' or 'L')."
    )
    period: Optional[int] = Field(
        default=0,
        description="Period filter (1-4 for quarters, 5+ for overtime, 0 for all periods)."
    )
    season_segment: Optional[str] = Field(
        default="",
        description="Season segment filter ('Pre All-Star', 'Post All-Star')."
    )
    vs_conference: Optional[str] = Field(
        default="",
        description="Conference filter ('East' or 'West')."
    )
    vs_division: Optional[str] = Field(
        default="",
        description="Division filter (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )

@tool("get_nba_league_player_stats", args_schema=LeagueDashPlayerStatsInput)
def get_nba_league_player_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    team_id: str = "",
    player_position: str = "",
    player_experience: str = "",
    starter_bench: str = "",
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    last_n_games: int = 0,
    league_id: str = "00",
    location: str = "",
    month: int = 0,
    opponent_team_id: int = 0,
    outcome: str = "",
    period: int = 0,
    season_segment: str = "",
    vs_conference: str = "",
    vs_division: str = ""
) -> str:
    """Fetches comprehensive player statistics across the league, including basic and advanced stats, scoring and defensive metrics, and player rankings. Allows extensive filtering by season, season type, per mode, measure type, team, player position, experience, starter/bench status, date range, game segment, last N games, league, location, month, opponent, outcome, period, season segment, and opponent conference/division."""
    
    json_response = fetch_league_player_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        team_id=team_id,
        player_position=player_position,
        player_experience=player_experience,
        starter_bench=starter_bench,
        date_from=date_from,
        date_to=date_to,
        game_segment=game_segment,
        last_n_games=last_n_games,
        league_id=league_id,
        location=location,
        month=month,
        opponent_team_id=opponent_team_id,
        outcome=outcome,
        period=period,
        season_segment=season_segment,
        vs_conference=vs_conference,
        vs_division=vs_division,
        return_dataframe=False
    )
    return json_response

class LeagueDashPlayerShotLocationsInput(BaseModel):
    """Input schema for the League Dash Player Shot Locations tool."""
    distance_range: Optional[str] = Field(
        default="By Zone",
        description="Distance range ('5ft Range', '8ft Range', 'By Zone')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Number of last games to consider (e.g., 5, 10, 20). Set to 0 for all games."
    )
    measure_type_simple: Optional[str] = Field(
        default="Base",
        description="Measure type ('Base')."
    )
    per_mode_detailed: Optional[str] = Field(
        default="Totals",
        description="Statistic mode ('Totals' or 'PerGame')."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type_all_star: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Pre Season', 'Playoffs', 'All-Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League). Leave empty for all leagues."
    )
    
from backend.api_tools.league_dash_player_shot_locations import get_league_dash_player_shot_locations as fetch_player_shot_locations_data

@tool("get_league_player_shot_locations", args_schema=LeagueDashPlayerShotLocationsInput)
def get_league_player_shot_locations(
    distance_range: str = "By Zone",
    last_n_games: int = 0,
    measure_type_simple: str = "Base",
    per_mode_detailed: str = "Totals",
    season: str = "2024-25",
    season_type_all_star: str = "Regular Season",
    league_id_nullable: str = ""
) -> str:
    """Fetches league-wide player shot locations data, including shooting percentages by various court zones and distances. Allows filtering by distance range, number of last games, measure type, per mode, season, season type, and league ID."""
    
    json_response = fetch_player_shot_locations_data(
        distance_range=distance_range,
        last_n_games=last_n_games,
        measure_type_simple=measure_type_simple,
        per_mode_detailed=per_mode_detailed,
        season=season,
        season_type_all_star=season_type_all_star,
        league_id_nullable=league_id_nullable,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.schedule_league_v2_int import get_schedule_league_v2_int as fetch_schedule_league_v2_int_data

class ScheduleLeagueV2IntInput(BaseModel):
    """Input schema for the NBA Schedule League V2 International tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )

@tool("get_nba_schedule_league_v2_int", args_schema=ScheduleLeagueV2IntInput)
def get_nba_schedule_league_v2_int(
    league_id: str = "00",
    season: str = "2024-25"
) -> str:
    """Fetches comprehensive league schedule data, including games, weeks, and broadcaster information. Allows filtering by league and season."""
    
    json_response = fetch_schedule_league_v2_int_data(
        league_id=league_id,
        season=season,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.shot_chart_league_wide import get_shot_chart_league_wide as fetch_shot_chart_league_wide_data

class ShotChartLeagueWideInput(BaseModel):
    """Input schema for the NBA League Wide Shot Chart tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current season."
    )

@tool("get_nba_league_wide_shot_chart", args_schema=ShotChartLeagueWideInput)
def get_nba_league_wide_shot_chart(
    league_id: str = "00",
    season: str = "2024-25"
) -> str:
    """Fetches league-wide shot chart data, including shooting percentages by various court zones and distances. Allows filtering by league and season."""
    
    json_response = fetch_shot_chart_league_wide_data(
        league_id=league_id,
        season=season,
        return_dataframe=False
    )
    return json_response

from backend.api_tools.playoff_picture import get_playoff_picture as fetch_playoff_picture_data

class PlayoffPictureInput(BaseModel):
    """Input schema for the NBA Playoff Picture tool."""
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA). Defaults to NBA."
    )
    season_id: Optional[str] = Field(
        default="22024",
        description="Season ID (e.g., '22024' for 2024-25 season). Defaults to current season."
    )

@tool("get_nba_playoff_picture", args_schema=PlayoffPictureInput)
def get_nba_playoff_picture(
    league_id: str = "00",
    season_id: str = "22024"
) -> str:
    """Fetches comprehensive playoff picture data, including series data, standings, and remaining games for both conferences. Allows filtering by league and season ID."""
    
    json_response = fetch_playoff_picture_data(
        league_id=league_id,
        season_id=season_id,
        return_dataframe=False
    )
class LeagueDashPtTeamDefendInput(BaseModel):
    """Input schema for the NBA League Team Tracking Defense Stats tool."""
    season: Optional[str] = Field(
        default="2024-25",
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode for stats ('Totals', 'PerGame')."
    )
    defense_category: Optional[str] = Field(
        default="Overall",
        description="Defense category ('Overall', '3 Pointers', '2 Pointers', 'Less Than 6Ft', 'Less Than 10Ft', 'Greater Than 15Ft')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for teams (e.g., 'East', 'West')."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date filter in YYYY-MM-DD format."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date filter in YYYY-MM-DD format."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for teams (e.g., 'Atlantic', 'Pacific')."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Game segment filter (e.g., 'First Half', 'Second Half')."
    )
    last_n_games_nullable: Optional[int] = Field(
        default=None,
        description="Last N games filter."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Location filter ('Home' or 'Road')."
    )
    month_nullable: Optional[int] = Field(
        default=None,
        description="Month filter (0-12)."
    )
    opponent_team_id_nullable: Optional[int] = Field(
        default=None,
        description="Opponent team ID filter."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Outcome filter ('W' or 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round filter."
    )
    period_nullable: Optional[int] = Field(
        default=None,
        description="Period filter."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Season segment filter (e.g., 'Pre All-Star', 'Post All-Star')."
    )
    team_id_nullable: Optional[str] = Field(
        default=None,
        description="Team ID filter."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Conference filter for opponents (e.g., 'East', 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Division filter for opponents (e.g., 'Atlantic', 'Pacific')."
    )

from backend.api_tools.league_dash_pt_team_defend import fetch_league_dash_pt_team_defend_logic as fetch_league_dash_pt_team_defend_data

@tool("get_nba_league_team_tracking_defense_stats", args_schema=LeagueDashPtTeamDefendInput)
def get_nba_league_team_tracking_defense_stats(
    season: str = "2024-25",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    defense_category: str = "Overall",
    league_id: str = "00",
    conference_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = None,
    location_nullable: Optional[str] = None,
    month_nullable: Optional[int] = None,
    opponent_team_id_nullable: Optional[int] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    period_nullable: Optional[int] = None,
    season_segment_nullable: Optional[str] = None,
    team_id_nullable: Optional[str] = None,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None
) -> str:
    """Fetches defensive team tracking statistics across the league, showing how teams perform when defending shots in different categories. Includes metrics like defended field goal percentage, normal field goal percentage, and the difference between them (PCT_PLUSMINUS) which indicates defensive impact at the team level. Allows extensive filtering."""
    json_response = fetch_league_dash_pt_team_defend_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        defense_category=defense_category,
        league_id=league_id,
        conference_nullable=conference_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        division_nullable=division_nullable,
        game_segment_nullable=game_segment_nullable,
        last_n_games_nullable=last_n_games_nullable,
        location_nullable=location_nullable,
        month_nullable=month_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        period_nullable=period_nullable,
        season_segment_nullable=season_segment_nullable,
        team_id_nullable=team_id_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        return_dataframe=False
    )
    return json_response
class LeagueTeamStatsInput(BaseModel):
    """Input schema for fetching league-wide team statistics."""
    season: Optional[str] = Field(
        default=None,
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Statistic mode ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Optional: Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Optional: Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Optional: Opponent team ID filter (0 for all teams)."
    )
    period: Optional[int] = Field(
        default=0,
        description="Optional: Period filter (1-4 for quarters, 0 for all periods)."
    )
    team_id: Optional[str] = Field(
        default=None,
        description="Optional: Team ID filter."
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Optional: Start date filter (MM/DD/YYYY)."
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Optional: End date filter (MM/DD/YYYY)."
    )
    game_segment: Optional[str] = Field(
        default=None,
        description="Optional: Game segment filter ('First Half', 'Second Half', 'Overtime')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="Optional: League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    location: Optional[str] = Field(
        default=None,
        description="Optional: Location filter ('Home', 'Road')."
    )
    outcome: Optional[str] = Field(
        default=None,
        description="Optional: Outcome filter ('W', 'L')."
    )
    po_round: Optional[str] = Field(
        default=None,
        description="Optional: Playoff round filter (1-4)."
    )
    season_segment: Optional[str] = Field(
        default=None,
        description="Optional: Season segment filter ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range: Optional[str] = Field(
        default=None,
        description="Optional: Shot clock range filter (e.g., '24-22', '22-18', '18-15', '15-7', '7-4', '4-0', 'ShotClockOff')."
    )
    vs_conference: Optional[str] = Field(
        default=None,
        description="Optional: Conference filter for opponents ('East', 'West')."
    )
    vs_division: Optional[str] = Field(
        default=None,
        description="Optional: Division filter for opponents (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    conference: Optional[str] = Field(
        default=None,
        description="Optional: Conference filter for teams ('East', 'West')."
    )
    division: Optional[str] = Field(
        default=None,
        description="Optional: Division filter for teams (e.g., 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest')."
    )
    game_scope: Optional[str] = Field(
        default=None,
        description="Optional: Game scope filter (e.g., 'Season', 'Playoffs', 'All-Star')."
    )
    player_experience: Optional[str] = Field(
        default=None,
        description="Optional: Player experience filter (e.g., 'Rookie', 'Sophomore', 'Veteran')."
    )
    player_position: Optional[str] = Field(
        default=None,
        description="Optional: Player position filter (e.g., 'Guard', 'Forward', 'Center')."
    )
    starter_bench: Optional[str] = Field(
        default=None,
        description="Optional: Starter/bench filter ('Starter', 'Bench')."
    )
    two_way: Optional[str] = Field(
        default=None,
        description="Optional: Two-way player filter ('Y', 'N')."
    )

@tool("get_league_team_stats", args_schema=LeagueTeamStatsInput)
def get_league_team_stats(
    season: str = None,
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    measure_type: str = "Base",
    last_n_games: int = 0,
    month: int = 0,
    opponent_team_id: int = 0,
    pace_adjust: str = "N",
    plus_minus: str = "N",
    rank: str = "N",
    period: int = 0,
    team_id: str = "",
    date_from: str = "",
    date_to: str = "",
    game_segment: str = "",
    league_id: str = "00",
    location: str = "",
    outcome: str = "",
    po_round: str = "",
    season_segment: str = "",
    shot_clock_range: str = "",
    vs_conference: str = "",
    vs_division: str = "",
    conference: str = "",
    division: str = "",
    game_scope: str = "",
    player_experience: str = "",
    player_position: str = "",
    starter_bench: str = "",
    two_way: str = ""
) -> str:
    """Fetches league-wide team statistics.
    This endpoint provides comprehensive team statistics across the league,
    including basic and advanced statistics, scoring and defensive metrics,
    team rankings, and filtering by conference, division, etc.
    """
    from backend.api_tools.league_dash_team_stats import fetch_league_team_stats_logic as fetch_team_stats_data
    
    json_response = fetch_team_stats_data(
        season=season,
        season_type=season_type,
        per_mode=per_mode,
        measure_type=measure_type,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        period=period,
        team_id=team_id,
        date_from=date_from,
        date_to=date_to,
        game_segment=game_segment,
        league_id=league_id,
        location=location,
        outcome=outcome,
        po_round=po_round,
        season_segment=season_segment,
        shot_clock_range=shot_clock_range,
        vs_conference=vs_conference,
        vs_division=vs_division,
        conference=conference,
        division=division,
        game_scope=game_scope,
        player_experience=player_experience,
        player_position=player_position,
        starter_bench=starter_bench,
        two_way=two_way,
        return_dataframe=False
    )
    return json_response
class DraftHistoryInput(BaseModel):
    """Input schema for the NBA Draft History tool."""
    season_year: Optional[str] = Field(
        default=None,
        description="Four-digit draft year (e.g., '2023'). If None, returns all years."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="NBA League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    team_id: Optional[int] = Field(
        default=None,
        description="Optional: NBA team ID to filter by team."
    )
    round_num: Optional[int] = Field(
        default=None,
        description="Optional: Draft round number to filter by round."
    )
    overall_pick: Optional[int] = Field(
        default=None,
        description="Optional: Overall pick number to filter by pick."
    )

@tool("get_nba_draft_history", args_schema=DraftHistoryInput)
def get_nba_draft_history(
    season_year: Optional[str] = None,
    league_id: str = "00",
    team_id: Optional[int] = None,
    round_num: Optional[int] = None,
    overall_pick: Optional[int] = None
) -> str:
    """Fetches NBA draft history, optionally filtered by season year, league, team, round number, or overall pick.
    Each draft pick includes player, year, round, pick, team, and organization info.
    """
    from backend.api_tools.league_draft import fetch_draft_history_logic as fetch_draft_history_data
    
    json_response = fetch_draft_history_data(
        season_year_nullable=season_year,
        league_id_nullable=league_id,
        team_id_nullable=team_id,
        round_num_nullable=round_num,
        overall_pick_nullable=overall_pick,
        return_dataframe=False
    )
    return json_response
class LeagueLeadersInput(BaseModel):
    """Input schema for the NBA League Leaders tool."""
    season: str = Field(
        description="NBA season in 'YYYY-YY' format (e.g., '2023-24')."
    )
    stat_category: Optional[str] = Field(
        default="PTS",
        description="Statistical category abbreviation (e.g., 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    per_mode: Optional[str] = Field(
        default="PerGame",
        description="Per mode ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    scope: Optional[str] = Field(
        default="S",
        description="Scope of leaders ('S' for season, 'RS' for rookies, 'All' for all players)."
    )
    top_n: Optional[int] = Field(
        default=10,
        description="Number of top leaders to return (e.g., 5, 10, 25). Defaults to 10."
    )

@tool("get_nba_league_leaders", args_schema=LeagueLeadersInput)
def get_nba_league_leaders(
    season: str,
    stat_category: str = "PTS",
    season_type: str = "Regular Season",
    per_mode: str = "PerGame",
    league_id: str = "00",
    scope: str = "S",
    top_n: int = 10
) -> str:
    """Fetches league leaders for a specific statistical category and criteria.
    Provides a list of top players/teams based on the specified filters.
    """
    from backend.api_tools.league_leaders_data import fetch_league_leaders_logic as fetch_league_leaders_data
    
    json_response = fetch_league_leaders_data(
        season=season,
        stat_category=stat_category,
        season_type=season_type,
        per_mode=per_mode,
        league_id=league_id,
        scope=scope,
        top_n=top_n,
        return_dataframe=False
    )
    return json_response
class LeagueDashOpponentPtShotInput(BaseModel):
    """Input schema for the NBA League Opponent Player Tracking Shot tool."""
    season: str = Field(
        description="Season in YYYY-YY format (e.g., '2023-24')."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    per_mode_simple: Optional[str] = Field(
        default="Totals",
        description="Per mode ('Totals', 'PerGame')."
    )
    month_nullable: Optional[int] = Field(
        default=0,
        description="Filter by month (1-12, 0 for all months)."
    )
    period_nullable: Optional[int] = Field(
        default=0,
        description="Filter by period (1-4 for quarters, 0 for full game)."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Start date (YYYY-MM-DD)."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD)."
    )
    opponent_team_id_nullable: Optional[int] = Field(
        default=0,
        description="Filter by opponent team ID (0 for all opponents)."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent conference ('East', 'West')."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by opponent division."
    )
    team_id_nullable: Optional[int] = Field(
        default=None,
        description="Filter by a specific team's ID to see shots against them."
    )
    conference_nullable: Optional[str] = Field(
        default=None,
        description="Filter by team's conference ('East', 'West')."
    )
    division_nullable: Optional[str] = Field(
        default=None,
        description="Filter by team's division."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by game segment ('First Half', 'Second Half', 'Overtime')."
    )
    last_n_games_nullable: Optional[int] = Field(
        default=0,
        description="Filter by last N games (0 for all games)."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Filter by location ('Home', 'Road')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Filter by outcome ('W', 'L')."
    )
    po_round_nullable: Optional[str] = Field(
        default=None,
        description="Playoff round (e.g., '1', '2')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    shot_clock_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot clock range."
    )
    close_def_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by closest defender distance."
    )
    shot_dist_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by shot distance."
    )
    dribble_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by dribble range."
    )
    general_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by general range."
    )
    touch_time_range_nullable: Optional[str] = Field(
        default=None,
        description="Filter by touch time range."
    )

@tool("get_league_opponent_shot_dashboard", args_schema=LeagueDashOpponentPtShotInput)
def get_league_opponent_shot_dashboard(
    season: str,
    season_type: str = "Regular Season",
    league_id_nullable: Optional[str] = "00",
    per_mode_simple: str = "Totals",
    month_nullable: Optional[int] = 0,
    period_nullable: Optional[int] = 0,
    date_from_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    opponent_team_id_nullable: Optional[int] = 0,
    vs_conference_nullable: Optional[str] = None,
    vs_division_nullable: Optional[str] = None,
    team_id_nullable: Optional[int] = None,
    conference_nullable: Optional[str] = None,
    division_nullable: Optional[str] = None,
    game_segment_nullable: Optional[str] = None,
    last_n_games_nullable: Optional[int] = 0,
    location_nullable: Optional[str] = None,
    outcome_nullable: Optional[str] = None,
    po_round_nullable: Optional[str] = None,
    season_segment_nullable: Optional[str] = None,
    shot_clock_range_nullable: Optional[str] = None,
    close_def_dist_range_nullable: Optional[str] = None,
    shot_dist_range_nullable: Optional[str] = None,
    dribble_range_nullable: Optional[str] = None,
    general_range_nullable: Optional[str] = None,
    touch_time_range_nullable: Optional[str] = None
) -> str:
    """Fetches league dashboard data for opponent player/team shots, providing statistics about shots taken by opponents. Allows extensive filtering."""
    from backend.api_tools.league_opponent_shot_dashboard import fetch_league_dash_opponent_pt_shot_logic as fetch_opponent_shot_data
    
    json_response = fetch_opponent_shot_data(
        season=season,
        season_type=season_type,
        league_id_nullable=league_id_nullable,
        per_mode_simple=per_mode_simple,
        month_nullable=month_nullable,
        period_nullable=period_nullable,
        date_from_nullable=date_from_nullable,
        date_to_nullable=date_to_nullable,
        opponent_team_id_nullable=opponent_team_id_nullable,
        vs_conference_nullable=vs_conference_nullable,
        vs_division_nullable=vs_division_nullable,
        team_id_nullable=team_id_nullable,
        conference_nullable=conference_nullable,
        division_nullable=division_nullable,
        game_segment_nullable=game_segment_nullable,
        last_n_games_nullable=last_n_games_nullable,
        location_nullable=location_nullable,
        outcome_nullable=outcome_nullable,
        po_round_nullable=po_round_nullable,
        season_segment_nullable=season_segment_nullable,
        shot_clock_range_nullable=shot_clock_range_nullable,
        close_def_dist_range_nullable=close_def_dist_range_nullable,
        shot_dist_range_nullable=shot_dist_range_nullable,
        dribble_range_nullable=dribble_range_nullable,
        general_range_nullable=general_range_nullable,
        touch_time_range_nullable=touch_time_range_nullable,
        return_dataframe=False
    )
    return json_response
class LeaguePlayerOnDetailsInput(BaseModel):
    """Input schema for the NBA League Player On Details tool."""
    season: Optional[str] = Field(
        default=None,
        description="Season in YYYY-YY format (e.g., '2023-24'). Defaults to current NBA season."
    )
    season_type: Optional[str] = Field(
        default="Regular Season",
        description="Season type ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')."
    )
    measure_type: Optional[str] = Field(
        default="Base",
        description="Statistical category ('Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent', 'Usage', 'Defense')."
    )
    per_mode: Optional[str] = Field(
        default="Totals",
        description="Per mode ('Totals', 'PerGame', 'MinutesPer', 'Per48', 'Per40', 'Per36', 'PerMinute', 'PerPossession', 'PerPlay', 'Per100Possessions', 'Per100Plays')."
    )
    team_id: int = Field(
        description="Team ID to filter by. This is a required parameter for this endpoint."
    )
    last_n_games: Optional[int] = Field(
        default=0,
        description="Optional: Last N games filter (0 for all games)."
    )
    month: Optional[int] = Field(
        default=0,
        description="Optional: Month filter (1-12, 0 for all months)."
    )
    opponent_team_id: Optional[int] = Field(
        default=0,
        description="Optional: Opponent team ID filter (0 for all opponents)."
    )
    pace_adjust: Optional[str] = Field(
        default="N",
        description="Whether to pace-adjust stats ('Y' or 'N')."
    )
    plus_minus: Optional[str] = Field(
        default="N",
        description="Whether to include plus-minus stats ('Y' or 'N')."
    )
    rank: Optional[str] = Field(
        default="N",
        description="Whether to include rank stats ('Y' or 'N')."
    )
    period: Optional[int] = Field(
        default=0,
        description="Optional: Period filter (1-4 for quarters, 0 for all periods)."
    )
    vs_division_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by opponent division."
    )
    vs_conference_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by opponent conference ('East', 'West')."
    )
    season_segment_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by season segment ('Pre All-Star', 'Post All-Star')."
    )
    outcome_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by outcome ('W', 'L')."
    )
    location_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by location ('Home', 'Road')."
    )
    league_id_nullable: Optional[str] = Field(
        default="00",
        description="Optional: League ID (00 for NBA, 10 for WNBA, 20 for G-League)."
    )
    game_segment_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Filter by game segment ('First Half', 'Second Half', 'Overtime')."
    )
    date_to_nullable: Optional[str] = Field(
        default=None,
        description="Optional: End date (YYYY-MM-DD)."
    )
    date_from_nullable: Optional[str] = Field(
        default=None,
        description="Optional: Start date (YYYY-MM-DD)."
    )

@tool("get_league_player_on_details", args_schema=LeaguePlayerOnDetailsInput)
def get_league_player_on_details(
    team_id: int,
    season: str = None,
    season_type: str = "Regular Season",
    measure_type: str = "Base",
    per_mode: str = "Totals",
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
    league_id_nullable: Optional[str] = "00",
    game_segment_nullable: Optional[str] = None,
    date_to_nullable: Optional[str] = None,
    date_from_nullable: Optional[str] = None
) -> str:
    """Fetches NBA league player on details data, providing statistics about players when they are on the court for a specific team. Allows extensive filtering by season, season type, measure type, per mode, team ID, last N games, month, opponent team, pace adjustment, plus/minus, rank, period, opponent division/conference, season segment, outcome, location, league ID, game segment, and date range."""
    from backend.api_tools.league_player_on_details import fetch_league_player_on_details_logic as fetch_player_on_details_data
    
    json_response = fetch_player_on_details_data(
        season=season,
        season_type=season_type,
        measure_type=measure_type,
        per_mode=per_mode,
        team_id=team_id,
        last_n_games=last_n_games,
        month=month,
        opponent_team_id=opponent_team_id,
        pace_adjust=pace_adjust,
        plus_minus=plus_minus,
        rank=rank,
        period=period,
        vs_division_nullable=vs_division_nullable,
        vs_conference_nullable=vs_conference_nullable,
        season_segment_nullable=season_segment_nullable,
        outcome_nullable=outcome_nullable,
        location_nullable=location_nullable,
        league_id_nullable=league_id_nullable,
        game_segment_nullable=game_segment_nullable,
        date_to_nullable=date_to_nullable,
        date_from_nullable=date_from_nullable,
        return_dataframe=False
    )
    return json_response
class CommonPlayoffSeriesInput(BaseModel):
    """Input schema for the Common Playoff Series tool."""
    season: str = Field(
        description="The NBA season identifier in YYYY-YY format (e.g., '2022-23')."
    )
    league_id: Optional[str] = Field(
        default="00",
        description="The league ID ('00' for NBA, '10' for WNBA, '20' for G-League). Defaults to '00'."
    )
    series_id: Optional[str] = Field(
        default=None,
        description="A specific SeriesID to filter for. Optional."
    )

@tool("get_common_playoff_series", args_schema=CommonPlayoffSeriesInput)
def get_common_playoff_series(
    season: str,
    league_id: str = "00",
    series_id: Optional[str] = None
) -> str:
    """Fetches information about playoff series for a given league and season.
    Can optionally be filtered by a specific SeriesID.
    Returns a JSON string containing a list of playoff series game details."""
    
    json_response = fetch_common_playoff_series_data(
        season=season,
        league_id=league_id,
        series_id=series_id,
        return_dataframe=False
    )
    return json_response