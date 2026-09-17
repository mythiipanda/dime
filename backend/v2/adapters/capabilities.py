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

EFG_DEF = "Effective field-goal percentage: (FGM + 0.5 * FG3M) / FGA."
TS_DEF = "True shooting percentage: PTS / (2 * (FGA + 0.44 * FTA))."
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


def _player_entity(rows: Any) -> list[EntityRef]:
    if not isinstance(rows, Mapping):
        return []
    line = rows.get("season_line")
    line = line if isinstance(line, Mapping) else {}
    player_id = rows.get("player_id") or line.get("PLAYER_ID")
    name = (rows.get("player") or rows.get("PLAYER_NAME")
            or line.get("PLAYER") or line.get("PLAYER_NAME"))
    return ([EntityRef(id=str(player_id), type="player", display_name=str(name or player_id))]
            if player_id is not None else [])


def _team_entities(rows: Any) -> list[EntityRef]:
    items = rows if isinstance(rows, list) else [rows]
    found: dict[str, EntityRef] = {}
    for item in items:
        if not isinstance(item, Mapping) or item.get("team_id") is None:
            continue
        ref = EntityRef(id=str(item["team_id"]), type="team",
                        display_name=str(item.get("team") or item["team_id"]))
        found[ref.id] = ref
    return list(found.values())


@dataclass(frozen=True)
class Capability:
    name: str
    tool_name: str
    season_arg: str | None = "season"
    units: Mapping[str, str] = field(default_factory=dict)
    metric_definitions: Mapping[str, str] = field(default_factory=dict)
    qualification: str | None = None
    coverage: str | None = None
    source_prefix: str = "v1"
    task_season_scoped: bool = True
    extract_entities: Callable[[Any], list[EntityRef]] | None = None
    # Provider arguments whose identity must be established by a direct
    # entity-resolution dependency before execution. Keys are tool argument
    # names; values are EntityRef types.
    dependent_entity_arguments: Mapping[str, str] = field(default_factory=dict)


_LIST = [
    Capability(
        name="entity_resolution",
        tool_name="resolve_entity",
        season_arg=None,
        task_season_scoped=False,
        extract_entities=_resolve_entities,
    ),
    Capability(
        name="warehouse_freshness",
        tool_name="get_warehouse_freshness",
        season_arg=None,
        task_season_scoped=False,
        units={"rows": COUNT, "age_hours": "hours"},
        coverage=(
            "All silver warehouse tables with row count, last observed fetch, "
            "expected cadence, and tri-state stale status. Static tables are "
            "never marked stale; missing timestamps remain unknown."
        ),
    ),
    Capability(
        name="standings",
        tool_name="get_standings",
        units={"WINS": COUNT, "LOSSES": COUNT, "WinPCT": FRACTION,
               "PointsPG": PER_GAME, "OppPointsPG": PER_GAME,
               "DiffPointsPG": PER_GAME},
    ),
    Capability(
        name="team_trajectory",
        tool_name="get_team_trajectory",
        season_arg="through_season",
        units={"wins": COUNT, "losses": COUNT, "win_pct": FRACTION},
        coverage="Bounded regular-season records, newest first.",
        extract_entities=_team_entities,
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
        coverage="Source-ranked qualified leaderboard; returned rows preserve population ranks.",
    ),
    Capability(
        name="team_splits", tool_name="get_team_splits",
        units={"GP": COUNT, "W": COUNT, "L": COUNT, "PPG": PER_GAME},
        coverage="Home, away, result, last-10, and monthly splits from cached team games.",
    ),
    Capability(
        name="injury_impact", tool_name="get_injury_impact",
        coverage="Current injury rows combined with team rating and recent-form context.",
        dependent_entity_arguments={"team": "team"},
    ),
    Capability(
        name="lineup_matchups", tool_name="get_lineup_matchup_matrix",
        units={"shared_minutes": MINUTES, "NET_RATING": POINTS_PER_100},
        qualification="Both teams' lineups meet the configured season-minute floor.",
        coverage="Observed shared play-level possessions for the selected team matchup.",
    ),
    Capability(
        name="competitive_ratings", tool_name="get_competitive_ratings",
        units={"mov": "points", "competitive_mov": "points"},
        qualification="Competitive-game sample meets the configured games floor.",
        coverage="Selected warehouse season and season type with blowouts separated.",
    ),
    Capability(
        name="injuries", tool_name="get_injuries",
        season_arg=None, task_season_scoped=False,
        coverage="Current warehouse injury rows with source freshness metadata.",
    ),
    Capability(
        name="team_shot_zones", tool_name="get_team_shot_zones",
        units={"attempt_share": FRACTION, "efg": FRACTION},
        qualification="Geometric shot zones with pooled league baselines.",
        coverage="All teams represented in the selected historical shot table.",
    ),
    Capability(
        name="player_shot_zones", tool_name="get_shot_zones",
        units={"share": FRACTION, "FG_PCT": FRACTION},
        qualification="One resolved player; source-specific zone granularity applies.",
    ),
    Capability(
        name="rest_splits", tool_name="get_rest",
        units={"wins": COUNT, "losses": COUNT, "games": COUNT,
               "win_pct": FRACTION},
        qualification=("Rest days before each game: zero, one, or two-plus; "
                       "first game per team excluded."),
        coverage="All dated team-games in the selected season scope.",
    ),
    Capability(
        name="rookie_leaders", tool_name="get_rookie_leaders",
        units={"GP": COUNT, "MPG": MINUTES, "PPG": PER_GAME,
               "RPG": PER_GAME, "APG": PER_GAME},
        qualification=("First NBA season only: no player row in any prior "
                       "warehouse season; configurable games/stat floors."),
        coverage="Current-season players represented in the warehouse.",
    ),
    Capability(
        name="team_ratings",
        tool_name="get_ratings",
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "NET_RATING": POINTS_PER_100, "PACE": "possessions_per_48"},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
        qualification="All NBA teams in the selected regular season.",
        coverage="Full regular-season team rating table.",
    ),
    Capability(name="roster", tool_name="get_team_hub"),
    Capability(name="player_report", tool_name="get_player_report",
               extract_entities=_player_entity),
    Capability(name="player_evaluation", tool_name="get_player_evaluation",
               qualification="Ranks use the tool's declared qualified player pools.",
               coverage="Current-season player population represented in the warehouse.",
               extract_entities=_player_entity),
    Capability(name="player_comparison", tool_name="get_compare"),
    Capability(name="metric_adjudication", tool_name="compare_metrics"),
    Capability(name="metric_coverage", tool_name="metric_coverage", source_prefix="v2"),
    Capability(
        name="shots",
        tool_name="search_shots",
        units={"SHOT_DISTANCE": "feet", "LOC_X": "court_tenths_feet",
               "LOC_Y": "court_tenths_feet"},
    ),
    Capability(
        name="shooting_efficiency",
        tool_name="get_advanced",
        units={"TS_PCT": PERCENT, "EFG_PCT": PERCENT},
        metric_definitions={"TS_PCT": TS_DEF, "EFG_PCT": EFG_DEF},
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
    Capability(
        name="player_ratings", tool_name="get_player_ratings",
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "MINUTES": MINUTES},
        qualification="Minimum total-minutes floor is required.",
        coverage=("On-court team rating while each player played; not an "
                  "isolated individual-value metric."),
    ),
    Capability(
        name="playoff_team_ratings", tool_name="get_playoff_team_ratings",
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "NET_RATING": POINTS_PER_100},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
        qualification=("All playoff teams; estimated possessions use the "
                       "NBA box-score formula."),
        coverage="Completed playoff games only.",
    ),
    Capability(name="trades", tool_name="get_trade_check", season_arg=None,
               task_season_scoped=False),
    Capability(name="trade_value", tool_name="get_trade_value", season_arg=None,
               task_season_scoped=False),
    Capability(name="contracts", tool_name="get_cap_ledger", season_arg=None,
               task_season_scoped=False),
    Capability(
        name="game_prediction", tool_name="get_game_prediction",
        units={"win_prob": FRACTION, "win_prob_ci90": FRACTION,
               "projected_score": "points", "projected_total": "points",
               "total_ci90": "points", "margin_ci90": "points"},
        metric_definitions={
            "win_probability": "Share of Monte Carlo simulations won.",
        },
        qualification="Pre-game estimate from 10,000 seeded simulations by default.",
        coverage="Two-team matchup using season ratings, pace, and available injury data.",
    ),
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

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "entity_resolution": "Resolve a player or team name to canonical identity.",
    "warehouse_freshness": "Authoritative warehouse table freshness, cadence, row counts, and stale status.",
    "standings": "League standings for one season.",
    "team_trajectory": "Bounded multi-season regular-season records for one team.",
    "team_totals": "Team leaderboard for a counting stat, with totals and per-game averages.",
    "qualified_leaders": "Qualified player leaderboard for one stat category.",
    "team_splits": "Team home/away, result, last-10, and monthly records and scoring.",
    "injury_impact": "Current injuries combined with team ratings and recent form.",
    "lineup_matchups": "Observed lineup-vs-lineup shared possessions for two teams with sample flags.",
    "competitive_ratings": "Team margin performance with blowouts separated from competitive games.",
    "injuries": "Current team or player injury rows with designation and source freshness.",
    "team_shot_zones": "League or selected-team zone attempt share and efficiency with league baselines.",
    "player_shot_zones": "One player's shot-zone makes, attempts, efficiency, and attempt share.",
    "rest_splits": "Team records by zero, one, and two-plus days of rest, with sample sizes.",
    "rookie_leaders": "First-year NBA player leaderboard using prior-season exclusion, never age as a proxy.",
    "team_ratings": "Team offensive, defensive, and net ratings plus pace and ranks.",
    "roster": "Team roster and game-log context for one season.",
    "player_report": "Player season line, advanced profile, shots, and clutch context.",
    "player_evaluation": "Player tier, advanced profile, modeled value, and comparisons.",
    "player_comparison": "Side-by-side comparison of two players.",
    "metric_adjudication": "Cross-metric impact comparison for two players.",
    "metric_coverage": "Report available and unavailable metrics for an analysis request.",
    "shots": "Filter and aggregate shots by player, team, zone, period, result, or clock.",
    "shooting_efficiency": "Player usage, shooting efficiency, PIE, and ratings.",
    "on_off": "Player on-court and off-court possession splits for one team.",
    "lineups": "Five-player lineup ratings subject to a possession sample floor.",
    "clutch": "Player or team stats in the last five minutes with a margin of five or less.",
    "playoffs": "Playoff wins by team and champion for one season.",
    "player_ratings": (
        "Qualified player on-court offensive or defensive rating leaderboard. "
        "This is lineup context, not isolated player value."
    ),
    "playoff_team_ratings": (
        "Team offensive, defensive, and net ratings from completed playoff games."
    ),
    "trades": "Check salary-matching legality for players on two trade sides.",
    "trade_value": "Compare estimated production value, salary, and picks across trade sides.",
    "contracts": "Team payroll, player salaries, and apron room.",
    "game_prediction": "Pre-game Monte Carlo estimate for a two-team matchup.",
    "game_logs": "Filter player or team game logs by stats, opponent, date, or venue.",
    "four_factors": "Player on-off splits for the four factors.",
    "team_four_factors": "Team offensive and defensive four-factor profile.",
}

if len(CAPABILITIES) != len(_LIST):
    raise AssertionError("duplicate capability names")
if CAPABILITY_DESCRIPTIONS.keys() != CAPABILITIES.keys():
    raise AssertionError("capability descriptions must cover the catalog exactly")
