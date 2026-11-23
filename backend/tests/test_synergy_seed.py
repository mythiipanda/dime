import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.seed_synergy as seed


def test_seed_targets_synergy_table() -> None:
    assert seed.TABLE == "silver_synergy"


def test_covers_core_play_types() -> None:
    for pt in ("prballhandler", "isolation", "postup", "spotup", "transition"):
        assert pt in seed.PLAY_TYPES


def test_season_range_and_labels() -> None:
    assert seed.FIRST_YEAR >= 2016
    assert seed.LAST_YEAR - seed.FIRST_YEAR >= seed.MIN_SEASONS - 1
    assert seed.label(2025) == "2024-25"
