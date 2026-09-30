import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _ledger_leader_answer  # noqa: E402


TOTALS_2425 = (
    "Zoran Vexley leads the league with 812 assists "
    "in 74 games (10.97 assists per game) in 2024-25."
)
TOTALS_2324 = (
    "Miro Kessler leads the league with 795 assists "
    "in 71 games (11.20 assists per game) in 2023-24."
)
RATE_2425 = (
    "Zoran Vexley leads at 11.24 assists per game in 2024-25 (74 games)."
)
RATE_2324 = (
    "Miro Kessler leads at 11.02 assists per game in 2023-24 (71 games)."
)


def test_wrong_season_totals_fact_is_not_reused():
    out = _ledger_leader_answer(
        "Who led the league in assists in 2023-24?", [TOTALS_2425])
    assert out is None


def test_matching_season_totals_fact_is_reused():
    out = _ledger_leader_answer(
        "Who led the league in assists in 2024-25?", [TOTALS_2425])
    assert out == TOTALS_2425


def test_wrong_season_rate_fact_is_not_reused():
    out = _ledger_leader_answer(
        "Who averaged the most assists per game in 2023-24?", [RATE_2425])
    assert out is None


def test_matching_season_rate_fact_is_reused():
    out = _ledger_leader_answer(
        "Who averaged the most assists per game in 2024-25?", [RATE_2425])
    assert out == RATE_2425


def test_newest_matching_season_fact_wins():
    out = _ledger_leader_answer(
        "Who led the league in assists in 2023-24?",
        [TOTALS_2425, TOTALS_2324])
    assert out == TOTALS_2324


def test_rate_question_does_not_reuse_totals_scope():
    out = _ledger_leader_answer(
        "Who averaged the most assists per game in 2024-25?", [TOTALS_2425])
    assert out is None


def test_totals_question_does_not_reuse_rate_scope():
    out = _ledger_leader_answer(
        "Who led the league in assists in 2023-24?", [RATE_2324])
    assert out is None
