"""Tool registry. Desks own their tools. Order stays stable for prompts."""

from langchain_core.tools import BaseTool

from .league import (
    get_briefing,
    get_cap_ledger,
    get_combine,
    get_finder,
    get_hustle,
    get_leaders,
    get_playoffs,
    get_rapm,
    get_rest,
    get_standings,
    get_trade_check,
    get_win_prob,
    text_to_sql,
)
from .player import (
    get_compare,
    get_comps,
    get_four_factors,
    get_last_x,
    get_on_off,
    get_percentiles,
    get_player_intel,
    get_shot_zones,
    get_splits,
    get_trend,
    get_wowy,
)
from .shared import resolve_entity, search_nba
from .team import (
    get_boxscore,
    get_games_on_date,
    get_lineups,
    get_preview,
    get_recap,
    get_scouting_report,
    get_team_hub,
)
from ._core import MAX_ROWS, SEASON, STAT_CATEGORIES, clamp_stat

v1_tools: list[BaseTool] = [
    resolve_entity,
    search_nba,
    get_player_intel,
    get_team_hub,
    get_games_on_date,
    get_boxscore,
    get_standings,
    get_playoffs,
    get_leaders,
    get_lineups,
    get_on_off,
    get_wowy,
    get_four_factors,
    get_last_x,
    get_percentiles,
    get_briefing,
    get_shot_zones,
    get_hustle,
    get_splits,
    get_scouting_report,
    get_recap,
    text_to_sql,
    get_finder,
    get_rapm,
    get_combine,
    get_compare,
    get_comps,
    get_rest,
    get_trend,
    get_win_prob,
    get_preview,
    get_cap_ledger,
    get_trade_check,
]

TOOL_NAMES = [t.name for t in v1_tools]

__all__ = [
    "SEASON", "MAX_ROWS", "STAT_CATEGORIES", "clamp_stat",
    "v1_tools", "TOOL_NAMES",
]
