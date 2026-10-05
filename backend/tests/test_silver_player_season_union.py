import sys
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_silver_player_season as union
import seed_bbref_league_pages as bbref
from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.tools import _core as core_mod
from v2.adapters import coverage as coverage_mod

CURRY = 201939
LEBRON = 2544


@pytest.fixture()
def scratch(monkeypatch, tmp_path):
    path = tmp_path / "union.duckdb"
    duckdb.connect(str(path)).close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store._tables_cache.clear()
    store._pool_evict_all()
    store.warehouse_identity_cache_clear()
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()
    yield path
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()


def _save(table: str, frame: pl.DataFrame, season: str,
          source: str = "test-source") -> int:
    return store.save_frame(
        table,
        FetchResult(frame=frame, meta=FetchMeta(source=source, season=season)),
        entity="league", replace_season=True)


def _hist_frame() -> pl.DataFrame:
    return pl.DataFrame([{
        "player_id": CURRY, "player_name": "Stephen Curry",
        "team_abbreviation": "GSW", "age": 35.0, "gp": 74,
        "min": 32.7, "pts": 26.4, "reb": 4.5, "ast": 5.1,
        "stl": 0.7, "blk": 0.4, "fg_pct": 0.449,
        "fg3_pct": 0.408, "ft_pct": 0.915, "ts_pct": 0.616,
    }])


def _leaders_frame() -> pl.DataFrame:
    return pl.DataFrame([{
        "PLAYER_ID": LEBRON, "PLAYER": "LeBron James", "TEAM": "LAL",
        "GP": 71, "MIN": 2485, "PTS": 1822, "REB": 522, "AST": 589,
        "STL": 89, "BLK": 38, "FG_PCT": 0.540,
        "FG3_PCT": 0.410, "FT_PCT": 0.750,
    }])


def _advanced_frame() -> pl.DataFrame:
    return pl.DataFrame([{
        "PLAYER_ID": LEBRON, "PLAYER_NAME": "LeBron James",
        "TEAM_ABBREVIATION": "LAL", "AGE": 40.0, "GP": 71,
        "MIN": 35.0, "TS_PCT": 0.610, "FG_PCT": 0.540,
    }])


def _seasons(path: Path, table: str) -> set[str]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return {r[0] for r in con.execute(
            f"SELECT DISTINCT _season FROM {table}").fetchall()}
    finally:
        con.close()


def test_hist_season_copies_rates_with_honest_gs(scratch):
    _save(union.HIST_SOURCE, _hist_frame(), "2023-24")

    n = union.seed_season("2023-24")

    assert n == 1
    row = store.read_frame(
        union.TABLE, "_season = ?", ["2023-24"]).to_dicts()[0]
    assert row["PLAYER_ID"] == CURRY
    assert row["PLAYER"] == "Stephen Curry"
    assert row["TEAM"] == "GSW"
    assert row["MPG"] == pytest.approx(32.7)
    assert row["PPG"] == pytest.approx(26.4)
    assert row["TS_PCT"] == pytest.approx(0.616)
    assert row["GS"] is None
    assert row["_prov_PPG"] == union.HIST_SOURCE
    assert row["_prov_GS"] == union.ABSENT
    assert row["_season"] == "2023-24"


def test_totals_season_computes_per_game_at_boundary(scratch):
    _save(union.LEADERS_SOURCE, _leaders_frame(), "2025-26")
    _save(union.ADV_SOURCE, _advanced_frame(), "2025-26")

    union.seed_season("2025-26")

    row = store.read_frame(
        union.TABLE, "_season = ?", ["2025-26"]).to_dicts()[0]
    assert row["TEAM"] == "LAL"
    assert row["GP"] == pytest.approx(71.0)
    assert row["MPG"] == pytest.approx(2485 / 71)
    assert row["PPG"] == pytest.approx(1822 / 71)
    assert row["RPG"] == pytest.approx(522 / 71)
    assert row["APG"] == pytest.approx(589 / 71)
    assert row["AGE"] == pytest.approx(40.0)
    assert row["TS_PCT"] == pytest.approx(0.610)
    assert row["GS"] is None
    assert row["_prov_PPG"] == f"{union.LEADERS_SOURCE}:PTS/GP"
    assert row["_prov_TS_PCT"] == union.ADV_SOURCE
    assert row["_prov_GS"] == union.ABSENT


def test_rerun_skips_loaded_and_never_duplicates(scratch):
    _save(union.HIST_SOURCE, _hist_frame(), "2023-24")
    _save(union.LEADERS_SOURCE, _leaders_frame(), "2025-26")
    _save(union.ADV_SOURCE, _advanced_frame(), "2025-26")

    first = union.run(["2023-24", "2025-26"])
    before = store.read_frame(union.TABLE).height
    second = union.run(["2023-24", "2025-26"])

    assert sorted(first["loaded"]) == ["2023-24", "2025-26"]
    assert second == {"loaded": {}, "skipped": ["2023-24", "2025-26"],
                      "rows": 0}
    assert store.read_frame(union.TABLE).height == before == 2


def test_empty_source_names_season_and_writes_nothing(scratch):
    _save(union.HIST_SOURCE, _hist_frame(), "2023-24")

    with pytest.raises(union.SeasonBuildError, match="2021-22"):
        union.seed_season("2021-22")

    assert union.loaded_seasons() == set()


def test_player_report_returns_real_2025_26_line_with_team(scratch):
    from shared.tools import player as player_mod
    _save(union.LEADERS_SOURCE, _leaders_frame(), "2025-26")
    _save(union.ADV_SOURCE, _advanced_frame(), "2025-26")
    union.run(["2025-26"])

    avg = player_mod.get_season_averages.invoke(
        {"player_id": LEBRON, "season": "2025-26"})
    assert avg["ok"] is True
    line = avg["rows"][0]
    assert line["TEAM"] == "LAL"
    assert line["GP"] == pytest.approx(71.0)
    assert line["PPG"] == pytest.approx(1822 / 71)

    report = player_mod.get_player_report.invoke(
        {"player": LEBRON, "season": "2025-26"})
    assert report["ok"] is True
    assert report["rows"]["season_line"]["TEAM"] == "LAL"


def test_season_outside_every_source_fails_loudly_naming_coverage(scratch):
    from shared.tools import player as player_mod
    _save(union.HIST_SOURCE, _hist_frame(), "2023-24")
    _save(union.LEADERS_SOURCE, _leaders_frame(), "2025-26")
    _save(union.ADV_SOURCE, _advanced_frame(), "2025-26")
    union.run(["2023-24", "2025-26"])

    out = player_mod.get_season_averages.invoke(
        {"player_id": LEBRON, "season": "2005-06"})

    assert out["ok"] is False
    assert out.get("season_error") is True
    assert "2005-06" in out["error"]
    assert "2023-24" in out["error"] or "2025-26" in out["error"]


def test_wrong_subject_negative_through_true_path(scratch):
    from shared.tools import player as player_mod
    _save(union.LEADERS_SOURCE, _leaders_frame(), "2025-26")
    _save(union.ADV_SOURCE, _advanced_frame(), "2025-26")
    union.run(["2025-26"])

    out = player_mod.get_player_report.invoke(
        {"player": "Zzz No Such Player 999", "season": "2025-26"})

    assert out["ok"] is False
    assert "silver_player_season" not in out.get("error", "")


def _bbref_pg() -> pd.DataFrame:
    return pd.DataFrame([
        {"Player": "LeBron James", "Team": "TOT", "Age": 40.0,
         "G": 70.0, "GS": 70.0, "MP": 35.0, "PTS": 25.0,
         "TRB": 8.0, "AST": 9.0, "STL": 1.2, "BLK": 0.6,
         "FG%": 0.510, "3P%": 0.400, "FT%": 0.760, "FGA": 18.0},
        {"Player": "LeBron James", "Team": "LAL", "Age": 40.0,
         "G": 60.0, "GS": 60.0, "MP": 35.0, "PTS": 25.0,
         "TRB": 8.0, "AST": 9.0, "STL": 1.2, "BLK": 0.6,
         "FG%": 0.510, "3P%": 0.400, "FT%": 0.760, "FGA": 18.0},
        {"Player": "Stephen Curry", "Team": "GSW", "Age": 36.0,
         "G": 74.0, "GS": 74.0, "MP": 32.7, "PTS": 26.4,
         "TRB": 4.5, "AST": 5.1, "STL": 0.7, "BLK": 0.4,
         "FG%": 0.449, "3P%": 0.408, "FT%": 0.915, "FGA": 19.0},
    ])


def test_bbref_tot_team_rule_and_provenance(scratch):
    nm = {"LeBron James": LEBRON, "Stephen Curry": CURRY}

    rows = bbref.build_per_game_rows(_bbref_pg(), nm)

    assert len(rows) == 2
    lebron = next(r for r in rows if r["PLAYER_ID"] == LEBRON)
    assert lebron["TEAM"] == "TOT"
    assert lebron["PPG"] == pytest.approx(25.0)
    assert lebron["TS_PCT"] is None
    assert lebron["_prov_PPG"] == bbref.BBREF
    assert lebron["_prov_TS_PCT"] == bbref.ABSENT_TS


def test_bbref_season_idempotent_and_empty_names_season(scratch):
    nm = {"LeBron James": LEBRON, "Stephen Curry": CURRY}

    def fetch_page(page: str, year: int) -> pd.DataFrame:
        assert year == 2026
        assert page == "per_game"
        return _bbref_pg()

    first = bbref.run(["2025-26"], nm=nm, fetch_page=fetch_page)
    second = bbref.run(["2025-26"], nm=nm, fetch_page=fetch_page)

    assert first["loaded"] == {"2025-26": 2}
    assert second["skipped"] == ["2025-26"]
    assert _seasons(scratch, bbref.TABLE) == {"2025-26"}
    assert store.read_frame(bbref.TABLE).height == 2

    def empty_fetch(page: str, year: int) -> pd.DataFrame:
        return pd.DataFrame()

    with pytest.raises(bbref.SeasonFetchError, match="2024-25"):
        bbref.run(["2024-25"], nm=nm, fetch_page=empty_fetch)
    assert "2024-25" not in _seasons(scratch, bbref.TABLE)
