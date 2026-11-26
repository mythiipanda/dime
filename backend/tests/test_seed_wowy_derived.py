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
def wowy_rows():
    import duckdb
    from scripts.seed_wowy_derived import build

    con = duckdb.connect(str(RUNTIME_WAREHOUSE), read_only=True)
    try:
        cols, rows = build(con)
    finally:
        con.close()
    return cols, rows


def _idx(cols):
    return {c: i for i, c in enumerate(cols)}


def test_jokic_2024_25_wowy_in_sane_positive_range(wowy_rows):
    cols, rows = wowy_rows
    ix = _idx(cols)
    matches = [r for r in rows
               if r[ix["_season"]] == "2024-25" and r[ix["player_id"]] == 203999]
    assert len(matches) == 1
    wowy = matches[0][ix["wowy_diff_per48"]]
    assert wowy is not None
    assert 3.0 < wowy < 25.0


def test_rowcount_consistent_with_stint_coverage(wowy_rows):
    cols, rows = wowy_rows
    ix = _idx(cols)
    assert len(rows) > 5000
    seasons = {r[ix["_season"]] for r in rows}
    assert "2024-25" in seasons
    assert len(seasons) >= 10


def test_off_net_present_when_team_minutes_exceed_player_minutes(wowy_rows):
    cols, rows = wowy_rows
    ix = _idx(cols)
    violations = 0
    checked = 0
    for r in rows:
        on_minutes = r[ix["on_minutes"]]
        games_on = r[ix["games_on"]]
        games_played = r[ix["games_played"]]
        team_minutes_floor = games_played * 48.0
        if team_minutes_floor - on_minutes > 48.0 and games_on < games_played:
            checked += 1
            if r[ix["off_net_per48"]] is None:
                violations += 1
    assert checked > 100
    assert violations == 0
