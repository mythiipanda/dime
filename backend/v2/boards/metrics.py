from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Literal


Category = Literal["Scoring", "Efficiency", "Playmaking", "Rebounding", "Defense", "Impact", "Contract"]
Unit = Literal["per_game", "pct", "rating", "usd", "count"]


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    category: Category
    unit: Unit
    table: str
    column: str
    higher_is_better: bool
    definition: str

    def public(self) -> dict:
        return asdict(self)


_BASE = "silver_player_season"
_ADV = "silver_advanced"


def _metric(id: str, label: str, category: Category, unit: Unit, table: str,
            column: str, definition: str, higher_is_better: bool = True) -> Metric:
    return Metric(id, label, category, unit, table, column, higher_is_better, definition)


METRICS = MappingProxyType({metric.id: metric for metric in (
    _metric("gp", "Games played", "Impact", "count", _BASE, "GP", "Games played in the selected season."),
    _metric("mpg", "Minutes", "Impact", "per_game", _BASE, "MPG", "Minutes played per game."),
    _metric("ppg", "Points", "Scoring", "per_game", _BASE, "PPG", "Points per game."),
    _metric("rpg", "Rebounds", "Rebounding", "per_game", _BASE, "RPG", "Total rebounds per game."),
    _metric("apg", "Assists", "Playmaking", "per_game", _BASE, "APG", "Assists per game."),
    _metric("spg", "Steals", "Defense", "per_game", _BASE, "SPG", "Steals per game."),
    _metric("bpg", "Blocks", "Defense", "per_game", _BASE, "BPG", "Blocks per game."),
    _metric("fg_pct", "FG%", "Efficiency", "pct", _BASE, "FG_PCT", "Field goals made / attempted, on a 0–100 scale."),
    _metric("fg3_pct", "3P%", "Efficiency", "pct", _BASE, "FG3_PCT", "Three-pointers made / attempted, on a 0–100 scale."),
    _metric("ft_pct", "FT%", "Efficiency", "pct", _BASE, "FT_PCT", "Free throws made / attempted, on a 0–100 scale."),
    _metric("ts_pct", "TS%", "Efficiency", "pct", _ADV, "TS_PCT", "True shooting percentage, on a 0–100 scale."),
    _metric("efg_pct", "eFG%", "Efficiency", "pct", _ADV, "EFG_PCT", "Effective field goal percentage, on a 0–100 scale."),
    _metric("usg_pct", "Usage", "Scoring", "pct", _ADV, "USG_PCT", "Share of team possessions used, on a 0–100 scale."),
    _metric("ast_pct", "Assist share", "Playmaking", "pct", _ADV, "AST_PCT", "Share of teammate field goals assisted, on a 0–100 scale."),
    _metric("reb_pct", "Rebound share", "Rebounding", "pct", _ADV, "REB_PCT", "Share of available rebounds collected, on a 0–100 scale."),
    _metric("oreb_pct", "Offensive rebound share", "Rebounding", "pct", _ADV, "OREB_PCT", "Share of available offensive rebounds collected, on a 0–100 scale."),
    _metric("dreb_pct", "Defensive rebound share", "Rebounding", "pct", _ADV, "DREB_PCT", "Share of available defensive rebounds collected, on a 0–100 scale."),
    _metric("off_rating", "Offensive rating", "Impact", "rating", _ADV, "OFF_RATING", "Team points scored per 100 possessions while on court."),
    _metric("def_rating", "Defensive rating", "Defense", "rating", _ADV, "DEF_RATING", "Team points allowed per 100 possessions while on court.", False),
    _metric("net_rating", "Net rating", "Impact", "rating", _ADV, "NET_RATING", "Offensive rating minus defensive rating."),
    _metric("pie", "PIE", "Impact", "pct", _ADV, "PIE", "Player impact estimate, on a 0–100 scale."),
    _metric("pace", "Pace", "Impact", "rating", _ADV, "PACE", "Estimated possessions per 48 minutes while on court."),
    _metric("ast_to", "Assist / turnover", "Playmaking", "rating", _ADV, "AST_TO", "Assists per turnover."),
    _metric("tov_pct", "Turnover rate", "Playmaking", "pct", _ADV, "TM_TOV_PCT", "Turnovers per 100 possessions; already stored on a 0–100 scale.", False),
    _metric("salary_2026_27", "2026–27 salary", "Contract", "usd", "silver_cap_players", "salary", "2026–27 salary in USD, matched only by an unambiguous normalized full name.", False),
)})
