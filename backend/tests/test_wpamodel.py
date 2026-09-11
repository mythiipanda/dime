"""WPA win-probability model tests. Pure-math cases are hermetic.

The holdout gate reads silver_hist_pbp read-only and runs the full 2024-25
season (about 630k events) through the fitted constants. It finishes in
seconds, well under the 120s budget.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.wpamodel import (  # noqa: E402
    B0,
    B1,
    SMOOTH,
    fit_logistic,
    parse_clock,
    seconds_remaining,
    win_probability,
    win_probability_from_scores,
)


def test_tipoff_probability():
    p = win_probability(0, 2880.0)
    assert p == pytest.approx(0.5398, abs=0.005)
    assert 0.45 < p < 0.62
    assert win_probability_from_scores("0", "0", "PT12M00.00S", 1) == p


def test_monotonic_in_lead():
    for sec in (60.0, 600.0, 2880.0):
        ps = [win_probability(lead, sec) for lead in range(-30, 31)]
        assert all(b > a for a, b in zip(ps, ps[1:]))


def test_trailing_team_time():
    early = win_probability(-8, 2880.0)
    mid = win_probability(-8, 1200.0)
    late = win_probability(-8, 60.0)
    assert early > mid > late


def test_leading_team_time():
    assert win_probability(8, 2880.0) < win_probability(8, 1200.0)
    assert win_probability(8, 60.0) > win_probability(8, 1200.0)


def test_clock_parsing():
    assert parse_clock("PT12M00.00S") == 720.0
    assert parse_clock("PT07M49.00S") == pytest.approx(469.0)
    assert parse_clock("PT05M00.00S") == 300.0
    assert parse_clock("PT00M00.00S") == 0.0
    assert parse_clock("11:43") is None
    assert parse_clock("") is None
    assert seconds_remaining("PT12M00.00S", 1) == 2880.0
    assert seconds_remaining("PT00M00.00S", 4) == 0.0
    assert seconds_remaining("PT05M00.00S", 5) == 300.0
    assert seconds_remaining("PT12M00.00S", 0) is None
    assert win_probability_from_scores("", "", "PT12M00.00S", 1) is None
    assert win_probability_from_scores("99", "101", "PT00M10.00S", 5) < 0.5


def test_determinism():
    rows = [(lead, sec, 1 if lead > 0 else 0)
            for lead in range(-12, 13) for sec in (120.0, 900.0, 2400.0)]
    assert fit_logistic(rows) == fit_logistic(rows)
    b0, b1 = fit_logistic(rows)
    assert b1 > 0
    assert win_probability(5, 300.0) == win_probability(5, 300.0)


_FEATURE_SQL = """
WITH d AS (
  SELECT DISTINCT game_id, action_number, clock, period,
         NULLIF(score_home, '')::INTEGER AS sh,
         NULLIF(score_away, '')::INTEGER AS sa
  FROM silver_hist_pbp WHERE _season = '2024-25'
),
f AS (
  SELECT game_id, action_number, clock, period,
         LAST_VALUE(sh IGNORE NULLS) OVER w AS h,
         LAST_VALUE(sa IGNORE NULLS) OVER w AS a
  FROM d WINDOW w AS (PARTITION BY game_id ORDER BY action_number
                      ROWS UNBOUNDED PRECEDING)
),
g AS (SELECT game_id, MAX(h) AS fh, MAX(a) AS fa FROM f GROUP BY game_id)
SELECT
  (regexp_extract(f.clock,'PT(\\d+)M',1)::INTEGER*60
   + regexp_extract(f.clock,'M([\\d.]+)S',1)::DOUBLE
   + CASE WHEN f.period <= 4 THEN 720*(4-f.period) ELSE 0 END) AS sec,
  (f.h - f.a) AS lead,
  CASE WHEN g.fh > g.fa THEN 1 ELSE 0 END AS y
FROM f JOIN g USING (game_id) WHERE f.h IS NOT NULL
"""


def test_holdout_calibration():
    from app import store

    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_pbp" not in tables:
            pytest.skip("silver_hist_pbp not seeded")
        start = time.time()
        rows = con.execute(_FEATURE_SQL).fetchall()
    finally:
        con.close()
    assert time.time() - start < 120
    assert len(rows) > 600000
    buckets: dict = {}
    for sec, lead, y in rows:
        p = win_probability(lead, sec)
        k = min(9, int(p * 10))
        n, sp, sy = buckets.get(k, (0, 0.0, 0))
        buckets[k] = (n + 1, sp + p, sy + y)
    assert len(buckets) == 10
    worst = 0.0
    for k in sorted(buckets):
        n, sp, sy = buckets[k]
        err = abs(sp / n - sy / n)
        worst = max(worst, err)
        assert err < 0.03, f"bucket {k}: pred={sp/n:.4f} actual={sy/n:.4f}"
    assert worst > 0.001
