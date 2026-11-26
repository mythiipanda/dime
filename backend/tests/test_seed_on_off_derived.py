import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

RUNTIME_WAREHOUSE = BACKEND / "data" / "warehouse-runtime.duckdb"

pytestmark = pytest.mark.skipif(
    not RUNTIME_WAREHOUSE.exists(),
    reason=f"the runtime warehouse is absent at {RUNTIME_WAREHOUSE}")


@pytest.fixture(scope="module")
def derived():
    import duckdb
    from scripts.seed_on_off_derived import build

    con = duckdb.connect(str(RUNTIME_WAREHOUSE), read_only=True)
    try:
        cols, records = build(con)
    finally:
        con.close()
    return cols, records


def test_jokic_on_off_net_sign_and_magnitude(derived):
    cols, records = derived
    jokic = [r for r in records
             if r["player_id"] == 203999 and r["_season"] == "2025-26"]
    assert jokic, "jokic 2025-26 absent from silver_on_off coverage"
    r = jokic[0]
    diff = r["pts_per_100_possessions_diff"]
    assert diff is not None
    assert 0.0 < diff < 35.0
    on = r["pts_per_100_possessions_on"]
    off = r["pts_per_100_possessions_off"]
    assert abs((on - off) - diff) < 0.01


def test_rows_are_typed_and_keyed(derived):
    cols, records = derived
    assert len(records) > 200
    assert "player_id" in cols and "_season" in cols and "team" in cols
    for r in records[:50]:
        assert isinstance(r["player_id"], int)
        v = r.get("pts_per_100_possessions_on")
        assert v is None or isinstance(v, float)
    teamed = sum(1 for r in records if r["team"])
    assert teamed / len(records) > 0.9


def test_no_entity_strings_leak(derived):
    cols, records = derived
    assert "_entity" not in cols
    stat_cols = [c for c in cols if c.endswith("_diff")]
    assert len(stat_cols) > 50
