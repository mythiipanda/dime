import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.seed_player_bio as seed


def test_seed_targets_bio_table() -> None:
    assert seed.TABLE == "silver_player_bio"


def test_keeps_international_and_draft_columns() -> None:
    for c in ("birth_country", "birth_city", "draft_year", "college_id"):
        assert c in seed.KEEP


def test_season_range_and_labels() -> None:
    assert seed.FIRST_YEAR >= 1994
    assert seed.LAST_YEAR - seed.FIRST_YEAR >= seed.MIN_SEASONS - 1
    assert seed.label(2000) == "1999-00"
