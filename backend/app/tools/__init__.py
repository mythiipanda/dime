"""Tool registry. Desks own their tools. Order stays stable for prompts."""

from langchain_core.tools import BaseTool

from .awards import get_award_race
from .history import get_historical_leaders
from .league import (
    get_briefing,
    get_cap_ledger,
    get_clutch,
    get_combine,
    get_contract_value,
    get_draft_board,
    get_draft_model,
    get_elo,
    get_elo_standings,
    get_finder,
    get_hustle,
    get_injuries,
    get_leaders,
    get_team_leaders,
    get_lineup_leaders,
    get_playoffs,
    get_playoff_sim,
    get_rapm,
    get_ratings,
    get_risers,
    get_player_risers,
    get_rookie_leaders,
    get_rest,
    get_standings,
    get_standings_deep,
    get_trade_check,
    get_trade_value,
    get_warehouse_freshness,
    get_win_prob,
    get_leaderboard_deltas,
    snapshot_leaderboard,
    text_to_sql,
)
from .lineup import get_lineup_stats
from .player import (
    compare_metrics,
    get_advanced,
    get_compare,
    get_debate_card,
    get_comps,
    get_four_factors,
    get_hustle_boards,
    get_impact_estimate,
    get_last_x,
    get_on_off,
    get_percentiles,
    get_player_intel,
    get_season_averages,
    get_playoff_intel,
    get_raptor_history,
    get_shot_compare,
    get_shot_zones,
    get_splits,
    get_trend,
    get_wowy,
)
from .preview import get_matchup_preview
from .prediction import get_game_prediction
from .priors import get_rapm_prior
from .shared import resolve_entity, run_python, search_nba
from .headtohead import get_head_to_head
from .team import get_season_series
from .gamelog import search_game_logs
from .splits import get_matchup_splits, get_regression_check
from .streaks import get_streaks
from .rest import get_rest_advantage
from .competitive import get_competitive_ratings
from .lineup_matrix import get_lineup_matchup_matrix
from .shots import search_shots
from .zone import get_team_shot_zones
from .zonedelta import get_zone_deltas
from .team import (
    get_boxscore,
    get_games_on_date,
    get_injury_impact,
    get_lineups,
    get_preview,
    get_recap,
    get_rotation_check,
    get_scout_pack,
    get_scouting_report,
    get_team_hub,
    get_team_splits,
)
from .today import get_today, get_morning_briefing
from .watchlist import add_watchlist_item, get_watchlist, remove_watchlist_item
from .wpa import get_wpa_leaders
from ._core import MAX_ROWS, SEASON, STAT_CATEGORIES, clamp_stat

v1_tools: list[BaseTool] = [
    resolve_entity,
    search_nba,
    run_python,
    get_player_intel,
    get_season_averages,
    get_playoff_intel,
    get_raptor_history,
    get_team_hub,
    get_games_on_date,
    get_boxscore,
    get_standings,
    get_playoffs,
    get_leaders,
    get_team_leaders,
    get_lineups,
    get_lineup_stats,
    get_on_off,
    get_wowy,
    get_four_factors,
    get_last_x,
    get_percentiles,
    get_shot_compare,
    get_shot_zones,
    get_hustle,
    get_injuries,
    get_splits,
    get_matchup_splits,
    get_regression_check,
    get_scouting_report,
    get_recap,
    text_to_sql,
    get_finder,
    get_rapm,
    get_combine,
    get_compare,
    compare_metrics,
    get_debate_card,
    get_award_race,
    get_historical_leaders,
    get_comps,
    get_advanced,
    get_rest,
    get_trend,
    get_win_prob,
    get_preview,
    get_matchup_preview,
    get_scout_pack,
    get_rotation_check,
    get_team_splits,
    get_injury_impact,
    get_cap_ledger,
    get_trade_check,
    get_trade_value,
    get_ratings,
    get_clutch,
    get_elo,
    get_elo_standings,
    get_playoff_sim,
    get_contract_value,
    get_draft_board,
    get_draft_model,
    get_risers,
    get_player_risers,
    get_rookie_leaders,
    get_lineup_leaders,
    get_standings_deep,
    get_hustle_boards,
    get_impact_estimate,
    get_warehouse_freshness,
    get_today,
    get_morning_briefing,
    get_briefing,
    get_leaderboard_deltas,
    snapshot_leaderboard,
    add_watchlist_item,
    get_watchlist,
    remove_watchlist_item,
    get_streaks,
    get_head_to_head,
    get_season_series,
    search_game_logs,
    get_game_prediction,
    get_team_shot_zones,
    get_rest_advantage,
    get_competitive_ratings,
    get_lineup_matchup_matrix,
    search_shots,
    get_zone_deltas,
    get_rapm_prior,
    get_wpa_leaders,
]

TOOL_NAMES = [t.name for t in v1_tools]

__all__ = [
    "SEASON", "MAX_ROWS", "STAT_CATEGORIES", "clamp_stat",
    "v1_tools", "TOOL_NAMES",
]
