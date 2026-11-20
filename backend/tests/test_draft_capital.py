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


def test_trade_value_pick_curve_fallback():
    from shared.tools.league.trade_value import _pick_value_for_slot

    curve = {1: 45.0, 30: 6.2, 45: 2.3}
    assert _pick_value_for_slot(1, True, curve) == 45.0
    assert _pick_value_for_slot(30, True, curve) == pytest.approx(6.2)
    assert _pick_value_for_slot(45, False, curve) == pytest.approx(2.3)
    assert _pick_value_for_slot(31, False, curve) > 0
    assert _pick_value_for_slot(1, True, None) > 0
