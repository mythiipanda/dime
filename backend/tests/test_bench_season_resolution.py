"""Golden season-resolution task family.

The 2026-09-27 bug class: a question naming one explicit past season
("2024-25 TS%") answered with the current season's numbers. The golden set
is fixed curated questions; ground truth is computed from the warehouse
for the NAMED season, so numeric_acc scores a wrong-season answer 0.

Hermetic: _tables/_qd are monkeypatched; no warehouse, no LLM, no network.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bench.ground as ground  # noqa: E402
from bench.ground import SkipTask  # noqa: E402
from bench.scoring import numeric_acc  # noqa: E402

_CANNED = {
    ("BOS", "2024-25"): {"gp": 82, "wins": 61, "pts": 9534,
                         "fga": 7400, "fta": 1600},
    ("OKC", "2024-25"): {"gp": 82, "wins": 68, "pts": 9800,
                         "fga": 7500, "fta": 1500},
    ("LAL", "2023-24"): {"gp": 82, "wins": 47, "pts": 9680,
                         "fga": 7300, "fta": 1700},
}


def _patch(monkeypatch):
    monkeypatch.setattr(ground, "_tables",
                        lambda: {"silver_hist_gamelogs"})

    def fake_qd(sql, params=None):
        abbr, season = params[0], params[1]
        return [dict(_CANNED[(abbr, season)])]

    monkeypatch.setattr(ground, "_qd", fake_qd)


def _ctx(idx):
    return {"task_id": f"season_resolution-{idx}-7",
            "seed": 7, "timeout_s": 180}


def test_golden_cycles_in_order(monkeypatch):
    _patch(monkeypatch)
    task0, truth0 = ground.gen_season_resolution(None, _ctx(0))
    assert "Boston Celtics" in task0.question
    assert "true shooting" in task0.question
    assert truth0.facts["ts_pct"] == pytest.approx(58.8, abs=0.05)
    task1, truth1 = ground.gen_season_resolution(None, _ctx(1))
    assert "Oklahoma City Thunder" in task1.question
    assert truth1.facts["wins"] == 68
    task8, truth8 = ground.gen_season_resolution(None, _ctx(8))
    assert task8.question == task0.question
    assert truth8.facts == truth0.facts


def test_question_names_explicit_past_season(monkeypatch):
    _patch(monkeypatch)
    for idx in (0, 1, 2):
        task, _ = ground.gen_season_resolution(None, _ctx(idx))
        assert "2024-25" in task.question or "2023-24" in task.question
        assert "2025-26" not in task.question


def test_ppg_template(monkeypatch):
    _patch(monkeypatch)
    task, truth = ground.gen_season_resolution(None, _ctx(2))
    assert "Los Angeles Lakers" in task.question
    assert "points per game" in task.question
    assert truth.facts["ppg"] == pytest.approx(9680 / 82, abs=0.05)


def test_skips_without_hist_table(monkeypatch):
    monkeypatch.setattr(ground, "_tables", lambda: set())
    with pytest.raises(SkipTask):
        ground.gen_season_resolution(None, _ctx(0))


def test_skips_without_games(monkeypatch):
    monkeypatch.setattr(ground, "_tables",
                        lambda: {"silver_hist_gamelogs"})
    monkeypatch.setattr(ground, "_qd",
                        lambda sql, params=None: [{"gp": 0, "wins": 0,
                                                   "pts": 0, "fga": 0,
                                                   "fta": 0}])
    with pytest.raises(SkipTask):
        ground.gen_season_resolution(None, _ctx(0))


def test_wrong_season_answer_scores_zero():
    # The bug, encoded: 2024-25 truth is 58.8, model answers 2025-26's 60.4.
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted a 60.4% true shooting mark in 2025-26.",
    ) == 0.0


def test_correct_season_answer_scores_one():
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "Boston's true shooting percentage was 58.8% in 2024-25.",
    ) == 1.0


def test_right_number_wrong_season_phrasing_scores_zero():
    # Instinct QA 2026-09-27 repro: numeric_acc stripped season strings,
    # so the right number with explicit wrong-season phrasing scored 1.0.
    assert numeric_acc(
        {"ts_pct": 58.8, "season": "2024-25"},
        "The Celtics posted a 58.8% true shooting mark in the "
        "2025-26 regular season.",
    ) == 0.0


def test_facts_carry_named_season(monkeypatch):
    _patch(monkeypatch)
    _, truth = ground.gen_season_resolution(None, _ctx(0))
    assert truth.facts["season"] == "2024-25"
    _, truth2 = ground.gen_season_resolution(None, _ctx(2))
    assert truth2.facts["season"] == "2023-24"
