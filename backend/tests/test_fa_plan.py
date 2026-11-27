import pytest

from shared import store
from shared.tools.league.fa_plan import get_fa_plan


def _seed(monkeypatch, tmp_path, with_room=True):
    path = tmp_path / "w.duckdb"
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    import duckdb
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_free_agents ("
        "PLAYER_NAME VARCHAR, TEAM VARCHAR, BREF_SLUG VARCHAR, "
        "FA_YEAR INTEGER, FA_TYPE VARCHAR, PRIOR_SALARY BIGINT, "
        "CAP_HOLD_EST BIGINT, _fetched_at TIMESTAMP)")
    if with_room:
        con.execute(
            "CREATE TABLE silver_cap_room ("
            "TEAM VARCHAR, CAP_SEASON VARCHAR, COMMITTED_SALARY BIGINT, "
            "PENDING_OPTION_SALARY BIGINT, FA_HOLDS_EST BIGINT, "
            "INCOMPLETE_ROSTER_CHARGES BIGINT, PROJECTED_ROOM BIGINT, "
            "MAX_ROOM BIGINT, PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, "
            "PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT, "
            "NTMLE_EST BIGINT, BAE_EST BIGINT, ROOM_EST BIGINT, "
            "TMLE_EST BIGINT, PLAYERS_UNDER_CONTRACT INTEGER, "
            "PENDING_OPTIONS INTEGER, "
            "ESTIMATED BOOLEAN, _fetched_at TIMESTAMP)")
    con.close()
    return path


def _load(path, fa_rows, room_row=None):
    import duckdb
    con = duckdb.connect(str(path))
    for f in fa_rows:
        con.execute(
            "INSERT INTO silver_free_agents VALUES (?,?,?,?,?,?,?,now())",
            [f["player"], f["team"], f.get("slug"), 2027, f["fa_type"],
             f["prior"], f["hold"]])
    if room_row:
        con.execute(
            "INSERT INTO silver_cap_room VALUES (?,?,?,?,?,?,?,?,?,?,?,?,"
            "?,?,?,?,?,?,?,now())", room_row)
    con.close()


def _okc_fa():
    return [
        {"player": "Star Wing", "team": "OKC", "fa_type": "ufa",
         "prior": 40_000_000, "hold": 60_000_000},
        {"player": "Cheap Guard", "team": "OKC", "fa_type": "rfa",
         "prior": 4_000_000, "hold": 6_000_000},
        {"player": "Opt Guy", "team": "OKC", "fa_type": "player_option",
         "prior": 10_000_000, "hold": 15_000_000},
        {"player": "Two Way", "team": "OKC", "fa_type": "two_way",
         "prior": 600_000, "hold": 900_000},
        {"player": "Other Team FA", "team": "DEN", "fa_type": "ufa",
         "prior": 20_000_000, "hold": 30_000_000},
    ]


def _okc_room():
    return ["OKC", "2027-28", 120_000_000, 10_000_000, 81_900_000,
            5_000_000, -35_400_000, 55_000_000, 181_457_100,
            220_470_800, 229_916_500, 243_854_600,
            16_548_400, 6_024_700, 10_302_600, 6_670_400, 8, 1, True]


def test_fa_rows_and_flags(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), _okc_room())
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    assert res["ok"] is True
    rows = {r["player"]: r for r in res["rows"]}
    assert len(rows) == 4
    assert rows["Star Wing"]["cap_hold_est"] == 60_000_000
    assert rows["Star Wing"]["extension_eligible"] is True
    assert rows["Cheap Guard"]["extension_eligible"] is True
    assert rows["Opt Guy"]["extension_eligible"] is False
    assert rows["Two Way"]["extension_eligible"] is False
    assert abs(rows["Star Wing"]["hold_share"] - 60_000_000
               / 181_457_100) < 0.001
    assert res["context"]["projected_cap"] == 181_457_100
    assert res["exceptions"]["ntmle"] == 16_548_400
    assert res["exceptions"]["tmle"] == 6_670_400
    assert res["exceptions"]["bae"] == 6_024_700
    assert res["exceptions"]["room"] == 10_302_600


def test_scenario_arithmetic(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), _okc_room())
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    assert scen[("keep_all", None)]["projected_room"] == -35_400_000
    assert scen[("keep_all", None)]["path"] == "over_cap"
    assert scen[("renounce_all", None)]["projected_room"] == 55_000_000
    assert scen[("renounce_all", None)]["path"] == "under_cap"
    assert scen[("renounce", "Star Wing")]["projected_room"] == 24_600_000
    assert scen[("keep_only", "Star Wing")]["projected_room"] == -5_000_000
    assert scen[("renounce", "Cheap Guard")]["projected_room"] \
        == -29_400_000


def test_missing_room_still_emits_fa_rows(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa())
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    assert res["ok"] is True
    assert res["rows"]
    assert res["scenarios"] == []
    assert any(c["rule"] == "cap room" and not c["checked"]
               for c in res["checks"])


def test_no_data_error(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path, with_room=False)
    _load(path, [])
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    assert res["ok"] is False
    assert "seed_free_agents" in res["error"]


def test_requires_team(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    res = get_fa_plan.invoke({"team": ""})
    assert res["ok"] is False
