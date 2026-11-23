import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import tools
from shared.tools.lineup import get_lineup_on_off

def test_registered_in_tool_registry():
    assert "get_lineup_on_off" in tools.TOOL_NAMES

def test_rejects_wrong_arity():
    res = get_lineup_on_off.invoke({"team": "OKC", "players": "Shai Gilgeous-Alexander"})
    assert res["ok"] is False
    res = get_lineup_on_off.invoke({"team": "OKC", "players": "a,b,c,d,e,f"})
    assert res["ok"] is False

def test_unknown_player_fails_cleanly():
    res = get_lineup_on_off.invoke({"team": "OKC", "players": "Not A Real Player XYZ, Jalen Williams"})
    assert res["ok"] is False
    assert "could not resolve" in res["error"]

def test_never_shared_floor_fails_cleanly():
    res = get_lineup_on_off.invoke({"team": "BOS", "players": "Shai Gilgeous-Alexander, Jalen Williams", "season": "2025-26"})
    assert res["ok"] is False
    assert "never shared the floor" in res["error"]

def test_three_man_unit_splits_sum():
    res = get_lineup_on_off.invoke({"team": "OKC", "players": "Shai Gilgeous-Alexander, Jalen Williams, Chet Holmgren", "season": "2025-26"})
    assert res["ok"] is True, res
    on, off, delta = res["on"], res["off"], res["delta"]
    assert on["poss"] == on["off_poss"] + on["def_poss"]
    assert off["poss"] == off["off_poss"] + off["def_poss"]
    assert on["poss"] > 0 and off["poss"] > on["poss"]
    assert delta["NET_RATING"] == round(on["NET_RATING"] - off["NET_RATING"], 1)
    assert on["blowout_share"] <= 1.0

def test_two_man_subset_matches_wowy_shape():
    res = get_lineup_on_off.invoke({"team": "OKC", "players": "Shai Gilgeous-Alexander, Jalen Williams", "season": "2025-26"})
    assert res["ok"] is True, res
    assert res["on"]["poss"] > 100
