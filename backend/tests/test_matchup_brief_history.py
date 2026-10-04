import asyncio
import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.sources import nba_stats  # noqa: E402
from shared.sources.base import FetchMeta, FetchResult  # noqa: E402
from shared.tools import team as team_mod  # noqa: E402
from shared.tools.prediction import get_game_prediction  # noqa: E402
from v2.adapters import AdapterError, call_capability  # noqa: E402

STORED_RATINGS_TABLE = "silver_team_ratings"
HIST_RATINGS_TABLE = "silver_hist_gamelogs"

BOS = 1610612738
NYK = 1610612752
WAS = 1610612764
MIA = 1610612748

_HIST_COLUMNS = (
    "team_id INTEGER, team_abbreviation VARCHAR, game_id VARCHAR, "
    "game_date DATE, matchup VARCHAR, wl VARCHAR, min DOUBLE, "
    "fgm INTEGER, fga INTEGER, fg_pct DOUBLE, "
    "fg3m INTEGER, fg3a INTEGER, fg3_pct DOUBLE, "
    "ftm INTEGER, fta INTEGER, ft_pct DOUBLE, "
    "oreb INTEGER, dreb INTEGER, reb INTEGER, "
    "ast INTEGER, stl INTEGER, blk INTEGER, "
    "tov INTEGER, pf INTEGER, pts INTEGER, "
    "season_type VARCHAR, _season VARCHAR"
)

_HIST_ROWS = [
    (BOS, "BOS", "0022400061", "2024-10-22", "BOS vs. NYK", "W", 240.0,
     40, 82, 0.488, 8, 26, 0.308, 20, 22, 0.909,
     8, 31, 39, 26, 6, 4, 13, 19, 132, "regular-season", "2024-25"),
    (NYK, "NYK", "0022400061", "2024-10-22", "NYK @ BOS", "L", 240.0,
     35, 78, 0.449, 7, 27, 0.259, 18, 20, 0.900,
     7, 30, 37, 24, 5, 3, 15, 20, 109, "regular-season", "2024-25"),
    (BOS, "BOS", "0022400748", "2025-02-08", "BOS @ NYK", "W", 240.0,
     39, 80, 0.488, 10, 28, 0.357, 22, 24, 0.917,
     6, 33, 39, 28, 7, 5, 12, 18, 131, "regular-season", "2024-25"),
    (NYK, "NYK", "0022400748", "2025-02-08", "NYK vs. BOS", "L", 240.0,
     34, 79, 0.430, 5, 25, 0.200, 18, 21, 0.857,
     9, 30, 39, 22, 6, 2, 14, 19, 104, "regular-season", "2024-25"),
    (BOS, "BOS", "0022400090", "2024-11-02", "BOS @ WAS", "W", 240.0,
     42, 85, 0.494, 9, 27, 0.333, 18, 20, 0.900,
     10, 32, 42, 27, 8, 4, 14, 21, 128, "regular-season", "2024-25"),
    (WAS, "WAS", "0022400090", "2024-11-02", "WAS vs. BOS", "L", 240.0,
     36, 80, 0.450, 8, 26, 0.308, 16, 19, 0.842,
     8, 33, 41, 23, 5, 4, 15, 22, 110, "regular-season", "2024-25"),
    (NYK, "NYK", "0022400100", "2024-11-05", "NYK vs. MIA", "W", 240.0,
     41, 83, 0.494, 11, 30, 0.367, 17, 19, 0.895,
     9, 31, 40, 26, 6, 3, 13, 20, 129, "regular-season", "2024-25"),
    (MIA, "MIA", "0022400100", "2024-11-05", "MIA @ NYK", "L", 240.0,
     37, 81, 0.457, 9, 28, 0.321, 15, 18, 0.833,
     11, 30, 41, 24, 7, 5, 16, 21, 112, "regular-season", "2024-25"),
    (BOS, "BOS", "0022500900", "2025-05-01", "BOS vs. NYK", "L", 240.0,
     35, 80, 0.438, 7, 27, 0.259, 15, 18, 0.833,
     9, 30, 39, 24, 6, 3, 14, 20, 105, "playoffs", "2024-25"),
    (NYK, "NYK", "0022500900", "2025-05-01", "NYK @ BOS", "W", 240.0,
     40, 79, 0.506, 11, 27, 0.407, 20, 22, 0.909,
     7, 34, 41, 27, 7, 4, 12, 18, 118, "playoffs", "2024-25"),
]


def _seed(path: Path) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE TABLE silver_hist_gamelogs ({_HIST_COLUMNS})")
        con.executemany(
            f"INSERT INTO silver_hist_gamelogs VALUES ({', '.join('?' * 27)})",
            [list(row) for row in _HIST_ROWS],
        )
        con.execute(
            "CREATE TABLE silver_team_games ("
            "Game_ID VARCHAR, GAME_DATE VARCHAR, MATCHUP VARCHAR, "
            "WL VARCHAR, PTS DOUBLE, _season VARCHAR, _entity VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_team_games VALUES (?, ?, ?, ?, ?, ?, ?)",
            [["0022500001", "OCT 22, 2025", "BOS vs. NYK", "W", 118.0,
              "2025-26", f"team:{BOS}"]],
        )
        con.execute(
            "CREATE TABLE silver_team_ratings ("
            "TEAM_ID BIGINT, TEAM_NAME VARCHAR, GP INTEGER, W INTEGER, "
            "L INTEGER, OFF_RATING DOUBLE, DEF_RATING DOUBLE, "
            "NET_RATING DOUBLE, PACE DOUBLE, _season VARCHAR, "
            "_source VARCHAR, _fetched_at VARCHAR)"
        )
        con.executemany(
            "INSERT INTO silver_team_ratings VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                [BOS, "Boston Celtics", 82, 61, 21, 118.9, 109.6, 9.3,
                 97.0, "2024-25", "fixture", "2026-04-14T00:00:00Z"],
                [NYK, "New York Knicks", 82, 51, 31, 117.7, 113.6, 4.2,
                 98.3, "2024-25", "fixture", "2026-04-14T00:00:00Z"],
            ],
        )
        con.execute(
            "CREATE TABLE silver_playoffs ("
            "TEAM_ID BIGINT, TEAM_NAME VARCHAR, TEAM_ABBREVIATION VARCHAR, "
            "GAME_ID VARCHAR, GAME_DATE VARCHAR, MATCHUP VARCHAR, "
            "WL VARCHAR, PTS DOUBLE, _season VARCHAR)"
        )
        con.execute(
            "INSERT INTO silver_playoffs VALUES "
            f"({BOS}, 'Boston Celtics', 'BOS', '0042500101', '2025-05-01', "
            "'BOS vs. NYK', 'W', 118.0, '2025-26')"
        )
        con.execute(
            "CREATE TABLE silver_injuries ("
            "display_name VARCHAR, injuries VARCHAR, _season VARCHAR, "
            "_fetched_at VARCHAR)"
        )
    finally:
        con.close()


@pytest.fixture()
def brief_db(tmp_path, monkeypatch):
    path = tmp_path / "brief.duckdb"
    _seed(path)

    def fake_connect(read_only=None):
        if read_only is None:
            read_only = True
        return duckdb.connect(str(path), read_only=read_only)

    monkeypatch.setattr(store, "connect", fake_connect)
    return path


def _drop_season_from(table, season):
    con = store.connect(read_only=False)
    try:
        con.execute(f"DELETE FROM {table} WHERE _season = ?", [season])
    finally:
        con.close()


def _forbid_live_ratings(monkeypatch):
    def forbidden(season):
        raise AssertionError(f"live ratings fetch for {season}")

    monkeypatch.setattr(nba_stats, "team_ratings", forbidden)


class _StubTool:
    def __init__(self, payload):
        self._payload = payload

    async def ainvoke(self, arguments):
        return self._payload


def test_brief_for_2024_25_composes_every_section(brief_db):
    env = call_capability(
        "matchup_brief",
        {"a": "BOS", "b": "NYK", "season": "2024-25"},
    )
    rows = env.rows
    assert env.capability == "matchup_brief"
    assert env.season == "2024-25"
    assert rows["teams"] == ["BOS", "NYK"]
    assert rows["ratings"]["BOS"]["NET_RATING"] == 9.3
    assert rows["ratings"]["NYK"]["NET_RATING"] == 4.2
    assert rows["form"]["BOS"]["last10"] == "3-0"
    assert rows["form"]["NYK"]["last10"] == "1-2"
    summary = rows["season_series"]["summary"]
    assert summary["games"] == 2
    assert summary["games_won"] == {"BOS": 2, "NYK": 0}
    assert summary["series_played"] is None
    assert summary["series"] is None
    assert rows["prediction"]["win_prob"]["BOS"] > 0.5
    assert rows["prediction"]["ratings_source"] == "silver_team_ratings"
    assert env.qualification
    assert env.coverage


def test_brief_carries_unknown_injuries_instead_of_refusing(brief_db):
    env = call_capability(
        "matchup_brief",
        {"a": "BOS", "b": "NYK", "season": "2024-25"},
    )
    for abbr in ("BOS", "NYK"):
        section = env.rows["injuries"][abbr]
        assert section["availability_known"] is False
        assert section["impact"] == "unknown"
        assert section["out"] == []


def test_brief_season_series_excludes_playoff_rows_from_history(brief_db):
    env = call_capability(
        "matchup_brief",
        {"a": "BOS", "b": "NYK", "season": "2024-25"},
    )
    games = env.rows["season_series"]["games"]
    assert [game["phase"] for game in games] == [
        "regular season", "regular season"]
    assert all(game["game_id"].startswith("0022") for game in games)


def test_brief_derived_ratings_when_season_absent_from_team_ratings(
    brief_db,
):
    con = store.connect(read_only=False)
    try:
        con.execute("DELETE FROM silver_team_ratings WHERE _season = '2024-25'")
    finally:
        con.close()
    out = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25", "n_sims": 2000})
    assert out["ok"] is True
    assert out["inputs"]["ratings_source"] == "silver_hist_gamelogs"
    assert out["meta"]["ratings_fetched_at"] is None
    assert out["inputs"]["home"]["record"] == "3-0"
    assert out["inputs"]["away"]["record"] == "1-2"


def test_prediction_fails_loud_when_no_ratings_source_has_the_season(
    brief_db,
):
    out = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2009-10", "n_sims": 2000})
    assert out["ok"] is False
    assert "ratings" in out["error"]


def test_brief_without_a_stored_season_shares_one_derived_provenance(
    brief_db, monkeypatch,
):
    _drop_season_from(STORED_RATINGS_TABLE, "2024-25")
    _forbid_live_ratings(monkeypatch)

    env = call_capability(
        "matchup_brief",
        {"a": "BOS", "b": "NYK", "season": "2024-25"},
    )

    assert env.rows["ratings_provenance"] == {
        "kind": "derived", "source": HIST_RATINGS_TABLE}
    assert env.rows["prediction"]["ratings_source"] == HIST_RATINGS_TABLE
    simulation = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25", "n_sims": 2000})
    assert env.rows["ratings"]["BOS"]["NET_RATING"] == pytest.approx(
        simulation["inputs"]["home"]["net_rating"], abs=0.1)
    assert env.rows["ratings"]["BOS"]["NET_RATING"] != pytest.approx(9.3, abs=0.01)
    assert "derived" in env.source
    assert "warehouse" not in env.source


def test_brief_keeps_stored_ratings_when_the_season_is_stored(brief_db):
    env = call_capability(
        "matchup_brief",
        {"a": "BOS", "b": "NYK", "season": "2024-25"},
    )

    assert env.rows["ratings_provenance"] == {
        "kind": "stored", "source": STORED_RATINGS_TABLE}
    assert env.rows["prediction"]["ratings_source"] == STORED_RATINGS_TABLE
    assert env.rows["ratings"]["BOS"]["NET_RATING"] == 9.3
    assert "warehouse" in env.source


def test_brief_fails_loud_when_no_ratings_source_has_the_season(
    brief_db, monkeypatch,
):
    monkeypatch.setattr(
        nba_stats, "team_ratings",
        lambda season: FetchResult(
            frame=pl.DataFrame(),
            meta=FetchMeta(source=nba_stats.SOURCE, season=season),
            ok=False, error="upstream returned nothing"))

    out = asyncio.run(team_mod.get_matchup_brief.ainvoke(
        {"a": "BOS", "b": "NYK", "season": "2009-10"}))

    assert out["ok"] is False
    assert "rows" not in out
    for named in ("2009-10", STORED_RATINGS_TABLE, HIST_RATINGS_TABLE):
        assert named in out["error"], named
    with pytest.raises(AdapterError):
        call_capability(
            "matchup_brief",
            {"a": "BOS", "b": "NYK", "season": "2009-10"},
        )


def test_brief_fails_when_card_and_simulation_disagree_on_provenance(
    brief_db, monkeypatch,
):
    simulation = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25", "n_sims": 2000})
    assert simulation["inputs"]["ratings_source"] == STORED_RATINGS_TABLE
    disagreeing = dict(simulation)
    disagreeing["inputs"] = {
        **simulation["inputs"],
        "ratings_provenance": "derived",
        "ratings_source": HIST_RATINGS_TABLE,
    }
    monkeypatch.setattr(
        "shared.tools.prediction.get_game_prediction",
        _StubTool(disagreeing))

    out = asyncio.run(team_mod.get_matchup_brief.ainvoke(
        {"a": "BOS", "b": "NYK", "season": "2024-25"}))

    assert out["ok"] is False
    assert "rows" not in out
    for named in (STORED_RATINGS_TABLE, HIST_RATINGS_TABLE):
        assert named in out["error"], named


def test_brief_rejects_wrong_subject_end_to_end(brief_db):
    with pytest.raises(AdapterError):
        call_capability(
            "matchup_brief",
            {"a": "BOS", "b": "ZZZ", "season": "2024-25"},
        )
    with pytest.raises(AdapterError):
        call_capability(
            "matchup_brief",
            {"a": "BOS", "b": "BOS", "season": "2024-25"},
        )


def test_playoff_rows_in_history_never_become_a_series_record(brief_db):
    con = store.connect(read_only=True)
    try:
        present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in ("silver_playoffs", "silver_playoff_gamelogs"):
            if table not in present:
                continue
            covered = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE _season = '2024-25'"
            ).fetchone()[0]
            if covered:
                pytest.skip(f"{table} covers 2024-25 in this fixture")
    finally:
        con.close()

    out = team_mod.get_season_series.invoke(
        {"team_a": "BOS", "team_b": "NYK", "season": "2024-25"})

    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 2
    assert summary["series_played"] is None
    assert summary["series_won"] is None
    assert summary["series"] is None
    assert "playoffs" not in summary["games_by_phase"]
    assert out["meta"]["coverage"]["regular season"]["source"] == (
        HIST_RATINGS_TABLE)
    assert out["meta"]["coverage"]["playoffs"]["source"] is None


def test_season_series_fails_loud_for_a_pairing_that_never_met(brief_db):
    out = team_mod.get_season_series.invoke(
        {"team_a": "BOS", "team_b": "MIA", "season": "2024-25"})
    assert out["ok"] is False
    assert "do not report a 0-0 record" in out["error"].lower()


def test_splits_read_history_when_team_games_lacks_the_season(brief_db):
    out = team_mod.get_team_splits.invoke(
        {"team": "BOS", "season": "2024-25"})
    assert out["ok"] is True
    splits = {row["split"]: row for row in out["rows"]}
    assert splits["home"]["GP"] == 1
    assert splits["away"]["GP"] == 2
    assert splits["wins"]["GP"] == 3
    assert splits["losses"]["GP"] == 0
    assert splits["OCT"]["GP"] == 1
    assert splits["NOV"]["GP"] == 1
    assert splits["FEB"]["GP"] == 1
    assert splits["last10"]["W"] == 3
    assert splits["home"]["PPG"] == 132.0


def test_splits_keeps_the_stored_slice_when_it_has_the_season(brief_db):
    out = team_mod.get_team_splits.invoke(
        {"team": "BOS", "season": "2025-26"})
    assert out["ok"] is True
    splits = {row["split"]: row for row in out["rows"]}
    assert splits["home"]["GP"] == 1
    assert splits["wins"]["W"] == 1