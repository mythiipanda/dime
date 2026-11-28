import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.sources.cap_history import history


def test_history_covers_cap_era():
    frame = history().frame
    seasons = sorted(frame["season"].to_list())
    assert seasons[0] == 1985
    assert seasons[-1] == 2027
    assert len(seasons) >= 43


def test_anchor_values():
    frame = history().frame
    by_season = {r["season"]: r for r in frame.iter_rows(named=True)}
    assert by_season[2016]["salary_cap"] == 70_000_000
    assert by_season[2017]["salary_cap"] == 94_143_000
    assert by_season[2024]["luxury_tax"] == 165_294_000


def test_aprons_only_post_2023():
    frame = history().frame
    apron_rows = [r for r in frame.iter_rows(named=True) if r["apron_1"]]
    assert all(r["season"] >= 2024 for r in apron_rows)
    assert len(apron_rows) == 4
    row_2026 = [r for r in apron_rows if r["season"] == 2026][0]
    assert row_2026["apron_1"] == 195_945_000
    assert row_2026["apron_2"] == 207_824_000
    row_2027 = [r for r in apron_rows if r["season"] == 2027][0]
    assert row_2027["salary_cap"] == 164_961_000
    assert row_2027["luxury_tax"] == 200_428_000
    assert row_2027["apron_1"] == 209_015_000
    assert row_2027["apron_2"] == 221_686_000
    assert row_2027["season_label"] == "2026-27"


def test_era_labels_and_max_tiers():
    frame = history().frame
    by_season = {r["season"]: r for r in frame.iter_rows(named=True)}
    assert by_season[1996]["cba_era"] == "1984-cba"
    assert by_season[2005]["cba_era"] == "1999-cba"
    assert by_season[2016]["cba_era"] == "2011-cba"
    assert by_season[2026]["cba_era"] == "2023-cba"
    assert by_season[2027]["cba_era"] == "2023-cba"
    assert by_season[2016]["max_salary_tier_high_pct"] == 0.35
    assert by_season[1990]["max_salary_tier_low_pct"] is None
