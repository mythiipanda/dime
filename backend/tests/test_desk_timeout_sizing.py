
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import DESK_CALL_TIMEOUT_S  # noqa: E402
from app.subagents import DESK_DEADLINE_S, LLM_ROUND_TIMEOUT_S  # noqa: E402


def test_outer_cap_at_or_above_inner_round_budget():
    assert DESK_CALL_TIMEOUT_S >= LLM_ROUND_TIMEOUT_S


def test_outer_cap_stays_bounded_under_desk_deadline():
    assert DESK_CALL_TIMEOUT_S <= DESK_DEADLINE_S


def test_budgets_are_positive_finite():
    import math

    for v in (DESK_CALL_TIMEOUT_S, LLM_ROUND_TIMEOUT_S, DESK_DEADLINE_S):
        assert math.isfinite(v) and v > 0
