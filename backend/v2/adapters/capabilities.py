from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from shared.tools.leader_metrics import COUNTING_METRICS, per_game_column

from ..contracts import EntityRef

COUNT = "count"
PER_GAME = "per_game"
FRACTION = "fraction_0_1"
PERCENT = "percent_0_100"
POINTS_PER_100 = "points_per_100_possessions"
MINUTES = "minutes"
BALLOT_POINTS = "ballot_points"
YEARS = "years"

COUNTING_UNITS = {metric: COUNT for metric in COUNTING_METRICS}
PER_GAME_UNITS = {per_game_column(metric): PER_GAME
                  for metric in COUNTING_METRICS}

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

AWARD_SHARE_DEF = ("Award share: share of the maximum ballot points available "
                   "to the placement, fraction scale 0-1. The official winner "
                   "usually lands near 0.9, so 0.913 is 91.3 percent.")
POINTS_WON_DEF = ("Points won: weighted ballot points credited to the "
                  "placement. points_max is the largest point total on that "
                  "ballot, so the winner's points_won equals points_max.")
VOTES_DEF = ("First, second, and third place votes a placement received on a "
             "published ballot, counted in ballots. Null where the source "
             "publishes no vote count for that award.")

AWARD_FIELD_UNITS = {
    "age": YEARS,
    "award_share": FRACTION,
    "points_max": BALLOT_POINTS,
    "points_won": BALLOT_POINTS,
    "rank": COUNT,
    "votes_first": COUNT,
    "votes_second": COUNT,
    "votes_third": COUNT,
}

AWARD_FIELD_DEFINITIONS = {
    "age": ("Age in years the player was on the ballot; null on a coach row."),
    "award": "Award code the source published the placement under.",
    "award_share": AWARD_SHARE_DEF,
    "coach": ("Coach named on the placement; null on a player award, so a "
              "Coach-of-the-Year question reads this column."),
    "player": ("Player named on the placement; null on a Coach-of-the-Year "
               "row, so a player-award question reads this column."),
    "points_max": POINTS_WON_DEF,
    "points_won": POINTS_WON_DEF,
    "rank": ("Published leading rank on the ballot. A tied placement shares "
             "the leading rank; null for an ORV row."),
    "rank_label": "Verbatim published rank label, including a tie suffix.",
    "season": "Season the source published the ballot for.",
    "team": "Team abbreviation published with the placement.",
    "tied": "True when the published rank label marks a tied placement.",
    "votes_first": VOTES_DEF,
    "votes_second": VOTES_DEF,
    "votes_third": VOTES_DEF,
}

AWARD_OUTPUT_ALIASES = {
    "PLAYER_NAME": "player",
    "COACH_NAME": "coach",
    "VOTE_SHARE": "award_share",
    "WINNER": "winner",
    "VOTE_COUNT": "votes_first",
}

def _award_vocabulary() -> tuple[dict[str, str], dict[str, str]]:
    from shared.tools.award_results import _SELECT, _placement

    source_row = dict.fromkeys(
        name.strip() for name in _SELECT.replace("\n", " ").split(","))
    fields = tuple(_placement(source_row))
    return ({field: AWARD_FIELD_UNITS[field] for field in fields
             if field in AWARD_FIELD_UNITS},
            {field: AWARD_FIELD_DEFINITIONS.get(
                field, f"{field.replace('_', ' ')} as the award ballot "
                       "publishes it.")
             for field in fields})

AWARD_UNITS, AWARD_DEFINITIONS = _award_vocabulary()

SQL_EXEC_UNITS = {
    "n": COUNT,
    "count": COUNT,
    "total": COUNT,
    "players": COUNT,
    "teams": COUNT,
    "games": COUNT,
    "wins": COUNT,
    "losses": COUNT,
}

SQL_EXEC_DEFINITIONS = {
    "n": ("Primary numeric answer the agent-written aggregate returned, "
          "counted in rows or wins as the SQL aliases it."),
    "count": "Row count the agent-written aggregate returned.",
    "total": "Total the agent-written aggregate summed or counted.",
    "players": "Players counted by the agent-written aggregate.",
    "teams": "Teams counted by the agent-written aggregate.",
    "games": "Games counted by the agent-written aggregate.",
    "wins": "Wins counted by the agent-written aggregate.",
    "losses": "Losses counted by the agent-written aggregate.",
}

SQL_EXEC_OUTPUT_ALIASES = {
    "TOTAL_COUNT": "n",
    "ROW_COUNT": "n",
}

def _name_entities(*fields: str) -> Callable[[Any], list[EntityRef]]:
    def extract(rows: Any) -> list[EntityRef]:
        items = rows if isinstance(rows, list) else [rows]
        found: dict[str, EntityRef] = {}
        for item in items:
            if not isinstance(item, Mapping):
                continue
            for field in fields:
                name = item.get(field)
                if isinstance(name, str) and name.strip():
                    key = name.strip().casefold()
                    if key not in found:
                        found[key] = EntityRef(
                            id=name.strip(), type="player",
                            display_name=name.strip())
        return list(found.values())
    return extract

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

def _player_entities(rows: Any) -> list[EntityRef]:
    items = rows if isinstance(rows, list) else [rows]
    found: dict[str, EntityRef] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        player_id = item.get("PLAYER_ID") or item.get("player_id")
        name = item.get("PLAYER_NAME") or item.get("PLAYER") or item.get("player")
        if player_id is None:
            continue
        ref = EntityRef(id=str(player_id), type="player",
                        display_name=str(name or player_id))
        found[ref.id] = ref
    return list(found.values())

def _team_entities(rows: Any) -> list[EntityRef]:
    items = rows if isinstance(rows, list) else [rows]
    found: dict[str, EntityRef] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        team_id = item.get("team_id")
        if team_id is None:
            team_id = item.get("TEAM_ID")
        if team_id is None:
            continue
        display = (item.get("team") or item.get("TEAM_NAME")
                   or item.get("TEAM") or team_id)
        ref = EntityRef(id=str(team_id), type="team",
                        display_name=str(display))
        found[ref.id] = ref
    return list(found.values())

@dataclass(frozen=True)
class Capability:
    name: str
    tool_name: str
    season_arg: str | None = "season"
    window_args: tuple[str, str] | None = None
    units: Mapping[str, str] = field(default_factory=dict)
    metric_definitions: Mapping[str, str] = field(default_factory=dict)
    output_aliases: Mapping[str, str] = field(default_factory=dict)
    qualification: str | None = None
    coverage: str | None = None
    source_prefix: str = "v1"
    task_season_scoped: bool = True
    live_fallback: bool = False
    extract_entities: Callable[[Any], list[EntityRef]] | None = None
    dependent_entity_arguments: Mapping[str, str] = field(default_factory=dict)
    domain: str = "basketball"
    open_vocabulary: bool = False
    publishes_declared_schema: bool = False

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
        live_fallback=True,
        units={"WINS": COUNT, "LOSSES": COUNT, "WinPCT": FRACTION,
               "PointsPG": PER_GAME, "OppPointsPG": PER_GAME,
               "DiffPointsPG": PER_GAME},
        qualification="All NBA teams in the selected regular season.",
        coverage="Full regular-season standings table.",
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
        units={"GP": COUNT, "TOTAL": COUNT, "PER_GAME": PER_GAME},
        qualification="All teams represented in deduplicated regular-season player game logs.",
        coverage="Source-ranked full team population for the selected counting stat.",
    ),
    Capability(
        name="qualified_leaders",
        tool_name="get_leaders",
        live_fallback=True,
        units={**COUNTING_UNITS, **PER_GAME_UNITS,
               "GP": COUNT, "MIN": MINUTES, "FG_PCT": FRACTION,
               "FG3_PCT": FRACTION, "FT_PCT": FRACTION},
        metric_definitions={
            "PLAYER": "Player named on the leaderboard row.",
        },
        qualification="Qualified players only (NBA leaderboard minimums).",
        coverage="Source-ranked qualified leaderboard; returned rows preserve population ranks.",
        extract_entities=_player_entities,
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
        live_fallback=True,
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
        live_fallback=True,
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
        live_fallback=True,
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
        live_fallback=True,
        extract_entities=_team_entities,
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "NET_RATING": POINTS_PER_100, "PACE": "possessions_per_48",
               "TS_PCT": PERCENT, "TM_TOV_PCT": PERCENT},
        metric_definitions={"NET_RATING": NET_RATING_DEF,
                            "TS_PCT": TS_DEF,
                            "TM_TOV_PCT": "Team turnovers per 100 possessions; lower is better."},
        qualification="All NBA teams in the selected regular season.",
        coverage="Full regular-season team rating table.",
    ),
    Capability(name="roster", tool_name="get_team_hub", live_fallback=True),
    Capability(name="player_report", tool_name="get_player_report",
               units={"GP": COUNT, "MPG": MINUTES,
                      "PPG": PER_GAME, "RPG": PER_GAME, "APG": PER_GAME,
                      "SPG": PER_GAME, "BPG": PER_GAME,
                      "FG_PCT": FRACTION, "FG3_PCT": FRACTION,
                      "FT_PCT": FRACTION, "TS_PCT": FRACTION},
               extract_entities=_player_entity,
               dependent_entity_arguments={"player": "player"}),
    Capability(name="player_evaluation", tool_name="get_player_evaluation",
               qualification="Ranks use the tool's declared qualified player pools.",
               coverage="Current-season player population represented in the warehouse.",
               extract_entities=_player_entity,
               dependent_entity_arguments={"player": "player"}),
    Capability(name="player_comparison", tool_name="get_compare",
               live_fallback=True),
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
        live_fallback=True,
        units={"TS_PCT": PERCENT, "EFG_PCT": PERCENT},
        metric_definitions={"TS_PCT": TS_DEF, "EFG_PCT": EFG_DEF},
    ),
    Capability(
        name="on_off",
        tool_name="get_on_off",
        live_fallback=True,
        units={"NET_RATING": POINTS_PER_100},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
    ),
    Capability(
        name="lineups",
        tool_name="get_lineup_stats",
        live_fallback=True,
        units={"MIN": MINUTES, "NET_RATING": POINTS_PER_100},
        metric_definitions={"NET_RATING": NET_RATING_DEF},
        qualification="Lineup sample floor applies (default 100 "
                      "possessions); smaller samples only on request.",
    ),
    Capability(
        name="clutch",
        tool_name="get_clutch",
        live_fallback=True,
        units={"GP": COUNT, "W": COUNT, "L": COUNT, "PTS": COUNT,
               "FG_PCT": FRACTION, "FG3_PCT": FRACTION,
               "PLUS_MINUS": "points"},
        metric_definitions={
            "GP": "Clutch games played.",
            "W": "Clutch wins.",
            "L": "Clutch losses.",
            "PTS": "Total clutch points.",
            "FG_PCT": "Clutch field-goal share, fraction scale 0-1.",
            "FG3_PCT": "Clutch three-point share, fraction scale 0-1.",
            "PLUS_MINUS": "Clutch point differential.",
        },
        qualification="Clutch: last 5 minutes, margin 5 or fewer.",
    ),
    Capability(name="playoffs", tool_name="get_playoffs", live_fallback=True),
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
    Capability(name="game_logs", tool_name="search_game_logs",
               window_args=("start_date", "end_date"),
               extract_entities=_player_entity,
               dependent_entity_arguments={"player": "player"}),
    Capability(
        name="four_factors",
        tool_name="get_four_factors",
        live_fallback=True,
        metric_definitions=FOUR_FACTORS_DEFS,
    ),
    Capability(
        name="team_four_factors",
        tool_name="get_team_four_factors",
        metric_definitions=FOUR_FACTORS_DEFS,
    ),
    Capability(
        name="matchup_brief",
        tool_name="get_matchup_brief",
        units={"OFF_RATING": POINTS_PER_100, "DEF_RATING": POINTS_PER_100,
               "NET_RATING": POINTS_PER_100, "PACE": "possessions_per_48",
               "win_prob": FRACTION, "projected_score": "points",
               "projected_total": "points"},
        qualification="Two named teams in the selected regular season.",
        coverage="Both teams ratings, last-10 form, injuries with impact, season-series meetings, and modeled win probability.",
    ),
    Capability(
        name="season_series",
        tool_name="get_season_series",
        qualification="Two different teams in the selected season.",
        coverage="Every regular-season and playoff meeting between the two teams with winner and scores when tracked.",
    ),
    Capability(
        name="head_to_head",
        tool_name="get_head_to_head",
        units={"gp": COUNT, "ppg": PER_GAME, "rpg": PER_GAME,
               "apg": PER_GAME, "fg_pct": FRACTION, "ts_pct": FRACTION,
               "pts": COUNT, "reb": COUNT, "ast": COUNT,
               "plus_minus": "points"},
        qualification="One resolved player against one resolved opponent team with fewer than 5 games flagged as small sample.",
        coverage="Player game logs against the opponent with vs-opponent averages next to the season baseline and deltas.",
    ),
    Capability(
        name="matchup_splits",
        tool_name="get_matchup_splits",
        live_fallback=True,
        units={"gp": COUNT, "ppg": PER_GAME, "rpg": PER_GAME,
               "apg": PER_GAME, "fg_pct": FRACTION,
               "plus_minus": "points"},
        qualification="One resolved player over the last N games with splits below 5 games flagged as low sample.",
        coverage="Situational splits over the window: defense tier, home and away, and rest days.",
    ),
    Capability(
        name="today",
        tool_name="get_today",
        qualification="Date-scoped snapshot; offseason returns honest empty lists, never fabricated games.",
        coverage="Last night results, tonight games, leaderboard movers, and streaks with scoreboard status.",
    ),
    Capability(
        name="morning_briefing",
        tool_name="get_morning_briefing",
        qualification="Date-scoped bundle; offseason sections stay honestly empty, never fabricated games.",
        coverage="Today snapshot plus watchlist updates and leaderboard deltas with scoreboard status.",
    ),
    Capability(
        name="award_results",
        tool_name="get_award_results",
        units=AWARD_UNITS,
        metric_definitions=AWARD_DEFINITIONS,
        output_aliases=AWARD_OUTPUT_ALIASES,
        extract_entities=_name_entities("player", "winner", "coach"),
        qualification=(
            "Every placement the source published on that ballot. A tied "
            "placement keeps the published leading rank and its verbatim "
            "rank_label; a null rank labelled ORV is a subject that got votes "
            "but made no team. Coach-of-the-Year rows name a coach and no "
            "player."),
        coverage=(
            "Published Basketball-Reference award ballots, 1976-77 onward, "
            "with the seasons the source publishes named per request. Never a "
            "model score, projection, or live race."),
    ),
    Capability(
        name="sql_exec",
        tool_name="sql_exec",
        open_vocabulary=True,
        publishes_declared_schema=True,
        units=SQL_EXEC_UNITS,
        metric_definitions=SQL_EXEC_DEFINITIONS,
        output_aliases=SQL_EXEC_OUTPUT_ALIASES,
        qualification=(
            "Agent-written read-only SQL for an analyst question no prebuilt "
            "tool covers. The agent supplies one SELECT or WITH statement; "
            "writes, stacked statements, and tables outside the declared "
            "set are refused before execution, results are row-capped with "
            "a statement timeout, and an empty result fails instead of "
            "publishing. The primary numeric column is named for what it "
            "measures, so the agent's own alias is the column a citation "
            "binds to."),
        coverage=(
            "Read-only analytical SQL over the declared warehouse tables, "
            "computed per query. Rows are computed from the supplied SQL, "
            "never curated table values."),
    ),
]

CAPABILITIES: dict[str, Capability] = {c.name: c for c in _LIST}

_METRIC_DISPLAY_ALIASES = {
    "ASSIST": "AST",
    "ASSISTS": "AST",
    "POINT": "PTS",
    "POINTS": "PTS",
    "REBOUND": "REB",
    "REBOUNDS": "REB",
    "OFFENSIVEREBOUND": "OREB",
    "OFFENSIVEREBOUNDS": "OREB",
    "DEFENSIVEREBOUND": "DREB",
    "DEFENSIVEREBOUNDS": "DREB",
    "STEAL": "STL",
    "STEALS": "STL",
    "BLOCK": "BLK",
    "BLOCKS": "BLK",
    "TURNOVER": "TOV",
    "TURNOVERS": "TOV",
    "FOUL": "PF",
    "FOULS": "PF",
    "GAME": "GP",
    "GAMES": "GP",
    "MINUTE": "MIN",
    "MINUTES": "MIN",
}

_AGGREGATION_SUFFIXES = ("TOTALS", "TOTAL")

_PER_GAME_STEM_SUFFIXES = ("PERGAME", "PG")

def _squashed(value: object) -> str:
    return "".join(
        character for character in str(value).upper() if character.isalnum())

def _per_game_stem(stem: str) -> str | None:
    for suffix in _PER_GAME_STEM_SUFFIXES:
        if stem.endswith(suffix) and len(stem) > len(suffix):
            return stem[: -len(suffix)]
    return None

def _per_game_column(vocabulary: Mapping[str, str], stem: str) -> str | None:
    base = _per_game_stem(stem)
    if base is None:
        return None
    for candidate in (base, _METRIC_DISPLAY_ALIASES.get(base)):
        if candidate is None:
            continue
        declared = vocabulary.get(_squashed(per_game_column(candidate)))
        if declared is not None:
            return declared
    return None

def _total_column(vocabulary: Mapping[str, str], units: Mapping[str, str],
                  squashed: str) -> str | None:
    if not squashed.startswith("TOTAL") or len(squashed) <= len("TOTAL"):
        return None
    remainder = squashed[len("TOTAL"):]
    for candidate in (remainder, _METRIC_DISPLAY_ALIASES.get(remainder)):
        if candidate is None:
            continue
        declared = vocabulary.get(candidate)
        if declared is not None and units.get(declared) == COUNT:
            return declared
    return None

def _games_column(vocabulary: Mapping[str, str], squashed: str) -> str | None:
    if squashed != "GAMESPLAYED":
        return None
    return vocabulary.get("GP")

def _name_column(vocabulary: Mapping[str, str], squashed: str) -> str | None:
    if not squashed.endswith("NAME") or len(squashed) <= len("NAME"):
        return None
    stem = squashed[: -len("NAME")]
    declared = vocabulary.get(stem)
    if declared is not None:
        return declared
    alias = _METRIC_DISPLAY_ALIASES.get(stem)
    if alias is not None:
        aliased = vocabulary.get(alias)
        if aliased is not None:
            return aliased
    return None

def resolve_metric_column(capability: Capability, output_id: str) -> str | None:
    vocabulary: dict[str, str] = {}
    for mapping in (capability.units, capability.metric_definitions):
        for key in mapping:
            vocabulary.setdefault(_squashed(key), str(key))
    squashed = _squashed(output_id)
    direct = vocabulary.get(squashed)
    if direct is not None:
        return direct
    explicit = next(
        (column for name, column in capability.output_aliases.items()
         if _squashed(name) == squashed), None)
    if explicit is not None:
        return explicit
    total = _total_column(vocabulary, capability.units, squashed)
    if total is not None:
        return total
    games = _games_column(vocabulary, squashed)
    if games is not None:
        return games
    named = _name_column(vocabulary, squashed)
    if named is not None:
        return named
    stem = squashed
    for suffix in _AGGREGATION_SUFFIXES:
        if stem.endswith(suffix) and len(stem) > len(suffix):
            stem = stem[: -len(suffix)]
            break
    stemmed = vocabulary.get(stem)
    if stemmed is not None:
        return stemmed
    per_game = _per_game_column(vocabulary, stem)
    if per_game is not None:
        return per_game
    alias = _METRIC_DISPLAY_ALIASES.get(stem)
    if alias is not None:
        aliased = vocabulary.get(alias)
        if aliased is not None:
            return aliased
    return output_id if capability.open_vocabulary else None

def _is_identity_output(output_id: str) -> bool:
    squashed = _squashed(output_id)
    return squashed.endswith("NAME") or squashed.endswith("ID")

def servable_names_for(spec: Capability) -> list[str]:
    if spec.open_vocabulary:
        return []
    names: set[str] = set()
    for key in spec.units:
        names.add(str(key).upper())
    for key in spec.metric_definitions:
        if not str(key).startswith("__"):
            names.add(str(key).upper())
    for key in spec.output_aliases:
        names.add(str(key).upper())
    return sorted(names)

def _servable_clause(spec: Capability) -> str:
    names = servable_names_for(spec)
    if names:
        return ", ".join(names)
    if spec.open_vocabulary:
        return "any column the query returns, since the capability has no fixed vocabulary"
    return "none"

def preconditions_for_node(task, node, spec: Capability) -> list:
    from ..contracts import NodePrecondition, PreconditionCheck
    requirements = {item.id: item for item in task.requirements}
    covered = [requirements[rid] for rid in node.covers_requirement_ids
               if rid in requirements]
    found: list = []
    for requirement in covered:
        outputs = [str(value) for value in
                   ([*requirement.metric_ids, *requirement.requested_outputs])]
        for output_id in outputs:
            if _is_identity_output(output_id):
                found.append(NodePrecondition(
                    check=PreconditionCheck.ENTITY, node_id=node.id,
                    requirement_id=requirement.id, output_id=output_id,
                    detail=(f"identity output {output_id!r} must resolve "
                            f"to a subject row of {spec.name!r} evidence")))
                continue
            column = resolve_metric_column(spec, output_id)
            if column is None:
                found.append(NodePrecondition(
                    check=PreconditionCheck.NUMERAL, node_id=node.id,
                    requirement_id=requirement.id, output_id=output_id,
                    resolvable=False,
                    detail=(f"output {output_id!r} does not resolve to "
                            f"{spec.name!r} vocabulary; servable: "
                            f"{_servable_clause(spec)}")))
                continue
            found.append(NodePrecondition(
                check=PreconditionCheck.NUMERAL, node_id=node.id,
                requirement_id=requirement.id, output_id=output_id,
                column=column, resolvable=True,
                detail=(f"output {output_id!r} resolves to {spec.name!r} "
                        f"column {column!r}")))
            if spec.open_vocabulary:
                continue
            unit = dict(spec.units).get(column)
            if unit is not None:
                found.append(NodePrecondition(
                    check=PreconditionCheck.UNIT, node_id=node.id,
                    requirement_id=requirement.id, output_id=output_id,
                    column=column, expected_unit=str(unit),
                    detail=(f"output {output_id!r} column {column!r} must "
                            f"carry unit {str(unit)!r}")))
    scope_requirement = covered[0].id if covered else None
    if task.entities:
        kinds = sorted({entity.type for entity in task.entities})
        found.append(NodePrecondition(
            check=PreconditionCheck.ENTITY, node_id=node.id,
            requirement_id=scope_requirement,
            detail=(f"node must serve task entities "
                    f"of kind {', '.join(kinds)}")))
    if task.season is not None:
        found.append(NodePrecondition(
            check=PreconditionCheck.SCOPE, node_id=node.id,
            requirement_id=scope_requirement,
            detail=(f"node must serve season {task.season.value}")))
    if task.window_start is not None or task.window_end is not None:
        from ..contracts import format_window
        found.append(NodePrecondition(
            check=PreconditionCheck.SCOPE, node_id=node.id,
            requirement_id=scope_requirement,
            detail=(f"node must serve window "
                    f"{format_window(task.window_start, task.window_end)}")))
    if task.as_of is not None:
        found.append(NodePrecondition(
            check=PreconditionCheck.SCOPE, node_id=node.id,
            requirement_id=scope_requirement,
            detail=(f"node must serve as-of {task.as_of.isoformat()}")))
    return found

def _row_keys_present(rows) -> set[str]:
    from ..domain.evidence import iter_values
    probe = {"evidence_id": "probe", "capability": "probe",
             "source": "probe", "observed_at": "2026-01-01T00:00:00Z",
             "rows": rows}
    try:
        from ..contracts import EvidenceEnvelope
        envelope = EvidenceEnvelope.model_validate(probe)
    except Exception:
        return set()
    keys: set[str] = set()
    for item in iter_values(envelope):
        for segment in str(item.path).split("."):
            keys.add(segment.split("[", 1)[0].casefold())
    return keys

def post_evidence_failures(preconditions: list, evidence) -> list[str]:
    from ..contracts import PreconditionCheck, precondition_repair_instruction
    failures: list[str] = []
    units = {str(key).casefold(): str(value)
             for key, value in dict(evidence.units).items()}
    for item in preconditions:
        if item.check == PreconditionCheck.NUMERAL and item.resolvable and item.column:
            present = _row_keys_present(evidence.rows)
            if item.column.casefold() not in present:
                failures.append(precondition_repair_instruction(
                    item.check, item.node_id, item.requirement_id, item.detail
                    + f"; evidence {evidence.evidence_id!r} carries no "
                    f"{item.column!r} column"))
        elif item.check == PreconditionCheck.UNIT and item.column and item.expected_unit:
            declared = units.get(item.column.casefold())
            if declared is not None and declared != item.expected_unit:
                failures.append(precondition_repair_instruction(
                    item.check, item.node_id, item.requirement_id, item.detail
                    + f"; evidence declares {declared!r}"))
    return failures

def _award_description() -> str:
    from shared.tools.award_results import AWARDS

    labels = ", ".join(
        f"{code} ({spec['label']})" for code, spec in AWARDS.items())
    return (
        "Official NBA award results recorded on published ballots: who won "
        "an award in a season, the full ranked field with award share and "
        "vote counts, and one player's award record through a season. A tied "
        "rank and an ORV row are reported as published. This is a recorded "
        "outcome, never a model score, so use it instead of any award race "
        f"for a result. The award argument is one of exactly these codes: "
        f"{labels}. Any other award, including Finals MVP, is outside this "
        "capability, so leave that requirement uncovered and let it gap "
        "rather than naming an unpublished award.")

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "entity_resolution": "Resolve a player or team name to canonical identity.",
    "warehouse_freshness": "Authoritative warehouse table freshness, cadence, row counts, and stale status.",
    "standings": "League standings for one season.",
    "team_trajectory": "Bounded multi-season regular-season records for one team.",
    "team_totals": ("Team leaderboard for a counting stat, with totals and "
                  "per-game averages. Ranks TEAMS (franchises), never "
                  "individual players; use qualified_leaders for player "
                  "questions."),
    "qualified_leaders": ("Qualified player leaderboard for one stat category; "
                          "ranks individual PLAYERS, never teams. Supports "
                          "ranking_direction and an explicit min_attempts "
                          "volume floor for percentage boards."),
    "team_splits": "Team home/away, result, last-10, and monthly records and scoring.",
    "injury_impact": "Current injuries combined with team ratings and recent form.",
    "lineup_matchups": "Observed lineup-vs-lineup shared possessions for two teams with sample flags.",
    "competitive_ratings": "Team margin performance with blowouts separated from competitive games.",
    "injuries": "Current team or player injury rows with designation and source freshness.",
    "team_shot_zones": "League or selected-team zone attempt share and efficiency with league baselines.",
    "player_shot_zones": "One player's shot-zone makes, attempts, efficiency, and attempt share.",
    "rest_splits": "Team records by zero, one, and two-plus days of rest, with sample sizes.",
    "rookie_leaders": "First-year NBA player leaderboard using prior-season exclusion, never age as a proxy.",
    "team_ratings": ("Regular-season team rating board: offensive, defensive, and net rating, "
                     "pace, true shooting percentage (TS_PCT), and team turnover percentage "
                     "(TM_TOV_PCT), with rank metadata. Ranking direction is metric-specific: "
                     "lower is better for DEF_RATING and TM_TOV_PCT; higher is better otherwise."),
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
    "matchup_brief": "Two-team matchup brief with ratings, form, injuries, season series, and win probability.",
    "season_series": "Every meeting between two teams in one season with winner and scores when tracked.",
    "head_to_head": "One player against one opponent team with vs-opponent averages next to the season baseline.",
    "matchup_splits": "Situational splits for one player over the last N games by defense tier, venue, and rest.",
    "today": "Date-scoped scoreboard snapshot with last night, tonight, movers, and streaks.",
    "morning_briefing": "Date-scoped bundle of today snapshot, watchlist updates, and leaderboard deltas.",
    "award_results": _award_description(),
    "sql_exec": (
        "Agent-written read-only SQL over the warehouse for an analyst "
        "question no prebuilt tool covers. The agent supplies one SELECT or "
        "WITH statement and the rows come back as evidence. Rows are "
        "computed from that SQL over the named tables, so the SQL is part "
        "of the evidence identity and a number from this capability never "
        "reads as a curated table value."
    ),
}

if len(CAPABILITIES) != len(_LIST):
    raise AssertionError("duplicate capability names")
if CAPABILITY_DESCRIPTIONS.keys() != CAPABILITIES.keys():
    raise AssertionError("capability descriptions must cover the catalog exactly")
for spec in CAPABILITIES.values():
    undeclared_aliases = sorted(
        target for target in spec.output_aliases.values()
        if target not in spec.units and target not in spec.metric_definitions)
    if undeclared_aliases:
        raise AssertionError(
            f"capability {spec.name} aliases undeclared outputs: "
            f"{undeclared_aliases}")
