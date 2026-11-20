import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_current_season as scs
from shared import store
from shared.sources.base import FetchMeta, FetchResult


def _result(frame, source="nba_api", season="2026-27"):
    return FetchResult(frame=frame, meta=FetchMeta(source=source, season=season))


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
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


def test_end_year():
    assert scs.end_year("2026-27") == 2027
    assert scs.end_year("1999-00") == 2000
    with pytest.raises(ValueError):
        scs.end_year("2026-2027")


def test_load_lineups_per_team_entity(scratch, monkeypatch):
    calls = []
    frame = pl.DataFrame({"GROUP_ID": ["a"], "TEAM_ID": [1],
                          "TEAM_ABBREVIATION": ["ATL"], "MIN": [10.0]})

    def fake_lineups(team_id, season):
        calls.append((team_id, season))
        return _result(frame)

    import scripts.seed_current_season as m
    monkeypatch.setattr("shared.sources.nba_stats.lineups", fake_lineups)
    monkeypatch.setattr(m, "LIVE_SLEEP_S", 0)
    import nba_api.stats.static.teams as tmod
    monkeypatch.setattr(tmod, "get_teams",
                        lambda: [{"id": 1, "abbreviation": "ATL"},
                                 {"id": 2, "abbreviation": "BOS"}])
    n = scs.load_lineups("2026-27", dry_run=False)
    assert n == 2 and calls == [(1, "2026-27"), (2, "2026-27")]
    rows = store.read_frame_optional("silver_lineups", "1=1", [])
    assert set(rows["_entity"]) == {"team:1", "team:2"}
    assert set(rows["_season"]) == {"2026-27"}


def test_load_on_off_pool_and_entities(scratch, monkeypatch):
    leaders = pl.DataFrame({
        "PLAYER_ID": [10, 11, 12], "PLAYER": ["a", "b", "c"],
        "TEAM_ID": [100, 100, 200], "MIN": [400.0, 320.0, 50.0]})
    store.save_frame("silver_leaders_pts", _result(leaders), entity="league")
    seen = []

    def fake_on_off(pid, tid, season):
        seen.append(pid)
        return _result(pl.DataFrame({"Stat": ["offrtg"], "On": [110.0],
                                     "Off": [108.0], "On-Off": [2.0]}),
                       source="pbpstats")

    import scripts.seed_current_season as m
    monkeypatch.setattr("shared.sources.pbpstats.on_off", fake_on_off)
    monkeypatch.setattr(m, "LIVE_SLEEP_S", 0)
    n = scs.load_on_off("2026-27", dry_run=False)
    assert seen == [10, 11]
    assert n == 2
    rows = store.read_frame_optional("silver_on_off", "1=1", [])
    assert set(rows["_entity"]) == {"player:10", "player:11"}


def test_load_team_ratings_replaces_season(scratch, monkeypatch):
    frame = pl.DataFrame({"TEAM_ID": [1], "TEAM_NAME": ["A"],
                          "NET_RATING": [5.0]})
    monkeypatch.setattr("shared.sources.nba_stats.team_ratings",
                        lambda season: _result(frame))
    n = scs.load_team_ratings("2026-27", dry_run=False)
    assert n == 1
    rows = store.read_frame_optional("silver_team_ratings", "1=1", [])
    assert rows["_season"].to_list() == ["2026-27"]
    assert rows["_source"].to_list() == ["nba_api"]
