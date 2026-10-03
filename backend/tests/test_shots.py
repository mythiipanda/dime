
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.shots import (ZONE_KEYS, ZONE_LABEL_MAP, disambiguate_last_name,
                             efficiency, fold_ot, format_clock, group_row,
                             is_heave, parse_group_by, parse_include_ot,
                             parse_made, parse_late_clock, parse_periods,
                             parse_zones, period_matches, search_shots,
                             seconds_left, summarize, summarize_by_period,
                             summarize_by_zone, zone_of_label, _where_sql)


def _require_full_shot_pack():
    from shared import store
    con = store.connect()
    try:
        count, teams, players = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT TEAM_ID), "
            "COUNT(DISTINCT PLAYER_ID) FROM silver_shots "
            "WHERE _season = '2025-26'"
        ).fetchone()
    finally:
        con.close()
    if count < 20000 or teams < 30 or players < 100:
        pytest.skip(
            "release pack has partial silver_shots coverage "
            f"({count} rows, {teams} teams, {players} players)"
        )


def _shot(zone, made, period=4, game="g1"):
    return {"zone": zone, "made": made, "period": period, "game_id": game}


@pytest.mark.parametrize("label,expected", [
    ("Restricted Area", "rim"),
    ("In The Paint (Non-RA)", "short_mid"),
    ("Mid-Range", "long_mid"),
    ("Left Corner 3", "corner_3"),
    ("Right Corner 3", "corner_3"),
    ("Above the Break 3", "atb_3"),
    ("Half Court", None),
    (None, None),
])
def test_zone_of_label_table(label, expected):
    assert zone_of_label(label) == expected
    assert set(ZONE_LABEL_MAP) == {
        "Restricted Area", "In The Paint (Non-RA)", "Mid-Range",
        "Left Corner 3", "Right Corner 3", "Above the Break 3"}


@pytest.mark.parametrize("text,expected", [
    ("", set(ZONE_KEYS)),
    ("corner_3, atb_3", {"corner_3", "atb_3"}),
])
def test_parse_zones_table(text, expected):
    assert parse_zones(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("", None),
    ("4th", {4}),
    ("ot", {5}),
    ("1h", {1, 2}),
    ("2h", {3, 4}),
    ("1,2", {1, 2}),
])
def test_parse_periods_table(text, expected):
    assert parse_periods(text) == expected


@pytest.mark.parametrize("period,wanted,expected", [
    (4, {4}, True),
    (5, {5}, True),
    (7, {5}, True),
    (5, {4}, False),
    (3, None, True),
    (None, {4}, False),
])
def test_period_matches_table(period, wanted, expected):
    assert period_matches(period, wanted) is expected


@pytest.mark.parametrize("text,expected", [
    ("", ""),
    ("player", "player"),
    ("TEAM", "team"),
])
def test_parse_group_by_table(text, expected):
    assert parse_group_by(text) == expected


@pytest.mark.parametrize("text,default,expected", [
    ("", True, True),
    ("auto", False, False),
    ("yes", False, True),
    ("no", True, False),
    ("TRUE", True, True),
])
def test_parse_include_ot_table(text, default, expected):
    assert parse_include_ot(text, default) is expected


@pytest.mark.parametrize("periods,include,expected", [
    ({4}, True, {4, 5}),
    ({4}, False, {4}),
    ({1, 2}, True, {1, 2, 5}),
    ({5}, False, {5}),
    (None, True, None),
    (None, False, None),
])
def test_fold_ot_table(periods, include, expected):
    assert fold_ot(periods, include) == expected


@pytest.mark.parametrize("func,args,expected", [
    (parse_made, ("MADE",), "made"),
    (parse_made, ("any",), "any"),
    (parse_late_clock, ("",), None),
    (parse_late_clock, ("30",), 30),
    (efficiency, (4, 2, 1), {"fg_pct": 0.5, "efg_pct": 0.625}),
    (efficiency, (0, 0, 0), {"fg_pct": 0.0, "efg_pct": 0.0}),
])
def test_parse_value_mappings_table(func, args, expected):
    assert func(*args) == expected


@pytest.mark.parametrize("period,secs,left,clock", [
    (1, 5, 65, "1:05"),
    (None, 5, None, None),
    (None, None, None, "unknown"),
])
def test_clock_helpers_table(period, secs, left, clock):
    assert seconds_left(period, secs) == left
    if clock is not None:
        assert format_clock(period, secs) == clock


@pytest.mark.parametrize("func,args,match", [
    (parse_zones, ("corner_3, paint",), "unknown zone"),
    (parse_periods, ("q5",), "unknown period"),
    (parse_group_by, ("zone",), "invalid group_by"),
    (parse_group_by, ("coach",), "invalid group_by"),
    (parse_include_ot, ("maybe", True), "invalid include_ot"),
    (parse_made, ("sometimes",), "invalid made filter"),
    (parse_late_clock, ("abc",), "invalid late_clock"),
    (parse_late_clock, ("Q4:30",), "invalid late_clock"),
])
def test_parse_invalid_rejected(func, args, match):
    with pytest.raises(ValueError, match=match):
        func(*args)


def test_group_row_small_sample_flag():
    big = group_row(50, 25, 10, games=12)
    assert big["attempts"] == 50
    assert big["efg_pct"] == 0.6
    assert big["points"] == 2 * 25 + 10
    assert big["small_sample"] is False
    small = group_row(5, 3, 2)
    assert small["small_sample"] is True
    assert "games" not in small


def test_is_heave_boundary():
    assert is_heave(29, 0, 3) is False
    assert is_heave(30, 0, 3) is True
    assert is_heave(30, 0, 4) is False
    assert is_heave(35, 0, 0) is True
    assert is_heave(30, None, None) is False
    assert is_heave(None, 0, 1) is False


def test_disambiguate_last_name_unique_and_ambiguous():
    unique = disambiguate_last_name(
        "gilgeous-alexander", [("Gilgeous-Alexander", 1628983)])
    assert unique == {"player_id": 1628983,
                      "candidates": [{"player": "Gilgeous-Alexander",
                                      "player_id": 1628983}],
                      "ambiguous": False}
    shared = disambiguate_last_name(
        "Williams", [("Williams", 101), ("Williams", 202)])
    assert shared["ambiguous"] is True
    assert shared["player_id"] is None
    assert [c["player_id"] for c in shared["candidates"]] == [101, 202]
    missing = disambiguate_last_name("Nobody", [("Williams", 101)])
    assert missing == {"player_id": None, "candidates": [],
                       "ambiguous": False}


def test_summarize_overall_and_by_zone_and_period():
    shots = [_shot("corner_3", True, 4, "g1"),
             _shot("corner_3", False, 4, "g1"),
             _shot("rim", True, 5, "g2"),
             _shot("atb_3", False, 6, "g2")]
    agg = summarize(shots)
    assert agg["attempts"] == 4
    assert agg["makes"] == 2
    assert agg["threes_made"] == 1
    assert agg["games"] == 2
    assert agg["efg_pct"] == 0.625
    by_zone = {r["zone"]: r for r in summarize_by_zone(shots)}
    assert by_zone["corner_3"]["attempts"] == 2
    assert by_zone["corner_3"]["makes"] == 1
    assert by_zone["rim"]["attempts"] == 1
    assert by_zone["long_mid"]["attempts"] == 0
    by_period = {r["period"]: r for r in summarize_by_period(shots)}
    assert by_period[4]["attempts"] == 2
    assert by_period["OT"]["attempts"] == 2
    assert by_period["OT"]["makes"] == 1


def test_tool_tatum_corner3_4th_matches_verified_numbers():
    _require_full_shot_pack()
    res = search_shots.invoke(
        {"player": "Tatum", "zones": "corner_3", "periods": "4th"})
    assert res["ok"] is True
    agg = res["aggregate"]
    assert agg["attempts"] == 5
    assert agg["makes"] == 3
    assert agg["efg_pct"] == 0.9
    assert agg["small_sample"] is True
    assert "sample_warning" in res["meta"]


def test_tool_small_sample_flag_off_for_big_lines():
    _require_full_shot_pack()
    res = search_shots.invoke({"team": "BOS", "zones": "rim"})
    assert res["ok"] is True
    agg = res["aggregate"]
    assert agg["attempts"] > 100
    assert agg["small_sample"] is False
    assert "sample_warning" not in res["meta"]


def test_tool_group_by_player_leaderboard():
    _require_full_shot_pack()
    res = search_shots.invoke({"periods": "4th", "group_by": "player"})
    assert res["ok"] is True
    rows = res["by_player"]
    assert len(rows) > 100
    attempts = [r["attempts"] for r in rows]
    assert attempts == sorted(attempts, reverse=True)
    top = rows[0]
    assert top["player_id"]
    assert top["player"]
    assert top["efg_pct"] > 0
    assert "small_sample" in top
    assert res["filters"]["group_by"] == "player"


def test_tool_by_zone_only_requested_zones():
    res = search_shots.invoke({"zones": "rim"})
    assert res["ok"] is True
    assert res["by_zone"]
    assert all(r["zone"] == "rim" for r in res["by_zone"])
    assert all(r["zone"] in {"rim", "corner_3"}
               for r in search_shots.invoke(
                   {"zones": "rim,corner_3"})["by_zone"])


def test_tool_performance_smoke():
    _require_full_shot_pack()
    start = time.perf_counter()
    res = search_shots.invoke(
        {"periods": "4th", "late_clock": "300", "group_by": "player"})
    elapsed = time.perf_counter() - start
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] > 20000
    assert elapsed < 2.0, f"search_shots took {elapsed:.2f}s"


def test_group_by_team_leaderboard():
    res = search_shots.invoke(
        {"group_by": "team", "periods": "4th", "late_clock": "300"})
    assert res["ok"] is True
    assert "by_team" in res
    rows = res["by_team"]
    assert len(rows) <= 50
    attempts = [r["attempts"] for r in rows]
    assert attempts == sorted(attempts, reverse=True)
    for r in rows:
        assert "efg_pct" in r
        assert "small_sample" in r
    assert sum(attempts) == res["aggregate"]["attempts"]


def test_group_by_player_small_sample():
    _require_full_shot_pack()
    res = search_shots.invoke(
        {"player": "Tatum", "zones": "corner_3", "periods": "4th"})
    assert res["ok"] is True
    agg = res["aggregate"]
    assert agg["attempts"] < 10
    assert agg["small_sample"] is True
    assert "sample_warning" in res["meta"]
    assert [r["zone"] for r in res["by_zone"]] == ["corner_3"]


def test_ot_included_by_default():
    default = search_shots.invoke({"periods": "4th"})
    explicit = search_shots.invoke({"periods": "4th,ot"})
    no_ot = search_shots.invoke({"periods": "4th", "include_ot": "no"})
    assert default["ok"] and explicit["ok"] and no_ot["ok"]
    assert (default["aggregate"]["attempts"]
            == explicit["aggregate"]["attempts"])
    assert no_ot["aggregate"]["attempts"] < default["aggregate"]["attempts"]


def test_late_clock_includes_ot_by_default():
    default = search_shots.invoke({"late_clock": "300"})
    no_ot = search_shots.invoke({"late_clock": "300", "include_ot": "no"})
    assert default["ok"] and no_ot["ok"]
    assert (default["aggregate"]["attempts"]
            > no_ot["aggregate"]["attempts"])


def test_disambiguation_returns_candidates():
    _require_full_shot_pack()
    res = search_shots.invoke({"player": "Williams"})
    assert res["ok"] is True
    assert "disambiguation" in res
    cands = res["disambiguation"]["candidates"]
    assert len(cands) > 0
    for c in cands:
        assert c["player_id"]
        assert isinstance(c["player"], str) and c["player"]
        assert isinstance(c["teams"], list) and len(c["teams"]) > 0


def test_unknown_player_still_fails():
    res = search_shots.invoke({"player": "Nobody XYZ"})
    assert res["ok"] is False
    assert "unknown player" in res["error"]


def test_clutch_safe_flag():
    res = search_shots.invoke({"periods": "4th"})
    assert res["ok"] is True
    assert res["meta"]["clutch_safe"] is False
    assert res["meta"]["score_aware"] is False


def test_heave_disabled_wording():
    res = search_shots.invoke({"player": "Tatum", "exclude_heaves": False})
    assert res["ok"] is True
    assert "INCLUDED" in res["meta"]["data_note"]
    assert res["meta"]["heaves_excluded"] == 0


def test_conflicting_filters_note():
    res = search_shots.invoke({"periods": "1h", "late_clock": "60"})
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] == 0
    assert "late_clock" in res["meta"]["note"]


def test_zero_match_note():
    res = search_shots.invoke(
        {"player": "Tatum", "zones": "rim", "periods": "1", "made": "made"})
    assert res["ok"] is True
    if res["aggregate"]["attempts"] == 0:
        assert "note" in res["meta"]


def test_invalid_group_by():
    res = search_shots.invoke({"group_by": "coach"})
    assert res["ok"] is False


def test_sample_rows_spread():
    res = search_shots.invoke({"periods": "4th", "limit": 25})
    assert res["ok"] is True
    shots = res["shots"]
    assert len(shots) <= 25
    assert len({s["game_id"] for s in shots}) >= 5


def test_performance_smoke():
    search_shots.invoke(
        {"group_by": "player", "periods": "4th", "late_clock": "300"})
    start = time.perf_counter()
    res = search_shots.invoke(
        {"group_by": "player", "periods": "4th", "late_clock": "300"})
    elapsed = time.perf_counter() - start
    assert res["ok"] is True
    assert elapsed < 2.0, f"search_shots took {elapsed:.2f}s"


def test_ot_late_clock_returns_rows_note_free():
    res = search_shots.invoke({"periods": "ot", "late_clock": "60"})
    assert res["ok"] is True
    assert res["filters"]["include_ot"] is True
    assert res["filters"]["periods"] == ["OT"]
    assert res["aggregate"]["attempts"] > 0
    assert "note" not in res["meta"]
    assert all(r["period"] == "OT" for r in res["by_period"])
    assert all(s["period"] is not None and s["period"] >= 5
               for s in res["shots"])


def test_ot_explicit_include_ot_yes_late_clock():
    res = search_shots.invoke(
        {"periods": "ot", "include_ot": "yes", "late_clock": "60"})
    assert res["ok"] is True
    assert res["filters"]["include_ot"] is True
    assert res["aggregate"]["attempts"] > 0
    assert "note" not in res["meta"]


def test_late_clock_applies_to_folded_set_no_ot_leak():
    res = search_shots.invoke(
        {"periods": "4th", "include_ot": "no", "late_clock": "60"})
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] > 0
    assert not any(r["period"] == "OT" for r in res["by_period"])
    assert all(r["period"] == 4 for r in res["by_period"])


def test_where_sql_period_bounds():
    wanted = set(ZONE_KEYS)
    sql_on, _ = _where_sql("2025-26", None, None, wanted, {4, 5}, 300,
                           False, "any", True)
    assert "PERIOD >= 4" in sql_on
    assert "PERIOD >= 5" in sql_on
    sql_off, _ = _where_sql("2025-26", None, None, wanted, {4}, 300,
                            False, "any", False)
    assert "PERIOD >= 4" in sql_off
    assert "PERIOD = 4" not in sql_off
    assert "PERIOD >= 5" not in sql_off
    sql_none_off, _ = _where_sql("2025-26", None, None, wanted, None, 300,
                                 False, "any", False)
    assert "PERIOD = 4" in sql_none_off
    assert "PERIOD >= 4" not in sql_none_off
    sql, _ = _where_sql("2025-26", None, None, set(ZONE_KEYS), {5}, 60,
                        False, "any", True)
    assert "PERIOD >= 5" in sql
    assert "PERIOD = 4" not in sql


def test_non_late_period_late_clock_still_contradicts_with_note():
    res = search_shots.invoke({"periods": "3", "late_clock": "60"})
    assert res["ok"] is True
    assert res["aggregate"]["attempts"] == 0
    assert "note" in res["meta"]
    assert "late_clock" in res["meta"]["note"]


def test_individual_shot_rows_keep_canonical_player_and_team_ids(monkeypatch):
    class FakeCon:
        description = []
        def execute(self, sql, params=None):
            if "COUNT(*) FROM silver_shots WHERE _season" in sql:
                self.description = [("count_star()",)]
                self._rows = [(1,)]
            elif "COUNT(*) AS n" in sql:
                self.description = [("n",)]
                self._rows = [(0,)]
            elif "GROUP BY 1" in sql:
                self.description = []
                self._rows = []
            elif "SELECT PLAYER_NAME AS player" in sql:
                self.description = [(name,) for name in [
                    "player", "PLAYER_ID", "TEAM_ID", "period",
                    "MINUTES_REMAINING", "SECONDS_REMAINING", "zone",
                    "zone_label", "action", "distance_ft", "SHOT_MADE_FLAG",
                    "GAME_ID"]]
                self._rows = [("Tatum", 1628369, 1610612738, 1, 5, 0,
                               "corner_3", "Left Corner 3", "Jump Shot",
                               23.0, 1, "game")]
            else:
                self.description = [(name,) for name in [
                    "attempts", "makes", "threes_made", "games"]]
                self._rows = [(1, 1, 1, 1)]
            return self
        def fetchall(self): return self._rows
        def fetchone(self): return self._rows[0]
        def close(self): pass

    monkeypatch.setattr("shared.tools.shots._warehouse_conn", FakeCon)
    monkeypatch.setattr("shared.tools.shots._resolve_player",
                        lambda *args: (1628369, "exact", None))
    result = search_shots.invoke({"player": "Tatum", "zones": "corner_3"})
    row = result["shots"][0]
    assert row["player_id"] == 1628369
    assert row["team_id"] == 1610612738
    assert row["team"] == "BOS"
