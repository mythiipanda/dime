"""Desk timeout sizing (work order 2026-09-26): the outer desk-call cap must
sit at or above the desk's inner per-round budget, and stay bounded under
the overall desk wall-clock budget - never a bare magic number."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import DESK_CALL_TIMEOUT_S  # noqa: E402
from app.subagents import DESK_DEADLINE_S, LLM_ROUND_TIMEOUT_S  # noqa: E402


def test_outer_cap_at_or_above_inner_round_budget():
    # A single slow NIM round may legitimately take up to the inner
    # round budget; the outer cap must not kill the desk call first.
    assert DESK_CALL_TIMEOUT_S >= LLM_ROUND_TIMEOUT_S


def test_outer_cap_stays_bounded_under_desk_deadline():
    # The cap stays a cap: below the overall desk wall-clock budget so
    # the turn budget still binds.
    assert DESK_CALL_TIMEOUT_S <= DESK_DEADLINE_S


def test_budgets_are_positive_finite():
    import math

    for v in (DESK_CALL_TIMEOUT_S, LLM_ROUND_TIMEOUT_S, DESK_DEADLINE_S):
        assert math.isfinite(v) and v > 0
