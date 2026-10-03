import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seed_team_ratings as seed
from shared import store
from shared.sources.base import FetchMeta, FetchResult


@pytest.fixture
def scratch(monkeypatch, tmp_path):
    db = tmp_path / "ratings.duckdb"
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setenv("DIME_ENV", "dev")
    monkeypatch.delenv("DIME_STATE_DB", raising=False)
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(seed, "BACKOFF_S", 0)
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return db


def _frame(n_teams=30):
    rows = []
    for i in range(n_teams):
        rows.append({
            "TEAM_ID": 1610612700 + i,
            "TEAM_NAME": f"Team {i}",
            "GP": 82,
            "W": 50 - i,
            "L": 32 + i,
            "OFF_RATING": 120.0 - i * 0.2,
            "DEF_RATING": 108.0 + i * 0.2,
            "NET_RATING": 12.0 - i * 0.4,
            "PACE": 99.0,
            "TS_PCT": 0.590,
            "TM_TOV_PCT": 12.5,
        })
    return pl.DataFrame(rows)


def _ok(season, n_teams=30):
    return FetchResult(
        frame=_frame(n_teams),
        meta=FetchMeta(source="nba_api", season=season),
    )


def _count(season):
    con = store.connect(read_only=True)
    try:
        if "silver_team_ratings" not in store.tables():
            return 0
        return con.execute(
            "SELECT COUNT(*) FROM silver_team_ratings WHERE _season = ?",
            [season],
        ).fetchone()[0]
    finally:
        con.close()


def _provenance(season):
    con = store.connect(read_only=True)
    try:
        return con.execute(
            """SELECT DISTINCT _source, _season, _entity,
               COUNT(*) AS n, COUNT(_fetched_at) AS stamped
            FROM silver_team_ratings WHERE _season = ?
            GROUP BY _source, _season, _entity""",
            [season],
        ).fetchall()
    finally:
        con.close()


def test_seed_writes_provenance_on_every_row(scratch, monkeypatch):
    monkeypatch.setattr(seed, "fetch", lambda season: _ok(season))
    assert seed.main(["--seasons", "2024-25,2023-24"]) == 0
    for season in ("2024-25", "2023-24"):
        assert _count(season) == 30
        prov = _provenance(season)
        assert len(prov) == 1
        source, stamped_season, entity, n, stamped = prov[0]
        assert source == "nba_api"
        assert stamped_season == season
        assert entity == "teamratings:overall"
        assert n == 30
        assert stamped == 30


def test_rerun_skips_completed_units(scratch, monkeypatch):
    calls = []

    def fake_fetch(season):
        calls.append(season)
        return _ok(season)

    monkeypatch.setattr(seed, "fetch", fake_fetch)
    assert seed.main(["--seasons", "2024-25,2023-24"]) == 0
    assert sorted(calls) == ["2023-24", "2024-25"]
    assert seed.main(["--seasons", "2024-25,2023-24"]) == 0
    assert sorted(calls) == ["2023-24", "2024-25"]
    assert _count("2024-25") == 30


def test_rerun_after_clearing_watermark_replaces_without_duplicates(
        scratch, monkeypatch):
    monkeypatch.setattr(seed, "fetch", lambda season: _ok(season))
    assert seed.main(["--seasons", "2024-25"]) == 0
    assert _count("2024-25") == 30
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.execute("DELETE FROM fetch_log WHERE entity = ?",
                        [seed.ENTITY])
    finally:
        con.close()
    monkeypatch.setattr(seed, "fetch", lambda season: _ok(season, n_teams=29))
    assert seed.main(["--seasons", "2024-25"]) == 0
    assert _count("2024-25") == 29


def test_failure_records_fetch_log_and_returns_nonzero(scratch, monkeypatch):
    monkeypatch.setattr(
        seed, "fetch",
        lambda season: FetchResult(frame=pl.DataFrame(),
                                   meta=FetchMeta(source="nba_api",
                                                  season=season),
                                   ok=False, error="boom"))
    assert seed.main(["--seasons", "2024-25"]) == 1
    con = store.connect(read_only=True)
    try:
        row = con.execute(
            """SELECT rows FROM fetch_log
            WHERE dataset = ? AND season = ? AND entity = ?""",
            [seed.TABLE, "2024-25", seed.ENTITY],
        ).fetchone()
    finally:
        con.close()
    assert row is not None
    assert int(row[0]) == -1
    assert _count("2024-25") == 0


def test_failed_unit_is_retried_on_next_run(scratch, monkeypatch):
    attempts = []

    def flaky(season):
        attempts.append(season)
        if len(attempts) == 1:
            return FetchResult(frame=pl.DataFrame(),
                               meta=FetchMeta(source="nba_api",
                                              season=season),
                               ok=False, error="boom")
        return _ok(season)

    monkeypatch.setattr(seed, "fetch", flaky)
    assert seed.main(["--seasons", "2024-25"]) == 0
    assert _count("2024-25") == 30


def test_refuses_without_scratch_db(monkeypatch, tmp_path):
    calls = []
    monkeypatch.delenv("DIME_WAREHOUSE", raising=False)
    monkeypatch.setattr(seed, "fetch",
                        lambda season: calls.append(season) or _ok(season))
    assert seed.main(["--seasons", "2024-25"]) == 1
    assert calls == []


def test_positional_seasons_override_default(scratch, monkeypatch):
    calls = []
    monkeypatch.setattr(seed, "fetch",
                        lambda season: calls.append(season) or _ok(season))
    assert seed.main(["2024-25"]) == 0
    assert calls == ["2024-25"]


def test_refuses_prod_env_without_explicit_scratch_db(monkeypatch, tmp_path):
    db = tmp_path / "ratings.duckdb"
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setenv("DIME_ENV", "prod")
    def _must_not_fetch(season):
        raise AssertionError("seeder must not fetch against prod")
    monkeypatch.setattr(seed, "fetch", _must_not_fetch)
    assert seed.main(["--seasons", "2024-25"]) == 1
    assert not db.exists()


def test_explicit_scratch_db_opts_in_without_env(monkeypatch, tmp_path):
    db = tmp_path / "ratings.duckdb"
    monkeypatch.delenv("DIME_WAREHOUSE", raising=False)
    monkeypatch.delenv("DIME_ENV", raising=False)
    monkeypatch.setattr(seed, "fetch", lambda season: _ok(season))
    assert seed.main(["--seasons", "2024-25", "--scratch-db", str(db)]) == 0
    assert db.exists()
