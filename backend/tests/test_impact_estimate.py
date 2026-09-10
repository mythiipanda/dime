"""get_impact_estimate tests. Warehouse-backed and hermetic: the estimator
reads only the local warehouse, and the RAPTOR-ballpark test pins its
tolerance to the blend's measured p95 residual (2.16 -> tolerance 2.5),
not to an exact reconstruction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import TOOL_NAMES, get_impact_estimate
from app.tools.player import (
    IMPACT_RAPTOR_ONOFF_W,
    _fit_box_prior,
    _solve_linear,
)

# Documented tolerance: the 80/20 empirical blend reconstructs RAPTOR_TOTAL
# with p95 residual 2.16 per 100 possessions (fitted 2026-09-10, n=4684).
RAPTOR_BLEND_TOLERANCE = 2.5


def test_registered_in_v1_tools():
    assert "get_impact_estimate" in TOOL_NAMES


def test_solve_linear_2x2():
    x = _solve_linear([[2.0, 1.0], [1.0, 3.0]], [5.0, 6.0])
    assert x is not None
    assert abs(x[0] - 1.8) < 1e-9
    assert abs(x[1] - 1.4) < 1e-9


def test_solve_linear_singular_returns_none():
    assert _solve_linear([[1.0, 2.0], [2.0, 4.0]], [3.0, 6.0]) is None


def test_raptor_covered_player_within_documented_tolerance():
    out = get_impact_estimate.invoke(
        {"player": "LeBron James", "season": "2021-22"})
    assert out["ok"] is True
    assert out["is_estimate"] is True
    assert out["method"] == "raptor_components"
    assert out["disclaimer"].startswith("This is a statistical estimate")
    measured = out["measured"]["total_per_100"]
    assert abs(out["estimate_per_100"] - measured) <= RAPTOR_BLEND_TOLERANCE
    comps = out["components"]
    assert comps["onoff_weight"] == IMPACT_RAPTOR_ONOFF_W
    assert comps["raptor_box_per_100"] is not None
    assert comps["raptor_onoff_per_100"] is not None


def test_raptor_covered_second_player_ballpark():
    out = get_impact_estimate.invoke(
        {"player": "Stephen Curry", "season": "2021-22"})
    assert out["ok"] is True
    assert abs(out["estimate_per_100"]
               - out["measured"]["total_per_100"]) <= RAPTOR_BLEND_TOLERANCE


def test_current_season_no_coverage_returns_flagged_estimate():
    out = get_impact_estimate.invoke(
        {"player": "Cooper Flagg", "season": "2025-26"})
    assert out["ok"] is True
    assert out["is_estimate"] is True
    assert out["method"] == "box_prior_shrinkage"
    assert out["measured"] is None
    assert isinstance(out["estimate_per_100"], float)
    assert any("RAPTOR" in n and "frozen" in n
               for n in out["confidence"]["notes"])
    comps = out["components"]
    assert comps["box_prior"]["fitted"] is True
    assert 0.0 <= comps["box_prior"]["r2"] <= 1.0


def test_low_minute_player_is_prior_dominated():
    out = get_impact_estimate.invoke(
        {"player": "Tristen Newton", "season": "2025-26"})
    assert out["ok"] is True
    assert out["components"]["prior_weight"] > 0.5
    assert out["confidence"]["level"] == "low"
    assert any("Prior-dominated" in n for n in out["confidence"]["notes"])


def test_high_minute_player_is_measured_dominated():
    out = get_impact_estimate.invoke(
        {"player": "Nikola Jokic", "season": "2025-26"})
    assert out["ok"] is True
    assert out["components"]["measured_weight"] > 0.5
    assert out["confidence"]["level"] == "high"


def test_veteran_gets_stale_raptor_context():
    out = get_impact_estimate.invoke(
        {"player": "Nikola Jokic", "season": "2025-26"})
    stale = out["stale_measured"]
    assert stale is not None
    assert stale["metric"] == "RAPTOR"
    assert stale["season"] < "2025-26"
    assert "not used in the estimate" in stale["note"]


def test_rookie_has_no_stale_raptor():
    out = get_impact_estimate.invoke(
        {"player": "Cooper Flagg", "season": "2025-26"})
    assert out["ok"] is True
    assert out["stale_measured"] is None


def test_unknown_player_clean_error():
    out = get_impact_estimate.invoke(
        {"player": "Zzz Notaplayer", "season": "2025-26"})
    assert out["ok"] is False
    assert "unknown player" in out["error"]
    assert out["is_estimate"] is True


def test_box_prior_fit_diagnostics_sane():
    prior = _fit_box_prior("2025-26")
    assert prior is not None
    assert prior["n"] >= 30
    assert 0.0 <= prior["r2"] <= 1.0
    assert set(prior["coefs"]) == {"USG_PCT", "TS_PCT", "AST_PCT",
                                   "REB_PCT", "TM_TOV_PCT"}
