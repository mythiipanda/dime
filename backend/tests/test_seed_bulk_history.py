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
