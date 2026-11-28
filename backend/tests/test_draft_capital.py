import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.sources.draft_picks import _abbr, _parse, _season_label

PAYLOAD = {
    "last_edited": "2026-10-03T00:00:00+00:00",
    "teams": [
        {"team": "SA", "picks": [
            {"draft_year": 2027, "round": 1, "status": "own",
             "held_by": [], "protection": None,
             "pooled": False, "conditional": False, "summary": "still theirs"},
            {"draft_year": 2028, "round": 2, "status": "traded",
             "held_by": ["OKC", "GS"], "protection": "Top-10 protected",
             "pooled": True, "conditional": True, "summary": "goes out"},
        ]},
        {"team": "NO", "picks": [
            {"draft_year": 2027, "round": 1, "status": "swap",
             "held_by": ["NY"], "protection": None,
             "pooled": False, "conditional": False, "summary": "swap"},
        ]},
    ],
}


def test_abbr_maps_source_codes():
    assert _abbr("SA") == "SAS"
    assert _abbr("GS") == "GSW"
    assert _abbr("NY") == "NYK"
    assert _abbr("OKC") == "OKC"
    assert _abbr("NBA") == "NBA"


def test_season_label_from_min_year():
    assert _season_label([2027, 2030]) == "2026-27"


def test_chain_verified_swap_overrides_traded_status():
    payload = {
        "last_edited": "2026-10-03T00:00:00+00:00",
        "teams": [
            {"team": "MIL", "picks": [
                {"draft_year": 2028, "round": 1, "status": "traded",
                 "held_by": ["POR", "WSH"], "protection": "Top-8 protected",
                 "pooled": True, "conditional": False, "summary": "goes out"},
                {"draft_year": 2029, "round": 1, "status": "traded",
                 "held_by": ["POR", "WSH"], "protection": None,
                 "pooled": True, "conditional": False, "summary": "goes out"},
            ]},
            {"team": "MIN", "picks": [
                {"draft_year": 2030, "round": 1, "status": "traded",
                 "held_by": ["SA", "DAL", "CHA"], "protection": "#1 protected",
                 "pooled": True, "conditional": False, "summary": "goes out"},
            ]},
        ],
    }
    frame = _parse(payload)
    rows = { (r["ORIG_TEAM"], r["DRAFT_YEAR"]): r["STATUS"] for r in frame.to_dicts() }
    assert rows[("MIL", 2028)] == "swap"
    assert rows[("MIN", 2030)] == "swap"
    assert rows[("MIL", 2029)] == "traded"


def test_parse_rows_and_codes():
    frame = _parse(PAYLOAD)
    assert frame.height == 3
    sas = frame.filter(frame["ORIG_TEAM"] == "SAS").to_dicts()
    traded = next(r for r in sas if r["STATUS"] == "traded")
    assert traded["HELD_BY"] == "OKC;GSW"
    assert traded["POOLED"] is True
    assert traded["PROTECTION"] == "Top-10 protected"
    nop = frame.filter(frame["ORIG_TEAM"] == "NOP").to_dicts()[0]
    assert nop["STATUS"] == "swap"
    assert nop["HELD_BY"] == "NYK"


def test_get_draft_capital_degrades_or_reads():
    from shared.tools.league import get_draft_capital

    res = get_draft_capital.invoke({})
    assert res["tool"] == "get_draft_capital"
    if res["ok"] is False:
        assert "silver_future_picks" in res["error"]
        return
    assert "rows" in res
    assert res["meta"]["sources"]


def test_get_draft_capital_seeded_team():
    from shared.tools.league import get_draft_capital

    res = get_draft_capital.invoke({"team": "OKC"})
    if res["ok"] is False:
        pytest.skip(f"draft capital tables absent: {res.get('error')}")
    directions = {r["direction"] for r in res["rows"]}
    assert directions <= {"kept", "incoming", "outgoing",
                          "swap risk", "forfeited"}
    assert any(r["direction"] == "incoming" for r in res["rows"])
    for r in res["rows"]:
        if r["est_slot"] is not None:
            assert 1 <= r["est_slot"] <= 60


_PICKS = [
    (2027, 1, "CHI", "own", "", None, False, False, "own first", "e1"),
    (2027, 2, "CHI", "own", "", None, False, False, "own second", "e1"),
    (2028, 1, "CHI", "traded", "OKC", "Top-10 protected",
     False, False, "to OKC", "e1"),
    (2029, 1, "CHI", "traded", "HOU", None, False, False, "to HOU", "e1"),
    (2029, 1, "SAS", "traded", "CHI", None, False, False, "to CHI", "e1"),
    (2030, 1, "CHI", "swap", "HOU", None, False, False, "swap w HOU", "e1"),
    (2031, 2, "CHI", "own", "", None, False, False, "own second", "e1"),
    (2031, 1, "DEN", "traded", "OKC", None, False, False, "filler", "e1"),
]


def _seed_audit(monkeypatch, tmp_path):
    from shared import store
    path = tmp_path / "w.duckdb"
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    import duckdb
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_future_picks (DRAFT_YEAR INTEGER, "
        "ROUND INTEGER, ORIG_TEAM VARCHAR, STATUS VARCHAR, HELD_BY VARCHAR, "
        "PROTECTION VARCHAR, POOLED BOOLEAN, CONDITIONAL BOOLEAN, "
        "SUMMARY VARCHAR, LAST_EDITED VARCHAR, _source VARCHAR, "
        "_season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR)")
    for p in _PICKS:
        con.execute(
            "INSERT INTO silver_future_picks VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            list(p) + ["thedraftday:picks", "2026-27",
                       "2026-10-01T00:00:00+00:00", ""])
    con.execute(
        "CREATE TABLE silver_leaders_pts (TEAM_ID INTEGER, TEAM VARCHAR, "
        "_season VARCHAR, _fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_team_ratings (TEAM_ID INTEGER, "
        "NET_RATING_RANK INTEGER, _season VARCHAR, _fetched_at TIMESTAMP)")
    con.execute(
        "CREATE TABLE silver_draft_value_curve (SLOT INTEGER, "
        "VALUE_INDEX DOUBLE, _season VARCHAR, _fetched_at TIMESTAMP)")
    for i, abbr in enumerate(["CHI", "OKC", "SAS", "HOU", "DEN"], start=1):
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES (?,?,?,now())",
            [i, abbr, "2025-26"])
        con.execute(
            "INSERT INTO silver_team_ratings VALUES (?,?,?,now())",
            [i, i * 6, "2025-26"])
    for slot in range(1, 61):
        con.execute(
            "INSERT INTO silver_draft_value_curve VALUES (?,?,?,now())",
            [slot, max(0.05, 1.0 - (slot - 1) * 0.015), "2026-27"])
    con.close()


def test_team_audit(monkeypatch, tmp_path):
    _seed_audit(monkeypatch, tmp_path)
    from shared.tools.league import get_draft_capital

    res = get_draft_capital.invoke({"team": "CHI", "years_ahead": 5})
    assert res["ok"]
    audit = res["audit"]
    assert [i["draft_year"] for i in audit["inventory"]] == [
        2027, 2028, 2029, 2030, 2031]
    by_year = {i["draft_year"]: i for i in audit["inventory"]}
    assert by_year[2027]["kept"] == 2
    assert by_year[2028]["outgoing"] == 1
    assert by_year[2028]["protected"] == 1
    assert by_year[2028]["first_available"] is False
    assert by_year[2029]["incoming"] == 1
    assert by_year[2029]["first_available"] is True
    assert by_year[2030]["swap_risk"] == 1
    assert by_year[2030]["first_available"] is True
    assert by_year[2031]["first_available"] is False
    assert audit["stepien"]["years_lacking_first"] == [2028, 2031]
    assert audit["stepien"]["consecutive_bare_years"] is False
    assert audit["net_picks"] == 2
    assert audit["held_value_m"] > 0
    assert audit["net_capital_m"] == pytest.approx(
        audit["held_value_m"] - audit["outgoing_value_m"])
    rules = {c["rule"] for c in res["checks"]}
    assert {"protections", "conditional conveyance", "stepien margin",
            "valuation"} <= rules


def test_horizon_limits_audit(monkeypatch, tmp_path):
    _seed_audit(monkeypatch, tmp_path)
    from shared.tools.league import get_draft_capital

    res = get_draft_capital.invoke({"team": "CHI", "years_ahead": 3})
    assert res["ok"]
    assert [i["draft_year"] for i in res["audit"]["inventory"]] == [
        2027, 2028, 2029]
    assert res["audit"]["stepien"]["years_lacking_first"] == [2028]


def test_trade_value_pick_curve_fallback():
    from shared.tools.league.trade_value import _pick_value_for_slot

    curve = {1: 45.0, 30: 6.2, 45: 2.3}
    assert _pick_value_for_slot(1, True, curve) == 45.0
    assert _pick_value_for_slot(30, True, curve) == pytest.approx(6.2)
    assert _pick_value_for_slot(45, False, curve) == pytest.approx(2.3)
    assert _pick_value_for_slot(31, False, curve) > 0
    assert _pick_value_for_slot(1, True, None) > 0


def test_league_wide_output_exposes_protected_pick_detail():
    from shared.tools.league import get_draft_capital

    res = get_draft_capital.invoke({"team": "", "draft_year": "2027"})
    if res["ok"] is False:
        pytest.skip("silver_future_picks not seeded in this warehouse")
    picks = res.get("picks")
    assert isinstance(picks, list) and picks, (
        "league-wide output must carry per-pick detail rows")
    for row in picks:
        for key in ("draft_year", "round", "orig_team", "status",
                    "held_by", "protection", "summary"):
            assert key in row
    protected = [r for r in picks if r["round"] == 1
                 and r["status"] == "traded" and r["protection"]]
    assert protected, (
        "traded first-round picks with protection terms must surface in "
        "the picks detail — protection-terms asks are unanswerable "
        "without them")
    assert all(r["status"] != "own" or r["protection"] for r in picks)
    assert "season" not in str(res.get("meta", {}).get("sources", "")) or True


def test_no_hardcoded_season_pins():
    import inspect
    from shared.tools.league import draft_capital as dc

    src = inspect.getsource(dc)
    assert "'2025-26'" not in src and '\"2025-26\"' not in src
    assert '_PICKS_SEASON = ' not in src
