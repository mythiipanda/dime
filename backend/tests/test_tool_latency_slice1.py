import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.player import get_shot_zones
from shared.tools.zone import get_team_shot_zones, zone_case_sql, zone_of
from shared.tools.zonedelta import get_zone_deltas

FIX = Path(__file__).resolve().parent / "fixtures" / "slice1"


def _load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def _norm(out):
    return json.loads(json.dumps(out, sort_keys=True))


def test_sql_case_agrees_with_zone_of_on_real_shots():
    case = zone_case_sql()
    con = store.connect(read_only=True)
    try:
        rows = con.execute(
            f"SELECT x_legacy, y_legacy, shot_value, {case} AS z"
            " FROM (SELECT * FROM ("
            "SELECT x_legacy, y_legacy, shot_value FROM silver_hist_shots"
            " WHERE (x_legacy = 0 AND y_legacy = 80)"
            " OR ABS(x_legacy) = 220 LIMIT 100) UNION ALL ("
            "SELECT x_legacy, y_legacy, shot_value FROM silver_hist_shots"
            " ORDER BY RANDOM() LIMIT 2500))"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) >= 2000
    assert any(
        (x or 0) ** 2 + (y or 0) ** 2 == 6400 for x, y, _, _ in rows
    )
    assert any(abs(x or 0) == 220 for x, _, _, _ in rows)
    for x, y, v, z in rows:
        assert z == zone_of(x, y, v)


def test_sql_case_matches_zone_of_on_null_coords():
    case2 = zone_case_sql("NULL", "NULL", "2")
    case3 = zone_case_sql("NULL", "NULL", "3")
    con = store.connect(read_only=True)
    try:
        got2 = con.execute(f"SELECT {case2}").fetchone()[0]
        got3 = con.execute(f"SELECT {case3}").fetchone()[0]
    finally:
        con.close()
    assert got2 == zone_of(None, None, 2) == "long_mid"
    assert got3 == zone_of(None, None, 3) == "atb_3"


def test_get_shot_zones_matches_pre_change_outputs():
    for name, kwargs in [
        ("sz_sga", {"player_id": 1628983, "season": "2024-25"}),
        ("sz_luka", {"player_id": 1629029, "season": "2024-25"}),
        ("sz_lebron_2022", {"player_id": 2544, "season": "2022-23",
                            "min_attempts": 10}),
        ("sz_konchar", {"player_id": 1629723, "season": "2024-25",
                        "min_attempts": 10}),
    ]:
        assert _norm(get_shot_zones.invoke(kwargs)) == _load(name)


def test_get_team_shot_zones_matches_pre_change_outputs():
    for name, kwargs in [
        ("tz_league", {"teams": "league", "season": "2025-26"}),
        ("tz_bos", {"teams": "BOS", "season": "2025-26"}),
        ("tz_lal", {"teams": "LAL", "season": "2025-26"}),
    ]:
        assert _norm(get_team_shot_zones.invoke(kwargs)) == _load(name)


def test_get_zone_deltas_matches_pre_change_outputs():
    for name, kwargs in [
        ("zd_sga", {"player": "Shai Gilgeous-Alexander", "season": 2025}),
        ("zd_taylor", {"player": "Terry Taylor", "season": 2025,
                       "min_attempts": 10}),
    ]:
        assert _norm(get_zone_deltas.invoke(kwargs)) == _load(name)


def _max_of_five(fn):
    fn()
    best = 0.0
    for _ in range(5):
        start = time.perf_counter()
        fn()
        best = max(best, time.perf_counter() - start)
    return best


def test_get_shot_zones_p95_under_400ms():
    assert _max_of_five(lambda: get_shot_zones.invoke(
        {"player_id": 1628983, "season": "2024-25"})) < 0.4


def test_get_team_shot_zones_p95_under_400ms():
    assert _max_of_five(lambda: get_team_shot_zones.invoke(
        {"teams": "league", "season": "2025-26"})) < 0.4


def test_get_zone_deltas_p95_under_400ms():
    assert _max_of_five(lambda: get_zone_deltas.invoke(
        {"player": "Shai Gilgeous-Alexander", "season": 2025})) < 0.4
