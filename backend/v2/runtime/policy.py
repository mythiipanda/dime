from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

class ExecutionMode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"
    EVAL = "eval"
    SHADOW = "shadow"

class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ExecutionMode
    max_concurrency: StrictInt = Field(default=4, ge=1, le=16)
    max_failures: StrictInt = Field(default=2, ge=1, le=10)
    repair_attempts: StrictInt = Field(default=1, ge=0, le=2)
    ledger_dir: Path | None = None
    checkpoint_dir: Path | None = None
    replay_path: Path | None = None
    publish: StrictBool = True

    @model_validator(mode="after")
    def validate_mode(self) -> "ExecutionPolicy":
        if self.mode == ExecutionMode.REPLAY and self.replay_path is None:
            raise ValueError("replay mode requires replay_path")
        if self.mode != ExecutionMode.REPLAY and self.replay_path is not None:
            raise ValueError("replay_path is valid only in replay mode")
        if self.mode != ExecutionMode.LIVE and self.publish:
            raise ValueError(f"{self.mode.value} mode cannot publish")
        for field_name in ("ledger_dir", "checkpoint_dir", "replay_path"):
            path = getattr(self, field_name)
            if path is None:
                continue
            if path.is_symlink():
                raise ValueError(f"{field_name} cannot be a symlink")
            parent = path.parent
            if any(component.is_symlink() for component in (parent, *parent.parents)):
                raise ValueError(f"{field_name} parent cannot be a symlink")
        return self

    @classmethod
    def live(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.LIVE, ledger_dir=ledger_dir)

    @classmethod
    def shadow(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.SHADOW, ledger_dir=ledger_dir, publish=False)

    @classmethod
    def evaluation(cls, *, ledger_dir: str | Path | None = None) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.EVAL, ledger_dir=ledger_dir, publish=False)

    @classmethod
    def replay(cls, path: str | Path) -> "ExecutionPolicy":
        return cls(mode=ExecutionMode.REPLAY, replay_path=path, publish=False)

LOOKUP_PROFILE = "lookup"
STANDARD_PROFILE = "standard"
FULL_PROFILE = "full"

_WEB_CAPABILITIES = frozenset({"web_search", "web_fetch"})

_FULL_ALLOWLIST = frozenset({
    "entity_resolution", "warehouse_freshness", "standings", "team_trajectory",
    "team_totals", "qualified_leaders", "team_splits", "injury_impact",
    "lineup_matchups", "competitive_ratings", "injuries", "team_shot_zones",
    "player_shot_zones", "rest_splits", "rookie_leaders", "team_ratings",
    "roster", "player_report", "player_evaluation", "player_comparison",
    "metric_adjudication", "metric_coverage", "shots", "shooting_efficiency",
    "on_off", "lineups", "clutch", "playoffs", "player_ratings",
    "playoff_team_ratings", "trades", "trade_value", "contracts",
    "game_prediction", "game_logs", "four_factors", "team_four_factors",
    "matchup_brief", "season_series", "head_to_head", "matchup_splits",
    "today", "morning_briefing", "award_results", "sql_exec",
    "web_search", "web_fetch",
})

_QUICK_DENIED = frozenset({
    "web_search", "web_fetch", "player_comparison", "metric_adjudication",
    "trades", "trade_value", "lineup_matchups",
})

_STANDARD_DENIED = frozenset({"web_search", "web_fetch"})

_PROFILE_BY_MODE_VALUE = {
    "quick": LOOKUP_PROFILE,
    "deep_dive": STANDARD_PROFILE,
    "project": FULL_PROFILE,
}

_DENIED_BY_PROFILE = {
    LOOKUP_PROFILE: _QUICK_DENIED,
    STANDARD_PROFILE: _STANDARD_DENIED,
    FULL_PROFILE: frozenset(),
}

def capability_universe() -> frozenset[str]:
    from v2.adapters.capabilities import CAPABILITIES
    return frozenset(CAPABILITIES) | _WEB_CAPABILITIES

def _mode_value(mode: object) -> str:
    value = getattr(mode, "value", mode)
    return str(value)

def task_mode_profile(mode: object) -> str:
    try:
        return _PROFILE_BY_MODE_VALUE[_mode_value(mode)]
    except KeyError:
        raise ValueError(f"unknown task mode {mode!r}") from None

def allowed_capabilities_for_task_mode(mode: object) -> frozenset[str]:
    profile = task_mode_profile(mode)
    universe = capability_universe()
    stale = set(_FULL_ALLOWLIST) - set(universe)
    if stale:
        raise ValueError(
            f"mode profiles name retired capabilities: {sorted(stale)}")
    unprofiled = set(universe) - set(_FULL_ALLOWLIST)
    if unprofiled:
        raise ValueError(
            f"mode profiles miss registry capabilities: {sorted(unprofiled)}; "
            "profile each new capability before use")
    return frozenset(set(_FULL_ALLOWLIST) - set(_DENIED_BY_PROFILE[profile]))

def refuse_unprofiled_capability(
    mode: object, node_id: str, capability: str,
) -> None:
    allowed = allowed_capabilities_for_task_mode(mode)
    if capability in allowed:
        return
    if capability not in capability_universe():
        return
    profile = task_mode_profile(mode)
    raise ValueError(
        f"plan node {node_id!r} uses capability {capability!r}, which mode "
        f"{_mode_value(mode)!r} profile {profile!r} denies; "
        f"allowed: {sorted(allowed)}")
