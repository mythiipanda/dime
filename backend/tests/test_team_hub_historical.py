"""get_team_hub serves historical seasons from silver_hist_gamelogs.

Instinct QA (2026-09-27): the season_resolution bench truth aggregates
silver_hist_gamelogs for the NAMED season, but get_team_hub read only
silver_team_games (seeded for 2025-26) and errored on older seasons - the
bench graded truth against a source the app could never answer from.
Since silver_team_games is itself a promoted slice of
silver_hist_gamelogs, get_team_hub now serves the same slice for any
static season with no seeded rows, so truth and answer sources align.

Hermetic: temp DuckDB stands in for the warehouse; _warehouse_or_live and
coerce_team_id are monkeypatched. Needs the full backend env
(langchain_core); collection fails in the bare sandbox like the other
backend tool tests.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools import team as team_mod  # noqa: E402


def _seed_hist(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("""
        CREATE TABLE silver_hist_gamelogs (
            team_id INTEGER, game_id VARCHAR, game_date DATE,
            matchup VARCHAR, wl VARCHAR, min DOUBLE,
            fgm INTEGER, fga INTEGER, fg_pct DOUBLE,
            fg3m INTEGER, fg3a INTEGER, fg3_pct DOUBLE,
            ftm INTEGER, fta INTEGER, ft_pct DOUBLE,
            oreb INTEGER, dreb INTEGER, reb INTEGER,
            ast INTEGER, stl INTEGER, blk INTEGER,
            tov INTEGER, pf INTEGER, pts INTEGER,
            _season VARCHAR, season_type VARCHAR,
            team_abbreviation VARCHAR)
        """)
        con.execute("""
        INSERT INTO silver_hist_gamelogs VALUES
          (2, '0022400001', DATE '2024-10-22', 'BOS vs. NYK', 'W', 30.0,
           12, 30, 0.400, 5, 12, 0.417, 8, 10, 0.800,
           8, 30, 38, 25, 8, 4, 12, 18, 115,
           '2024-25', 'regular-season', 'BOS'),
          (2, '0022400015', DATE '2024-10-24', 'BOS @ WAS', 'W', 31.0,
           13, 32, 0.406, 6, 14, 0.429, 9, 11, 0.818,
           7, 28, 35, 27, 9, 5, 11, 17, 118,
           '2024-25', 'regular-season', 'BOS'),
          (2, '0022400030', DATE '2024-10-26', 'BOS vs. DET', 'L', 29.0,
           11, 31, 0.355, 4, 13, 0.308, 7, 9, 0.778,
           9, 27, 36, 22, 7, 3, 13, 19, 108,
           '2024-25', 'regular-season', 'BOS'),
          (2, '0042400101', DATE '2025-04-20', 'BOS vs. ORL', 'W', 30.0,
           12, 29, 0.414, 5, 11, 0.455, 8, 10, 0.800,
           8, 29, 37, 24, 8, 4, 12, 18, 112,
           '2024-25', 'playoffs', 'BOS'),
          (7, '0022400002', DATE '2024-10-22', 'DEN vs. OKC', 'L', 30.0,
           10, 28, 0.357, 3, 10, 0.300, 6, 8, 0.750,
           9, 26, 35, 21, 6, 2, 12, 16, 102,
           '2024-25', 'regular-season', 'DEN')
        """)
    finally:
        con.close()


@pytest.fixture()
def hist_db(tmp_path, monkeypatch):
    path = tmp_path / "hist.duckdb"
    _seed_hist(path)

    def fake_connect(read_only=False):
        return duckdb.connect(str(path), read_only=read_only)

    monkeypatch.setattr(store, "connect", fake_connect)
    return path


def _no_seeded_rows(table, where, params, fetch, season, **kw):
    if table == "silver_team_games":
        return [], {"source": "warehouse", "static_season": True,
                    "error": f"no seeded rows for {table} ({season}); "
                             "season complete, live refetch disabled"}
    return [], {}


def test_hist_slice_shape_and_order(hist_db):
    rows = team_mod._hist_team_games(2, "2024-25")
    assert len(rows) == 3  # playoffs row excluded, DEN row excluded
    assert [r["Game_ID"] for r in rows] == [
        "0022400001", "0022400015", "0022400030"]
    r0, r1, r2 = rows
    assert r0["GAME_DATE"] == "OCT 22, 2024"
    assert (r0["W"], r0["L"], r0["W_PCT"]) == (1, 0, 1.0)
    assert (r2["W"], r2["L"]) == (2, 1)
    assert r2["W_PCT"] == pytest.approx(2 / 3)
    assert r2["WL"] == "L" and r2["PTS"] == 108
    assert r0["_season"] == "2024-25"
    assert r0["_entity"] == "team:2"
    assert r0["_source"] == "sportsdataverse"


def test_hist_slice_matches_truth_aggregation(hist_db):
    rows = team_mod._hist_team_games(2, "2024-25")
    gp = len(rows)
    wins = sum(1 for r in rows if r["WL"] == "W")
    pts = sum(r["PTS"] for r in rows)
    fga = sum(r["FGA"] for r in rows)
    fta = sum(r["FTA"] for r in rows)
    assert (gp, wins, pts, fga, fta) == (3, 2, 341, 93, 30)
    ts = round(100 * pts / (2 * (fga + 0.44 * fta)), 1)
    assert ts == pytest.approx(round(100 * 341 / (2 * (93 + 0.44 * 30)), 1))


def test_hist_slice_empty_without_coverage(hist_db):
    assert team_mod._hist_team_games(2, "2021-22") == []
    assert team_mod._hist_team_games(7, "2021-22") == []


def test_get_team_hub_falls_back_to_hist(monkeypatch, hist_db):
    monkeypatch.setattr(team_mod, "_warehouse_or_live", _no_seeded_rows)
    monkeypatch.setattr(team_mod, "coerce_team_id", lambda v: 2)
    out = team_mod.get_team_hub.invoke({"team_id": "BOS", "season": "2024-25"})
    games = out["rows"]["games"]
    assert len(games) == 3
    assert out["meta"]["source"] == "warehouse:silver_hist_gamelogs"
    assert out["meta"]["season"] == "2024-25"
    assert out["meta"]["static_season"] is True


def test_get_team_hub_keeps_error_without_hist(monkeypatch, hist_db):
    monkeypatch.setattr(team_mod, "_warehouse_or_live", _no_seeded_rows)
    monkeypatch.setattr(team_mod, "coerce_team_id", lambda v: 2)
    out = team_mod.get_team_hub.invoke({"team_id": "BOS", "season": "2021-22"})
    assert out["rows"]["games"] == []


def test_get_team_hub_seeded_season_untouched(monkeypatch, hist_db):
    seeded = [{"GAME_DATE": "OCT 01, 2025", "WL": "W", "PTS": 120}]

    def fake_wol(table, where, params, fetch, season, **kw):
        if table == "silver_team_games":
            return list(seeded), {"rows": 1, "cached": True}
        return [], {}

    monkeypatch.setattr(team_mod, "_warehouse_or_live", fake_wol)
    monkeypatch.setattr(team_mod, "coerce_team_id", lambda v: 2)
    out = team_mod.get_team_hub.invoke({"team_id": "BOS", "season": "2025-26"})
    assert out["rows"]["games"] == seeded


def test_summary_exact_on_hist_slice(hist_db):
    # The 3-game fixture: PTS 115+118+108=341, FGA 30+32+31=93,
    # FTA 10+11+9=30. Same aggregates the bench truth computes.
    rows = team_mod._hist_team_games(2, "2024-25")
    s = team_mod._team_game_summary(rows, True)
    assert s["games"] == 3
    assert (s["wins"], s["losses"]) == (2, 1)
    assert s["covers_full_season"] is True
    assert s["ppg"] == pytest.approx(341 / 3, abs=0.05)
    assert s["ts_pct"] == pytest.approx(
        round(100 * 341 / (2 * (93 + 0.44 * 30)), 1))


def test_summary_realistic_rows_partial_season():
    games = [
        {"wl": "w", "pts": 115, "fga": 88, "fta": 22},
        {"wl": "L", "pts": 108, "fga": 90, "fta": 18},
    ]
    s = team_mod._team_game_summary(games, False)
    assert (s["games"], s["wins"], s["losses"]) == (2, 1, 1)
    assert s["covers_full_season"] is False
    assert s["ppg"] == pytest.approx(111.5)
    assert s["ts_pct"] == pytest.approx(
        round(100 * 223 / (2 * (178 + 0.44 * 40)), 1))


def test_summary_no_stat_columns_omits_rates():
    s = team_mod._team_game_summary(
        [{"WL": "W", "GAME_DATE": "OCT 01, 2025"}], True)
    assert s["wins"] == 1 and s["covers_full_season"] is True
    assert "ppg" not in s and "ts_pct" not in s


def test_summary_empty_games():
    assert team_mod._team_game_summary([], False) == {
        "games": 0, "wins": 0, "losses": 0, "covers_full_season": False}


def test_summary_partial_stats_uses_per_metric_denominators():
    # Instinct QA 2026-09-27 repro: 2 rows, one statless, silently
    # averaged 100 PTS over 2 games as ppg=50.0. Now a game counts
    # toward a metric only when that metric's fields exist.
    games = [
        {"WL": "W", "PTS": 100, "FGA": 90, "FTA": 20},
        {"WL": "L", "GAME_DATE": "OCT 01, 2025"},
    ]
    s = team_mod._team_game_summary(games, False)
    assert (s["games"], s["wins"], s["losses"]) == (2, 1, 1)
    assert s["ppg"] == pytest.approx(100.0)  # not 50.0
    assert s["ppg_games"] == 1
    assert s["ts_pct"] == pytest.approx(
        round(100 * 100 / (2 * (90 + 0.44 * 20)), 1))
    assert s["ts_pct_games"] == 1
    assert s["covers_full_season"] is False


def test_summary_pts_without_fga_counts_only_for_ppg():
    # PTS present but FGA/FTA missing: counts toward PPG, not TS%.
    games = [
        {"WL": "W", "PTS": 100, "FGA": 90, "FTA": 20},
        {"WL": "W", "PTS": 110},
    ]
    s = team_mod._team_game_summary(games, True)
    assert s["ppg"] == pytest.approx(105.0)
    assert s["ppg_games"] == 2
    assert s["ts_pct_games"] == 1
    # Row coverage is complete (the rows in hand ARE the season); stat
    # coverage is per-metric, so the flag stays a row-coverage claim.
    assert s["covers_full_season"] is True


def test_summary_full_coverage_carries_game_counts(hist_db):
    rows = team_mod._hist_team_games(2, "2024-25")
    s = team_mod._team_game_summary(rows, True)
    assert s["ppg_games"] == 3 and s["ts_pct_games"] == 3
    assert s["ppg"] == pytest.approx(341 / 3, abs=0.05)


def test_get_team_hub_summary_full_season_on_hist(monkeypatch, hist_db):
    monkeypatch.setattr(team_mod, "_warehouse_or_live", _no_seeded_rows)
    monkeypatch.setattr(team_mod, "coerce_team_id", lambda v: 2)
    out = team_mod.get_team_hub.invoke({"team_id": "BOS", "season": "2024-25"})
    rows = out["rows"]
    # summary rides ahead of the game list so it survives evidence clipping
    assert list(rows.keys()) == ["roster", "summary", "games"]
    s = rows["summary"]
    assert s["covers_full_season"] is True
    assert (s["games"], s["wins"], s["losses"]) == (3, 2, 1)
    assert s["ts_pct"] == pytest.approx(
        round(100 * 341 / (2 * (93 + 0.44 * 30)), 1))


def test_get_team_hub_summary_flags_capped_sample(monkeypatch, hist_db):
    # Live path returns a 25-row head of an 82-game season: the summary
    # must say so instead of masquerading as season totals.
    sample = [{"WL": "W", "PTS": 120, "FGA": 90, "FTA": 20}] * 25

    def fake_wol(table, where, params, fetch, season, **kw):
        if table == "silver_team_games":
            return list(sample), {"rows": 82, "cached": True}
        return [], {}

    monkeypatch.setattr(team_mod, "_warehouse_or_live", fake_wol)
    monkeypatch.setattr(team_mod, "coerce_team_id", lambda v: 2)
    out = team_mod.get_team_hub.invoke({"team_id": "BOS", "season": "2025-26"})
    s = out["rows"]["summary"]
    assert s["games"] == 25 and s["covers_full_season"] is False
    assert s["wins"] == 25
