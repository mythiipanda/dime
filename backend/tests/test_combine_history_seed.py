import re

import scripts.seed_combine_history as seed


def test_seed_targets_combine_table() -> None:
    assert seed.TABLE == "silver_combine"


def test_season_range_covers_modern_era() -> None:
    assert seed.FIRST_YEAR <= 2000
    assert seed.LAST_YEAR >= 2025
    assert seed.LAST_YEAR - seed.FIRST_YEAR >= seed.MIN_SEASONS
