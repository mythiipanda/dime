import pytest

from shared import store
from shared.tools.league.fa_plan import get_fa_plan


def _seed(monkeypatch, tmp_path, with_room=True, with_minimum=True):
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
        minimum = ", ROSTER_CHARGE_MINIMUM BIGINT" if with_minimum else ""
        con.execute(
            "CREATE TABLE silver_cap_room ("
            "TEAM VARCHAR, CAP_SEASON VARCHAR, COMMITTED_SALARY BIGINT, "
            "PENDING_OPTION_SALARY BIGINT, FA_HOLDS_EST BIGINT, "
            "INCOMPLETE_ROSTER_CHARGES BIGINT, PROJECTED_ROOM BIGINT, "
            "MAX_ROOM BIGINT, PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, "
            "PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT, "
            "NTMLE_EST BIGINT, BAE_EST BIGINT, ROOM_EST BIGINT, "
            "TMLE_EST BIGINT, PLAYERS_UNDER_CONTRACT INTEGER, "
            "PENDING_OPTIONS INTEGER, ESTIMATED BOOLEAN"
            f"{minimum}, _fetched_at TIMESTAMP)")
    con.close()
    return path


def _load(path, fa_rows, room_rows=None, fa_year=2027):
    import duckdb
    con = duckdb.connect(str(path))
    for f in fa_rows:
        con.execute(
            "INSERT INTO silver_free_agents VALUES (?,?,?,?,?,?,?,now())",
            [f["player"], f["team"], f.get("slug"), fa_year, f["fa_type"],
             f["prior"], f["hold"]])
    room_has_minimum = bool(room_rows) and any(
        r[1] == "ROSTER_CHARGE_MINIMUM"
        for r in con.execute("PRAGMA table_info(silver_cap_room)").fetchall())
    for room_row in room_rows or []:
        values = list(room_row)
        if room_has_minimum:
            values.append(1_493_539)
        marks = ",".join("?" for _ in values)
        con.execute(
            f"INSERT INTO silver_cap_room VALUES ({marks},now())", values)
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
            0, 51_457_100, 53_989_405, 181_457_100,
            220_470_800, 229_916_500, 243_854_600,
            16_548_400, 6_024_700, 10_302_600, 6_670_400, 8, 1, True]


def _okc_room_2028():
    row = list(_okc_room())
    row[1] = "2028-29"
    row[2] = 100_000_000
    row[6] = 71_457_100
    row[7] = 73_989_405
    return row


def _cle_room():
    return ["CLE", "2027-28", 215_591_354, 7_460_937, 23_428_207,
            5_091_480, -46_643_771, -41_728_574, 181_500_000,
            221_152_800, 230_627_100, 244_609_200,
            15_510_000, 6_270_000, 9_680_000, None, 11, 2, True]


def _bos_fa():
    return [
        {"player": "Option Guy", "team": "BOS",
         "fa_type": "player_option", "prior": 15_000_000,
         "hold": 22_500_000},
        {"player": "Expiring Man", "team": "BOS", "fa_type": "ufa",
         "prior": 10_000_000, "hold": 15_000_000},
    ]


def _bos_room():
    return ["BOS", "2027-28", 21_000_000, 16_000_000, 37_500_000,
            11_948_312, 132_508_788, 144_028_171, 181_457_100,
            220_470_800, 229_916_500, 243_854_600,
            16_548_400, 6_024_700, 10_302_600, 6_670_400, 2, 1, True]


def test_fa_rows_and_flags(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), [_okc_room()])
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
    assert res["context"]["max_room"] == 53_989_405
    assert res["context"]["roster_charge_minimum"] == 1_493_539
    assert res["context"]["roster_charge_minimum_source"] == "warehouse"
    assert res["cap_season"] == "2027-28"
    assert res["exceptions"]["ntmle"] == 16_548_400
    assert res["exceptions"]["tmle"] == 6_670_400
    assert res["exceptions"]["bae"] == 6_024_700
    assert res["exceptions"]["room"] == 10_302_600


def test_unknown_hold_is_null_not_zero(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), [_okc_room()])

    def unknown_derivation(con, fa_year, team):
        return {"rows": [{
            "PLAYER_NAME": "Unknown Wing", "TEAM": "OKC", "FA_TYPE": "ufa",
            "PRIOR_SALARY": 10_000_000, "CAP_HOLD_EST": 15_000_000,
            "cap_hold": None, "cap_hold_est": None,
            "legacy_cap_hold_est": 15_000_000,
            "money_unit": "usd_dollars", "scenario_dependency": "active_expired_contract",
            "active_in_baseline": True, "provenance_class": "uncomputed_unknown_inputs",
            "input_exactness": {}, "input_provenance": {}, "uncertainty": [],
        }], "meta": {"derivation_status": "calculator_derived"}}

    monkeypatch.setattr("shared.tools.league.fa_plan.derive_cap_holds",
                        unknown_derivation)
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    row = res["rows"][0]
    assert row["cap_hold"] is None
    assert row["cap_hold_est"] is None
    assert row["hold_share"] is None
    assert row["legacy_cap_hold_est"] == 15_000_000
    assert res["context"]["fa_holds_unknown_count"] == 1
    assert res["meta"]["cap_hold_contract"]["cap_hold_est"].endswith("null when unknown")
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    keep = scen[("keep_only", "Unknown Wing")]
    assert keep["projected_room"] is None
    assert keep["projected_room_upper_bound"] == 46_976_483
    assert keep["path"] == "unknown"
    renounce = scen[("renounce", "Unknown Wing")]
    assert renounce["projected_room"] == 45_482_944
    assert renounce["arithmetic_status"] == "exact"


def test_ricky_rubio_unknown_hold_scenarios_are_disclosed(
        monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, [], [_cle_room()])

    def row(player, fa_type, hold, active):
        return {"PLAYER_NAME": player, "FA_TYPE": fa_type,
                "cap_hold": hold, "active_in_baseline": active}

    def cle_derivation(con, fa_year, team):
        rows = [row("Jaylon Tyson", "team_option", 5_641_500, False)]
        rows += [row(name, "ufa", 2_695_000, True)
                 for name in ["Thomas Bryant", "Mario Hezonja",
                              "Nae'Qwan Tomlin", "Craig Porter Jr."]]
        rows += [row("Cam Whitmore", "team_option", None, False),
                 row("Ricky Rubio", "ufa", None, True)]
        return {"rows": rows, "meta": {"derivation_status": "calculator_derived"}}

    monkeypatch.setattr("shared.tools.league.fa_plan.derive_cap_holds",
                        cle_derivation)
    res = get_fa_plan.invoke({"team": "CLE", "fa_year": "2027"})
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    assert res["context"]["fa_holds_unknown_count"] == 2
    assert res["context"]["fa_holds_active_unknown_count"] == 1

    keep = scen[("keep_only", "Ricky Rubio")]
    assert keep["projected_room"] is None
    assert keep["projected_room_upper_bound"] == -41_552_291
    assert keep["arithmetic_status"] == "partial_unknown_holds"
    assert keep["cap_holds_retained"] == 0
    assert keep["cap_holds_retained_semantics"] \
        == "known_amounts_partial_sum"
    assert keep["unknown_holds_retained_count"] == 1
    assert keep["unknown_holds_renounced_count"] == 0
    assert keep["hold_unknown"] is True
    assert "projected_room is null" in keep["warning"]
    assert keep["roster_charges"] == 0

    renounce = scen[("renounce", "Ricky Rubio")]
    assert renounce["projected_room"] == -52_332_291
    assert renounce["arithmetic_status"] == "exact"
    assert renounce["cap_holds_renounced"] == 0
    assert renounce["cap_holds_renounced_semantics"] \
        == "known_amounts_partial_sum"
    assert renounce["unknown_holds_retained_count"] == 0
    assert renounce["unknown_holds_renounced_count"] == 1
    assert renounce["hold_unknown"] is True
    assert "known-dollar partial sum" in renounce["warning"]

    keep_all = scen[("keep_all", None)]
    renounce_all = scen[("renounce_all", None)]
    assert keep_all["projected_room"] is None
    assert keep_all["projected_room_upper_bound"] == -52_332_291
    assert keep_all["unknown_holds_retained_count"] == 1
    assert renounce_all["projected_room"] == -43_045_830
    assert renounce_all["unknown_holds_renounced_count"] == 1
    assert renounce_all["cap_holds_renounced_semantics"] \
        == "known_amounts_partial_sum"

    known_keep = scen[("keep_only", "Thomas Bryant")]
    known_renounce = scen[("renounce", "Thomas Bryant")]
    assert known_keep["projected_room"] == -44_247_291
    assert known_keep["arithmetic_status"] == "exact"
    assert known_keep["unknown_holds_renounced_count"] == 1
    assert known_renounce["projected_room"] is None
    assert known_renounce["projected_room_upper_bound"] == -49_637_291
    assert known_renounce["unknown_holds_retained_count"] == 1


def test_scenario_arithmetic(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), [_okc_room()])
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    assert scen[("keep_all", None)]["projected_room"] == -16_936_439
    assert scen[("keep_all", None)]["path"] == "over_cap"
    assert scen[("keep_all", None)]["cap_holds_retained"] == 66_900_000
    assert scen[("keep_all", None)]["cap_holds_renounced"] == 0
    assert scen[("keep_all", None)]["roster_charges"] == 1_493_539
    assert scen[("renounce_all", None)]["projected_room"] == 45_482_944
    assert scen[("renounce_all", None)]["path"] == "under_cap"
    assert scen[("renounce_all", None)]["cap_holds_retained"] == 0
    assert scen[("renounce_all", None)]["cap_holds_renounced"] == 66_900_000
    assert scen[("renounce_all", None)]["roster_charges"] == 5_974_156
    assert scen[("renounce", "Star Wing")]["projected_room"] == 41_570_022
    assert scen[("renounce", "Star Wing")]["cap_holds_renounced"] \
        == 60_000_000
    assert scen[("renounce", "Star Wing")]["roster_charges"] == 2_987_078
    assert scen[("keep_only", "Star Wing")]["projected_room"] \
        == -13_023_517
    assert scen[("keep_only", "Star Wing")]["cap_holds_retained"] \
        == 60_000_000
    assert scen[("keep_only", "Star Wing")]["cap_holds_renounced"] \
        == 6_900_000
    assert scen[("keep_only", "Star Wing")]["roster_charges"] == 4_480_617
    assert scen[("renounce", "Cheap Guard")]["projected_room"] \
        == -12_429_978
    assert scen[("renounce", "Cheap Guard")]["cap_holds_renounced"] \
        == 6_000_000


def test_roster_charge_counts_only_active_holds(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _bos_fa(), [_bos_room()])
    res = get_fa_plan.invoke({"team": "BOS", "fa_year": "2027"})
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    keep = scen[("keep_all", None)]
    renounce = scen[("renounce", "Expiring Man")]
    assert keep["roster_charges"] == 13_441_851
    assert keep["roster_charges"] != res["context"]["roster_charges"]
    assert keep["projected_room"] == 116_015_249
    assert renounce["projected_room"] == 129_521_710
    assert renounce["projected_room"] - keep["projected_room"] \
        == 13_506_461


def test_legacy_room_without_minimum_uses_labeled_fallback(
        monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path, with_minimum=False)
    _load(path, _okc_fa(), [_okc_room()])
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027"})
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    assert res["context"]["roster_charge_minimum"] == 1_493_539
    assert res["context"]["roster_charge_minimum_source"] \
        == "legacy_approximation"
    assert scen[("renounce_all", None)]["roster_charges"] == 5_974_156


def test_fa_year_maps_to_matching_cap_season(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, _okc_fa(), [_okc_room(), _okc_room_2028()], fa_year=2028)
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2028"})
    assert res["ok"] is True
    assert res["cap_season"] == "2028-29"
    assert res["context"]["committed_salary"] == 100_000_000
    scen = {(s["scenario"], s["player"]): s for s in res["scenarios"]}
    assert scen[("keep_all", None)]["projected_room"] == 3_063_561
    assert scen[("renounce_all", None)]["projected_room"] == 65_482_944


def test_missing_mapped_cap_season_does_not_fall_back(monkeypatch, tmp_path):
    path = _seed(monkeypatch, tmp_path)
    _load(path, [], [_okc_room()])
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2028"})
    assert res["ok"] is False
    assert "2028-29" in res["error"]
    assert "seed_free_agents" in res["error"]


def test_invalid_fa_year_rejected(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    res = get_fa_plan.invoke({"team": "OKC", "fa_year": "2027-28"})
    assert res["ok"] is False
    assert "four-digit calendar year" in res["error"]


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
