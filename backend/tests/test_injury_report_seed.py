import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.seed_injury_report as seed


def test_seed_targets_injury_report_table() -> None:
    assert seed.TABLE == "silver_injury_report"


def test_season_range_and_labels() -> None:
    assert seed.FIRST_YEAR >= 2019
    assert seed.LAST_YEAR - seed.FIRST_YEAR >= seed.MIN_SEASONS - 1
    assert seed.label(2024) == "2023-24"
