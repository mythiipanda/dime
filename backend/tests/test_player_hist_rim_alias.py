
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools import player
from shared.tools.player import get_shot_zones, portability_fit, zone_diet

PLAYER_ID = 12345
SEASON = "2009-10"
FETCHED_AT = "2026-11-01T00:00:00Z"

SYN_RIM_FGA = 30
SYN_RIM_FGM = 18
SYN_TOTAL_FGA = 100


def _zone_agg_rows():
    return [
        {"zone": "rim", "fga": SYN_RIM_FGA, "fgm": SYN_RIM_FGM},
        {"zone": "short_mid", "fga": 20, "fgm": 8},
        {"zone": "long_mid", "fga": 15, "fgm": 5},
        {"zone": "corner_3", "fga": 15, "fgm": 6},
        {"zone": "atb_3", "fga": 20, "fgm": 8},
    ]


def _fake_fetch_hist_aggs(table, year, where="", params=None):
    assert table == "silver_hist_shots"
    assert year == 2010
    return _zone_agg_rows()


def _fake_fetched_at(table, season):
    assert table == "silver_hist_shots"
    return FETCHED_AT


class _FallbackReached(AssertionError):
    pass


def _forbidden_store_connect(*args, **kwargs):
    raise _FallbackReached("store.connect reached before hist result returned")


def _forbidden_split(*args, **kwargs):
    raise _FallbackReached("silver_zone_splits fallback reached before hist result returned")


def _forbidden_player_shots(*args, **kwargs):
    raise _FallbackReached("live player-shot fallback reached before hist result returned")


@pytest.fixture
def hist_fixture(monkeypatch):
    monkeypatch.setattr(player, "_fetch_hist_aggs", _fake_fetch_hist_aggs)
    monkeypatch.setattr(player, "_hist_fetched_at", _fake_fetched_at)
    monkeypatch.setattr(store, "connect", _forbidden_store_connect)
    monkeypatch.setattr(player, "_zone_split_shot_result", _forbidden_split)
    monkeypatch.setattr(player, "_player_shot_dicts", _forbidden_player_shots)
    yield


def test_hist_producer_consumer_chain_serves_rim_share(hist_fixture):
    res = get_shot_zones.invoke(
        {"player_id": PLAYER_ID, "season": SEASON, "min_attempts": 1})
    assert res["ok"] is True
    assert (res.get("meta") or {}).get("source") == "warehouse:silver_hist_shots"
    rows_by_zone = {r["zone"]: r for r in res["rows"]}
    assert rows_by_zone["rim"]["SHARE"] == pytest.approx(0.3)
    three = rows_by_zone["corner_3"]["SHARE"] + rows_by_zone["atb_3"]["SHARE"]
    assert three == pytest.approx(0.35)
    diet = zone_diet(res["rows"])
    assert diet["rim_share"] == pytest.approx(0.3)
    assert diet["three_share"] == pytest.approx(0.35)


def test_standard_label_rim_control(hist_fixture):
    rows = [
        {"zone": "Restricted Area", "SHARE": 0.3},
        {"zone": "Corner 3", "SHARE": 0.25},
        {"zone": "Above the Break 3", "SHARE": 0.1},
    ]
    diet = zone_diet(rows)
    assert diet["rim_share"] == pytest.approx(0.3)
    assert diet["three_share"] == pytest.approx(0.35)


def test_actual_zero_rim_share_stays_zero(hist_fixture):
    diet = zone_diet([{"zone": "rim", "SHARE": 0.0}])
    assert diet["rim_share"] == 0.0
    diet = zone_diet([{"zone": "Restricted Area", "SHARE": 0.0}])
    assert diet["rim_share"] == 0.0


def test_missing_rim_zone_yields_none(hist_fixture):
    diet = zone_diet([{"zone": "short_mid", "SHARE": 0.2}])
    assert diet["rim_share"] is None


def test_portability_note_lists_shot_diet_when_both_sides_carry_shares():
    hist_a = zone_diet(_zone_agg_rows())
    hist_b = zone_diet(_zone_agg_rows())
    a = {"name": "A", "usg_pct": 28.0, "ts_pct": 0.58, "net_onoff": 1.0, **hist_a}
    b = {"name": "B", "usg_pct": 27.0, "ts_pct": 0.57, "net_onoff": 2.0, **hist_b}
    fit = portability_fit(a, b)
    assert fit["fit"] == "neutral"
    assert "Shot diet" in fit["note"]


def test_portability_note_omits_shot_diet_when_side_missing_rim():
    hist_a = zone_diet(_zone_agg_rows())
    b = {"name": "B", "usg_pct": 27.0, "ts_pct": 0.57, "net_onoff": 2.0,
         "rim_share": None, "three_share": 0.35}
    a = {"name": "A", "usg_pct": 28.0, "ts_pct": 0.58, "net_onoff": 1.0, **hist_a}
    fit = portability_fit(a, b)
    assert fit["fit"] == "neutral"
    assert "Shot diet" not in fit["note"]
