import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from backend.scripts.seed_hist_pbp import PATTERN, parse_years


def test_pattern_matches_sdv_asset_names():
    assert PATTERN.format(y=2008) == "nba_play_by_play_2008.parquet"


def test_parse_years_allows_deep_history():
    years = parse_years("1997,2000,2008,2015")
    assert years == [1997, 2000, 2008, 2015]


def test_parse_years_rejects_out_of_range():
    with pytest.raises(SystemExit):
        parse_years("1996")
    with pytest.raises(SystemExit):
        parse_years("2026")
