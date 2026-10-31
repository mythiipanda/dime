from __future__ import annotations

import polars as pl
import pytest

from scripts.seed_player_season_stats import (
    BASE_COLS,
    ADV_COLS,
    label,
    transform_player_season_stats,
)


def _base_row(**kwargs):
    row = {
        "season_type": "regular-season",
        "per_mode": "pergame",
        "measure_type": "base",
        "player_id": 1,
        "player_name": "Player One",
        "team_abbreviation": "OKC",
        "season": 2025,
        "age": 25,
        "gp": 70,
        "min": 30.0,
        "pts": 20.0,
        "reb": 5.0,
        "ast": 5.0,
        "stl": 1.0,
        "blk": 0.5,
        "tov": 2.0,
        "fgm": 7.0,
        "fga": 15.0,
        "fg_pct": 0.467,
        "fg3m": 2.0,
        "fg3a": 5.0,
        "fg3_pct": 0.400,
        "ftm": 4.0,
        "fta": 5.0,
        "ft_pct": 0.800,
    }
    row.update(kwargs)
    return row


def _adv_row(**kwargs):
    row = {
        "season_type": "regular-season",
        "per_mode": "pergame",
        "measure_type": "advanced",
        "player_id": 1,
        "season": 2025,
        "ts_pct": 0.580,
        "efg_pct": 0.530,
        "usg_pct": 0.250,
        "off_rating": 110.0,
        "def_rating": 105.0,
        "net_rating": 5.0,
        "pie": 0.150,
        "pace": 100.0,
    }
    row.update(kwargs)
    return row


def _tot_row(**kwargs):
    row = {
        "season_type": "regular-season",
        "per_mode": "totals",
        "measure_type": "base",
        "player_id": 1,
        "season": 2025,
        "gp": 70,
        "pts": 1400.0,
        "reb": 350.0,
        "ast": 350.0,
    }
    row.update(kwargs)
    return row


@pytest.fixture()
def synthetic_season_feed() -> pl.DataFrame:
    """Synthetic feed with base, adv, tot matching sportsdataverse schema."""
    rows = [
        # SGA
        _base_row(
            player_id=1628983,
            player_name="Shai Gilgeous-Alexander",
            team_abbreviation="OKC",
            season=2025,
            age=26,
            gp=76,
            min=34.2,
            pts=32.7,
            reb=5.0,
            ast=6.4,
            stl=1.7,
            blk=1.0,
            tov=2.5,
            fgm=11.0,
            fga=21.0,
            fg_pct=0.524,
            fg3m=2.1,
            fg3a=5.6,
            fg3_pct=0.375,
            ftm=8.6,
            fta=9.8,
            ft_pct=0.878,
        ),
        _adv_row(
            player_id=1628983,
            season=2025,
            ts_pct=0.637,
            efg_pct=0.574,
            usg_pct=0.332,
            off_rating=118.5,
            def_rating=105.2,
            net_rating=13.3,
            pie=0.201,
            pace=101.4,
        ),
        _tot_row(
            player_id=1628983,
            season=2025,
            gp=76,
            pts=2484.0,
            reb=379.0,
            ast=486.0,
        ),
        # De'Aaron Fox - Traded player
        _base_row(
            player_id=1628368,
            player_name="De'Aaron Fox",
            team_abbreviation="SAS",
            season=2025,
            age=27,
            gp=62,
            min=33.1,
            pts=23.5,
            reb=4.1,
            ast=6.3,
            stl=1.4,
            blk=0.3,
            tov=2.7,
            fgm=8.5,
            fga=18.0,
            fg_pct=0.472,
            fg3m=1.9,
            fg3a=5.4,
            fg3_pct=0.352,
            ftm=4.6,
            fta=6.2,
            ft_pct=0.742,
        ),
        _adv_row(
            player_id=1628368,
            season=2025,
            ts_pct=0.560,
            efg_pct=0.525,
            usg_pct=0.280,
            off_rating=112.0,
            def_rating=110.0,
            net_rating=2.0,
            pie=0.145,
            pace=99.8,
        ),
        _tot_row(
            player_id=1628368,
            season=2025,
            gp=62,
            pts=1459.0,
            reb=254.0,
            ast=391.0,
        ),
        # Missing Totals Player
        _base_row(
            player_id=99999,
            player_name="Missing Totals Player",
            team_abbreviation="MIA",
            season=2025,
            gp=10,
            pts=6.5,
        ),
        _adv_row(
            player_id=99999,
            season=2025,
            ts_pct=0.540,
        ),
        # Playoffs row (should be filtered out)
        _base_row(
            player_id=1628983,
            season_type="playoffs",
            season=2025,
            pts=30.0,
        ),
    ]
    return pl.DataFrame(rows)


def test_transform_preserves_rates_and_adds_exact_totals(
        synthetic_season_feed: pl.DataFrame) -> None:
    merged = transform_player_season_stats(synthetic_season_feed)
    assert merged.height == 3
    assert set(merged["player_id"].to_list()) == {1628983, 1628368, 99999}

    sga = merged.filter(pl.col("player_id") == 1628983).to_dicts()[0]
    assert sga["pts"] == 32.7
    assert sga["reb"] == 5.0
    assert sga["ast"] == 6.4
    assert sga["gp"] == 76
    assert sga["min"] == 34.2
    assert sga["ts_pct"] == 0.637

    assert sga["pts_total"] == 2484.0
    assert sga["reb_total"] == 379.0
    assert sga["ast_total"] == 486.0
    assert sga["gp_total"] == 76
    assert sga["pts"] * sga["gp"] != sga["pts_total"]


def test_transform_handles_missing_totals_as_null(
        synthetic_season_feed: pl.DataFrame) -> None:
    merged = transform_player_season_stats(synthetic_season_feed)
    missing = merged.filter(pl.col("player_id") == 99999).to_dicts()[0]
    assert missing["pts"] == 6.5
    assert missing["gp"] == 10
    assert missing["pts_total"] is None
    assert missing["reb_total"] is None
    assert missing["ast_total"] is None
    assert missing["gp_total"] is None


def test_transform_handles_entirely_empty_totals() -> None:
    """Missing totals entire rows is valid and naturally empty totals select keeps schema/null."""
    feed = pl.DataFrame([
        _base_row(player_id=1, pts=18.0),
        _adv_row(player_id=1, ts_pct=0.550),
    ])
    merged = transform_player_season_stats(feed)
    assert merged.height == 1
    row = merged.to_dicts()[0]
    assert row["player_id"] == 1
    assert row["pts"] == 18.0
    assert row["ts_pct"] == 0.550
    assert row["pts_total"] is None
    assert row["reb_total"] is None
    assert row["ast_total"] is None
    assert row["gp_total"] is None


def test_transform_traded_player_aggregation(
        synthetic_season_feed: pl.DataFrame) -> None:
    merged = transform_player_season_stats(synthetic_season_feed)
    fox_rows = merged.filter(pl.col("player_id") == 1628368).to_dicts()
    assert len(fox_rows) == 1
    fox = fox_rows[0]
    assert fox["team_abbreviation"] == "SAS"
    assert fox["gp"] == 62
    assert fox["gp_total"] == 62
    assert fox["pts"] == 23.5
    assert fox["pts_total"] == 1459.0
    assert fox["ts_pct"] == 0.560


def test_transform_retains_both_gp_contexts() -> None:
    feed = pl.DataFrame([
        _base_row(player_id=1, season=2025, gp=50, pts=20.0),
        _adv_row(player_id=1, season=2025),
        _tot_row(player_id=1, season=2025, gp=52, pts=1040.0),
    ])
    merged = transform_player_season_stats(feed)
    row = merged.to_dicts()[0]
    assert row["gp"] == 50
    assert row["gp_total"] == 52
    assert row["pts_total"] == 1040.0


def test_transform_filters_phase() -> None:
    feed = pl.DataFrame([
        _base_row(player_id=1, season_type="playoffs"),
        _base_row(player_id=2, season_type="preseason"),
        _base_row(player_id=3, season_type="regular-season"),
        _adv_row(player_id=3, season_type="regular-season"),
        _tot_row(player_id=3, season_type="regular-season"),
    ])
    merged = transform_player_season_stats(feed)
    assert merged.height == 1
    assert merged["player_id"].to_list() == [3]


def test_transform_multiseason_isolation() -> None:
    """Prove two seasons for same player isolate advanced TS% and totals via [player_id, season]."""
    feed = pl.DataFrame([
        _base_row(player_id=1, season=2024, gp=70, pts=20.0),
        _adv_row(player_id=1, season=2024, ts_pct=0.550),
        _tot_row(player_id=1, season=2024, gp=70, pts=1400.0, reb=350.0, ast=350.0),
        _base_row(player_id=1, season=2025, gp=76, pts=25.0),
        _adv_row(player_id=1, season=2025, ts_pct=0.620),
        _tot_row(player_id=1, season=2025, gp=76, pts=1900.0, reb=400.0, ast=450.0),
    ])
    merged = transform_player_season_stats(feed).sort("season")
    assert merged.height == 2
    r2024, r2025 = merged.to_dicts()

    assert r2024["season"] == 2024
    assert r2024["pts"] == 20.0
    assert r2024["ts_pct"] == 0.550
    assert r2024["pts_total"] == 1400.0

    assert r2025["season"] == 2025
    assert r2025["pts"] == 25.0
    assert r2025["ts_pct"] == 0.620
    assert r2025["pts_total"] == 1900.0


def test_transform_missing_required_column_fails_boundary() -> None:
    """Missing required source columns fail boundary via Polars native error."""
    # Missing season_type
    bad_phase = pl.DataFrame([{"per_mode": "pergame", "measure_type": "base", "player_id": 1}])
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        transform_player_season_stats(bad_phase)

    # Missing measure column in base
    feed = pl.DataFrame([
        {"season_type": "regular-season", "per_mode": "pergame", "measure_type": "base", "player_id": 1}
    ])
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        transform_player_season_stats(feed)


def test_transform_duplicate_detection_fails_1_to_1() -> None:
    """Duplicate keys in base, advanced, or totals slices must fail 1:1 join validation."""
    # Duplicate in base
    dup_base = pl.DataFrame([
        _base_row(player_id=1, season=2025, pts=20.0),
        _base_row(player_id=1, season=2025, pts=22.0),
        _adv_row(player_id=1, season=2025),
        _tot_row(player_id=1, season=2025),
    ])
    with pytest.raises(Exception) as excinfo:
        transform_player_season_stats(dup_base)
    assert "1:1" in str(excinfo.value) or "duplicate" in str(excinfo.value).lower()

    # Duplicate in advanced
    dup_adv = pl.DataFrame([
        _base_row(player_id=1, season=2025),
        _adv_row(player_id=1, season=2025, ts_pct=0.55),
        _adv_row(player_id=1, season=2025, ts_pct=0.60),
        _tot_row(player_id=1, season=2025),
    ])
    with pytest.raises(Exception) as excinfo:
        transform_player_season_stats(dup_adv)
    assert "1:1" in str(excinfo.value) or "duplicate" in str(excinfo.value).lower()

    # Duplicate in totals
    dup_tot = pl.DataFrame([
        _base_row(player_id=1, season=2025),
        _adv_row(player_id=1, season=2025),
        _tot_row(player_id=1, season=2025, pts=1000.0),
        _tot_row(player_id=1, season=2025, pts=1050.0),
    ])
    with pytest.raises(Exception) as excinfo:
        transform_player_season_stats(dup_tot)
    assert "1:1" in str(excinfo.value) or "duplicate" in str(excinfo.value).lower()


def test_label_generation() -> None:
    assert label(2025) == "2024-25"
    assert label(2020) == "2019-20"
    assert label(2015) == "2014-15"
