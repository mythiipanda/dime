"""Warehouse freshness tests. Stale-flag logic is hermetic with fake metadata;
one integration test reads the real warehouse to prove wiring."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import get_warehouse_freshness
from app.tools.league import FRESHNESS_RULES, _freshness_row

NOW = datetime(2026, 9, 10, 15, 30, tzinfo=timezone.utc)  # September: offseason
SEASON_NOW = datetime(2026, 1, 15, 15, 30, tzinfo=timezone.utc)  # January: in season


def _iso(dt):
    return dt.isoformat()


def test_daily_table_fresh_in_season():
    row = _freshness_row("silver_scoreboard", 26, _iso(SEASON_NOW - timedelta(hours=2)),
                         SEASON_NOW)
    assert row["stale"] is False
    assert row["expected"] == "daily in season"
    assert row["age_hours"] == 2.0


def test_daily_table_stale_in_season():
    row = _freshness_row("silver_scoreboard", 26, _iso(SEASON_NOW - timedelta(days=3)),
                         SEASON_NOW)
    assert row["stale"] is True
    assert row["age_hours"] == 72.0


def test_daily_table_relaxes_to_weekly_offseason():
    row = _freshness_row("silver_scoreboard", 26, _iso(NOW - timedelta(days=3)), NOW)
    assert row["expected"] == "weekly (offseason)"
    assert row["stale"] is False
    old = _freshness_row("silver_scoreboard", 26, _iso(NOW - timedelta(days=10)), NOW)
    assert old["stale"] is True


def test_weekly_table_boundary():
    fresh = _freshness_row("silver_salaries", 461, _iso(NOW - timedelta(days=6)), NOW)
    assert fresh["stale"] is False
    old = _freshness_row("silver_salaries", 461, _iso(NOW - timedelta(days=8)), NOW)
    assert old["stale"] is True


def test_static_table_never_stale():
    row = _freshness_row("silver_hist_possessions", 1379694,
                         _iso(NOW - timedelta(days=900)), NOW)
    assert row["stale"] is False
    assert row["expected"] == "static"
    assert row["age_hours"] == 21600.0


def test_unknown_timestamp_stays_unknown():
    row = _freshness_row("silver_scoreboard", 26, None, NOW)
    assert row["last_fetch"] == "unknown"
    assert row["stale"] is None
    assert row["age_hours"] is None


def test_malformed_timestamp_stays_unknown():
    row = _freshness_row("silver_scoreboard", 26, "not-a-timestamp", NOW)
    assert row["last_fetch"] == "unknown"
    assert row["stale"] is None


def test_table_outside_registry_gets_unknown_rule():
    row = _freshness_row("silver_brand_new", 10, _iso(NOW - timedelta(hours=1)), NOW)
    assert row["expected"] == "unknown"
    assert row["stale"] is None
    assert row["age_hours"] == 1.0


def test_registry_covers_every_silver_table_in_warehouse():
    import duckdb
    from app import store

    con = duckdb.connect(str(store.DB_PATH), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()
                  if r[0].startswith("silver_")}
    finally:
        con.close()
    assert tables <= set(FRESHNESS_RULES), tables - set(FRESHNESS_RULES)


def test_tool_wired_and_reads_warehouse():
    out = get_warehouse_freshness.invoke({})
    assert out["ok"] is True
    assert out["meta"]["tables"] >= 32
    for row in out["rows"]:
        assert set(row) == {"table", "rows", "last_fetch", "age_hours",
                            "expected", "stale"}
        assert isinstance(row["rows"], int)
        assert row["stale"] in (True, False, None)
