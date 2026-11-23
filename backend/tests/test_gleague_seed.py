import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.seed_gleague_history as seed


def test_seed_targets_gleague_table() -> None:
    assert seed.TABLE == "silver_gleague_season"


def test_season_range() -> None:
    ss = seed.seasons()
    assert "2007-08" in ss and "2025-26" in ss
    assert len(ss) >= seed.MIN_SEASONS
