import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_prospects as sp
from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.tools.league.prospects import get_prospect, _height_in


def _result(frame, source="tankathon", season="2027"):
    return FetchResult(frame=frame, meta=FetchMeta(source=source,
                                                 season=season))


@pytest.fixture()
def scratch(tmp_path):
    db = tmp_path / "wh.duckdb"
    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = db
    store.LOCK_PATH = tmp_path / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield db
    store.DB_PATH, store.LOCK_PATH = old_db, old_lock
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _seed(scratch):
    boards = pl.DataFrame({
        "ORDER": [1, 14], "PLAYER_NAME": ["Cam Prospect", "Euro Wing"],
        "PLAYER_SLUG": ["cam-prospect", "euro-wing"],
        "POSITION": ["G", "SF"], "SCHOOL": ["Duke", "Real Madrid"],
        "TEAM_ABBREVIATION": ["BKN", ""],
        "HEIGHT": ["6-5", "6-8"], "WEIGHT_LBS": [200, 215],
        "CLASS_YEAR": ["Fr", ""], "AGE": [18.5, 19.2],
        "BOARD": ["mock_draft", "big_board"]})
    store.save_frame("silver_draft_boards", _result(boards), entity="board")
    stats = pl.DataFrame({
        "PLAYER_NAME": ["Cam Prospect"], "TEAM": ["Duke"],
        "GP": [10.0], "PTS": [19.2], "REB": [6.1], "AST": [4.0],
        "TS_PCT": [0.61], "USG": [27.0]})
    store.save_frame("silver_prospect_stats", _result(stats), entity="league")
    hist = pl.DataFrame({
        "PLAYER_NAME": ["Past Pick One", "Past Pick Two"],
        "OVERALL_PICK": [1, 2], "TEAM_ABBREVIATION": ["SAS", "CHA"],
        "DRAFT_YEAR": [2023, 2020]})
    store.save_frame("silver_hist_draft", _result(hist, season="hist"),
                     entity="league")
    combine = pl.DataFrame({
        "PLAYER_NAME": ["Old Guard"], "POSITION": ["G"],
        "HEIGHT_WO_SHOES": [77.0], "WEIGHT": [195.0],
        "WINGSPAN": [80.0]})
    store.save_frame("silver_combine", _result(combine, season="2025"),
                     entity="league")


def test_height_parse():
    assert _height_in("6-8") == 80.0
    assert _height_in("6'2.5") == 74.5
    assert _height_in("") is None


def test_get_prospect_full(scratch):
    _seed(scratch)
    res = get_prospect.func(player="Cam Prospect", draft_year="2027")
    assert res["ok"]
    assert res["boards"][0]["ORDER"] == 1
    assert res["college_stats"]["PTS"] == 19.2
    assert res["pick_slot_comps"]
    assert res["combine_comps"]
    assert res["meta"]["stats_available"] is True


def test_get_prospect_international_flag(scratch):
    _seed(scratch)
    res = get_prospect.func(player="Euro Wing", draft_year="2027")
    assert res["ok"]
    assert res["college_stats"] is None
    assert res["meta"]["international_or_non_ncaa"] is True
    assert res["meta"]["stats_available"] is False


def test_get_prospect_missing(scratch):
    res = get_prospect.func(player="Nobody", draft_year="2027")
    assert res["ok"] is False
    assert "seed_prospects" in res["error"]


def test_seeder_stats_into_scratch(scratch, monkeypatch):
    frame = pl.DataFrame({"PLAYER_NAME": ["X"], "TEAM": ["Y"], "GP": [5.0],
                          "PTS": [10.0], "REB": [4.0], "AST": [3.0],
                          "TS_PCT": [0.55], "USG": [20.0]})
    monkeypatch.setattr(sp._cbb, "get_player_stats",
                        lambda year: _result(frame, source="barttorvik",
                                             season=str(year)))
    n = sp.load_prospect_stats(2027, dry_run=False)
    assert n == 1
    rows = store.read_frame_optional("silver_prospect_stats", "1=1", [])
    assert rows["_season"].to_list() == ["2027"]
    assert rows["_source"].to_list() == ["barttorvik"]
