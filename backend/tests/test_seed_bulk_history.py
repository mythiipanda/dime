import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_bulk_history as sbh


def test_label_uses_end_year():
    assert sbh.label(2026) == "2025-26"
    assert sbh.label(1997) == "1996-97"


def test_resolve_target_refuses_canonical(tmp_path):
    assert sbh.resolve_target(str(sbh.store.CANONICAL_DB_PATH)) is None


def test_resolve_target_accepts_scratch(tmp_path):
    target = tmp_path / "warehouse.duckdb"
    assert sbh.resolve_target(str(target)) == target.resolve()


def test_transform_hist_gamelogs_keeps_regular_and_playoffs():
    df = pl.DataFrame({
        "season_type": ["regular-season", "playoffs", "preseason"],
        "game_id": ["1", "2", "3"],
    })
    out = sbh.transform_hist_gamelogs(df)
    assert out["season_type"].to_list() == ["regular-season", "playoffs"]


def test_transform_team_seasons_keeps_regular_season_only():
    df = pl.DataFrame({
        "season_type": ["regular-season", "playoffs", None],
        "team_id": [1, 2, 3],
    })
    out = sbh.transform_team_seasons(df)
    assert out["season_type"].to_list() == ["regular-season"]


def test_transform_player_seasons_joins_pergame_base_and_advanced():
    base = {name: None for name in sbh.PLAYER_BASE_COLS}
    base.update({
        "player_id": 1,
        "player_name": "Player One",
        "team_abbreviation": "BOS",
        "season": 2025,
        "gp": 10,
        "min": 200.0,
        "pts": 20.0,
    })
    adv = {name: None for name in sbh.PLAYER_ADV_COLS}
    adv.update({
        "player_id": 1,
        "team_abbreviation": "BOS",
        "ts_pct": 0.55,
        "efg_pct": 0.50,
    })
    total = {name: None for name in sbh.PLAYER_BASE_COLS}
    total.update({
        "player_id": 1,
        "player_name": "Player One",
        "team_abbreviation": "BOS",
        "season": 2025,
        "gp": 10,
    })
    df = pl.DataFrame([
        {**base, "season_type": "regular-season", "per_mode": "pergame", "measure_type": "base"},
        {**adv, "season_type": "regular-season", "per_mode": "pergame", "measure_type": "advanced"},
        {**total, "season_type": "regular-season", "per_mode": "totals", "measure_type": "base"},
        {**base, "season_type": "playoffs", "per_mode": "pergame", "measure_type": "base"},
    ])
    out = sbh.transform_player_seasons(df)
    assert out.height == 1
    assert out["player_id"].to_list() == [1]
    assert out["ts_pct"].to_list() == [0.55]
    assert "gp_total" not in out.columns


def test_completed_end_year_boundaries():
    import datetime
    assert sbh.completed_end_year(datetime.date(2026, 11, 27)) == 2026
    assert sbh.completed_end_year(datetime.date(2026, 8, 1)) == 2026
    assert sbh.completed_end_year(datetime.date(2026, 7, 31)) == 2026
    assert sbh.completed_end_year(datetime.date(2027, 3, 15)) == 2026
    assert sbh.completed_end_year(datetime.date(2027, 9, 1)) == 2027


def test_dataset_ranges_extend_through_completed_end_year():
    end = sbh.completed_end_year()
    for spec in sbh.DATASETS.values():
        assert end in spec["years"], f"{spec['table']} must cover the last completed end-year {end}"
        assert end + 1 not in spec["years"], f"{spec['table']} must not pull the in-progress season"


def test_newest_year_upstream_lag_degrades_to_skip_not_failure(monkeypatch):
    spec = {"table": "silver_hist_team_seasons", "source": "s", "entity": "league",
            "file": "f{year}", "min_rows": 1, "transform": "team_seasons"}
    years = [2025, 2026]

    def boom(spec_arg, year):
        raise RuntimeError("404")

    monkeypatch.setattr(sbh, "read_frame", boom)
    monkeypatch.setattr(sbh, "unit_done", lambda *a: False)
    written, skipped, failures = sbh.run_dataset("team_seasons", spec, years, False, True)
    assert written == 0
    assert any("2024-25" in f for f in failures)
    assert not any("2025-26" in f for f in failures)
