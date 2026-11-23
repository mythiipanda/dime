import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

import scripts.seed_early_draft as seed


def test_seed_targets_hist_draft() -> None:
    assert seed.TABLE == "silver_hist_draft"


def test_label_maps_draft_year_to_season() -> None:
    assert seed.label(1947) == "1947-48"
    assert seed.label(1984) == "1984-85"
    assert seed.label(1995) == "1995-96"


def _frame() -> pl.DataFrame:
    return pl.DataFrame({
        "PERSON_ID": [893, 78049],
        "PLAYER_NAME": ["Michael Jordan", "Bill Russell"],
        "SEASON": ["1984", "1956"],
        "ROUND_NUMBER": [1, 1],
        "ROUND_PICK": [3, 2],
        "OVERALL_PICK": [3, 2],
        "DRAFT_TYPE": ["Draft", "Draft"],
        "TEAM_ID": [1610612741, 1610612738],
        "TEAM_CITY": ["Chicago", "Boston"],
        "TEAM_NAME": ["Bulls", "Celtics"],
        "TEAM_ABBREVIATION": ["CHI", "BOS"],
        "ORGANIZATION": ["North Carolina", "San Francisco"],
        "ORGANIZATION_TYPE": ["College/University", "College/University"],
        "PLAYER_PROFILE_FLAG": [1, 1],
    })


def test_run_maps_draft_year_and_saves(monkeypatch, tmp_path) -> None:
    saved = {}

    class _Store:
        @staticmethod
        def connect(read_only=True):
            raise RuntimeError("no db")

        @staticmethod
        def save_frame(table, res, entity, replace_season):
            saved[res.meta.season] = res.frame
            return res.frame.height

    monkeypatch.setattr(seed, "store", _Store)
    n = seed.run([1956, 1984], frame=_frame())
    assert n == 2
    assert saved["1956-57"]["PLAYER_NAME"].to_list() == ["Bill Russell"]
    assert saved["1984-85"]["DRAFT_YEAR"].to_list() == [1984]
    assert saved["1984-85"]["SEASON"].to_list() == [1985]
