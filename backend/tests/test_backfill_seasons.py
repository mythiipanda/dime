import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backfill
from shared.tools._core import completed_season_for_date


def test_default_backfill_range_covers_last_completed_season():
    frontier = completed_season_for_date(dt.date.today())
    assert frontier is not None
    assert frontier in backfill.parse_seasons(backfill.DEFAULT_SEASONS)
