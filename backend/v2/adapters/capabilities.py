"""The v2 initial capability set: one Capability per v1 tool in the pack."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..contracts import EntityRef

COUNT = "count"
PER_GAME = "per_game"
FRACTION = "fraction_0_1"
PERCENT = "percent_0_100"
POINTS_PER_100 = "points_per_100_possessions"
MINUTES = "minutes"

EFG_DEF = (
    "Effective field-goal percentage: (FGM + 0.5 * FG3M) / FGA, "
    "fraction scale 0-1.")
TS_DEF = (
    "True shooting percentage: PTS / (2 * (FGA + 0.44 * FTA)), "
    "fraction scale 0-1.")
NET_RATING_DEF = (
    "Net rating: offensive rating minus defensive rating, points per "
    "100 possessions.")
FOUR_FACTORS_DEFS = {
    "efg_pct": EFG_DEF,
    "tov_pct": "Turnover percentage: turnovers per 100 possessions, "
               "fraction scale 0-1.",
    "orb_pct": "Offensive rebound percentage: share of available offensive "
               "rebounds, fraction scale 0-1.",
    "ft_rate": "Free-throw rate: FTM / FGA, fraction scale 0-1.",
}


def _resolve_entities(rows: Any) -> list[EntityRef]:
    out: list[EntityRef] = []
    if isinstance(rows, Mapping):
        for player in rows.get("players") or []:
            if isinstance(player, Mapping) and player.get("id"):
                out.append(EntityRef(
                    id=str(player["id"]), type="player",
                    display_name=str(player.get("full_name", ""))))
        for team in rows.get("teams") or []:
            if isinstance(team, Mapping) and team.get("id"):
                out.append(EntityRef(
                    id=str(team["id"]), type="team",
                    display_name=str(team.get("full_name", ""))))
    return out


@dataclass(frozen=True)
class Capability:
    name: str
    tool_name: str
    season_arg: str | None = "season"
    units: Mapping[str, str] = field(default_factory=dict)
    metric_definitions: Mapping[str, str] = field(default_factory=dict)
    qualification: str | None = None
    extract_entities: Callable[[Any], list[EntityRef]] | None = None


_LIST = [
    Capability(
        name="entity_resolution",
        tool_name="resolve_entity",
        season_arg=None,
        extract_entities=_resolve_entities,
    ),
    Capability(
        name="standings",
        tool_name="get_standings",
        units={"WINS": COUNT, "LOSSES": COUNT, "WinPCT": FRACTION,
               "PointsPG": PER_GAME, "OppPointsPG": PER_GAME,
               "DiffPointsPG": PER_GAME},
    ),
    Capability(
        name="team_totals",
        tool_name="get_team_leaders",
        units={"GP": COUNT},
    ),
    Capability(
        name="qualified_leaders",
        tool_name="get_leaders",
        units={"GP": COUNT, "MIN": MINUTES, "FG_PCT": FRACTION,
               "FG3_PCT": FRACTION, "FT_PCT": FRACTION},
        qualification="Qualified players only (NBA leaderboard minimums).",
    ),
    Capability(
        name="team_ratings",
        tool_name="get_ratings",
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "NET_RATING": POINTS_PER_100, "PACE": "possessions_per_48"},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
    ),
    Capability(name="roster", tool_name="get_team_hub"),
    Capability(name="player_report", tool_name="get_player_report"),
    Capability(name="player_comparison", tool_name="get_compare"),
    Capability(name="metric_coverage", tool_name="compare_metrics"),
    Capability(
        name="shots",
        tool_name="search_shots",
        units={"SHOT_DISTANCE": "feet", "LOC_X": "court_tenths_feet",
               "LOC_Y": "court_tenths_feet"},
    ),
    Capability(
        name="shooting_efficiency",
        tool_name="get_season_averages",
        units={"ts_pct": FRACTION, "efg_pct": FRACTION, "fg_pct": FRACTION,
               "fg3_pct": FRACTION, "ft_pct": FRACTION},
        metric_definitions={"ts_pct": TS_DEF, "efg_pct": EFG_DEF},
    ),
    Capability(
        name="on_off",
        tool_name="get_on_off",
        units={"NET_RATING": POINTS_PER_100},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
    ),
    Capability(
        name="lineups",
        tool_name="get_lineup_stats",
        units={"MIN": MINUTES, "NET_RATING": POINTS_PER_100},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
        qualification="Lineup sample floor applies (default 100 "
                      "possessions); smaller samples only on request.",
    ),
    Capability(
        name="clutch",
        tool_name="get_clutch",
        qualification="Clutch: last 5 minutes, margin 5 or fewer.",
    ),
    Capability(name="playoffs", tool_name="get_playoffs"),
    Capability(name="trades", tool_name="get_trade_check", season_arg=None),
    Capability(name="contracts", tool_name="get_cap_ledger", season_arg=None),
    Capability(name="game_logs", tool_name="search_game_logs"),
    Capability(
        name="four_factors",
        tool_name="get_four_factors",
        metric_definitions=FOUR_FACTORS_DEFS,
    ),
    Capability(
        name="team_four_factors",
        tool_name="get_team_four_factors",
        metric_definitions=FOUR_FACTORS_DEFS,
    ),
]

CAPABILITIES: dict[str, Capability] = {c.name: c for c in _LIST}

if len(CAPABILITIES) != len(_LIST):
    raise AssertionError("duplicate capability names")
