import sys
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools import league as league_mod  # noqa: E402
from shared.tools import team as team_mod  # noqa: E402
from v2.adapters import call_capability  # noqa: E402

REPO_WAREHOUSE = (
    Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
)


@contextmanager
def _warehouse():
    con = duckdb.connect(str(REPO_WAREHOUSE), read_only=True)
    try:
        yield con
    finally:
        con.close()


def _skip_without_warehouse():
    if not REPO_WAREHOUSE.exists():
        pytest.skip(f"no warehouse at {REPO_WAREHOUSE}")
    with _warehouse() as con:
        return con.execute("SHOW TABLES").fetchall()


def _trailing_games(con, team, season, count):
    return con.execute(
        "SELECT pts FROM ("
        "  SELECT pts, game_id, CAST(game_date AS DATE) AS played"
        "  FROM silver_hist_gamelogs"
        "  WHERE _season = ? AND season_type = 'regular-season'"
        "    AND team_abbreviation = ?"
        "  ORDER BY played DESC, game_id ASC LIMIT ?"
        ") ORDER BY played DESC, game_id ASC",
        [season, team, count],
    ).fetchall()


def _season_games_won(con, team, opponent, season):
    return con.execute(
        "SELECT COUNT(*) FILTER (WHERE wl = 'W') FROM silver_hist_gamelogs"
        " WHERE _season = ? AND season_type = 'regular-season'"
        "   AND team_abbreviation = ? AND matchup ILIKE ?",
        [season, team, f"%{opponent}%"],
    ).fetchone()[0]


def _season_points_pg(con, team_city, season):
    return con.execute(
        "SELECT PointsPG FROM silver_standings"
        " WHERE _season = ? AND TeamCity = ?",
        [season, team_city],
    ).fetchone()[0]


def _playoff_round_wins(con, team, opponent, season, round_code):
    return con.execute(
        "SELECT COUNT(*) FILTER (WHERE wl = 'W'), COUNT(DISTINCT game_id)"
        " FROM silver_playoffs"
        " WHERE _season = ? AND team_abbreviation = ? AND MATCHUP ILIKE ?"
        "   AND SUBSTR(game_id, 8, 1) = ?",
        [season, team, f"%{opponent}%", round_code],
    ).fetchone()


def _brief(a, b, season):
    env = call_capability("matchup_brief", {"a": a, "b": b, "season": season})
    assert env.capability == "matchup_brief"
    return env.rows


def _split(rows, name):
    return next(row for row in rows if row["split"] == name)


def test_warehouse_carries_the_tables_the_number_assertions_read():
    tables = {row[0] for row in _skip_without_warehouse()}
    assert {
        "silver_hist_gamelogs", "silver_standings", "silver_playoffs",
        "silver_leaders_ast", "silver_advanced",
    } <= tables


@pytest.mark.parametrize(
    "a, b, season, city_a, city_b",
    [
        ("MIN", "DAL", "2024-25", "Minnesota", "Dallas"),
        ("OKC", "DEN", "2024-25", "Oklahoma City", "Denver"),
    ],
)
def test_brief_last_ten_rate_equals_the_warehouse_last_ten_games(
    a, b, season, city_a, city_b,
):
    _skip_without_warehouse()
    rows = _brief(a, b, season)
    with _warehouse() as con:
        for abbr, city in ((a, city_a), (b, city_b)):
            games = _trailing_games(con, abbr, season, 10)
            published = _split(rows["form"][abbr]["splits"], "last10")
            assert published["PPG"] == pytest.approx(
                round(sum(point for (point,) in games) / len(games), 1))
            assert published["PPG_GAMES"] == len(games) == published["GP"]
            assert published["window"]["games"] == len(games)


@pytest.mark.parametrize(
    "a, b, season, city_a, city_b",
    [
        ("MIN", "DAL", "2024-25", "Minnesota", "Dallas"),
        ("OKC", "DEN", "2024-25", "Oklahoma City", "Denver"),
    ],
)
def test_last_ten_rate_is_not_answering_the_season_points_per_game(
    a, b, season, city_a, city_b,
):
    _skip_without_warehouse()
    rows = _brief(a, b, season)
    with _warehouse() as con:
        for abbr, city in ((a, city_a), (b, city_b)):
            season_ppg = _season_points_pg(con, city, season)
            published = _split(rows["form"][abbr]["splits"], "last10")
            assert published["PPG"] != pytest.approx(season_ppg)
            assert published["window"]["kind"] == "trailing_games"
            assert published["window"]["games"] == 10
            assert published["window"]["season"] == season


def test_every_split_rate_names_the_window_it_was_measured_over():
    _skip_without_warehouse()
    rows = _brief("MIN", "DAL", "2024-25")
    for name in ("home", "away", "wins", "losses", "last10"):
        row = _split(rows["form"]["MIN"]["splits"], name)
        window = row["window"]
        assert window["label"], name
        assert window["season"] == "2024-25", name
        assert row["PPG_GAMES"] <= row["GP"], name
        assert row["PPG"] is None or row["PPG_GAMES"] == window["games"], name


_GAMELOG_DDL = (
    "CREATE TABLE silver_hist_gamelogs ("
    "team_id INTEGER, team_abbreviation VARCHAR, game_id VARCHAR, "
    "game_date DATE, matchup VARCHAR, wl VARCHAR, pts DOUBLE, "
    "fga INTEGER, fta INTEGER, season_type VARCHAR, _season VARCHAR)"
)

SYNTHETIC_TEAM = "POR"
SYNTHETIC_SEASON = "2024-25"


def _synthetic(tmp_path, monkeypatch, pts_values, wl_values):
    path = tmp_path / "synthetic.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(f"ATTACH '{REPO_WAREHOUSE}' AS src (READ_ONLY)")
        for table in ("silver_hist_gamelogs", "silver_team_games"):
            con.execute(
                f"CREATE TABLE {table} AS "
                f"SELECT * FROM src.{table} LIMIT 0")
        for index, (pts, wl) in enumerate(zip(pts_values, wl_values)):
            con.execute(
                "INSERT INTO silver_hist_gamelogs (team_id, "
                "team_abbreviation, game_id, game_date, matchup, wl, pts, "
                "season_type, _season) VALUES (?, ?, ?, ?, 'POR vs. BOS', "
                "?, ?, 'regular-season', ?)",
                [team_mod.coerce_team_id(SYNTHETIC_TEAM), SYNTHETIC_TEAM,
                 f"0022400{index:03d}", f"2024-11-{index + 1:02d}",
                 wl, pts, SYNTHETIC_SEASON],
            )
    finally:
        con.close()

    def fake_connect(read_only=None):
        if read_only is None:
            read_only = True
        return duckdb.connect(str(path), read_only=read_only)

    monkeypatch.setattr(store, "connect", fake_connect)
    return path


def _synthetic_splits():
    out = team_mod.get_team_splits.invoke(
        {"team": SYNTHETIC_TEAM, "season": SYNTHETIC_SEASON})
    assert out["ok"] is True
    return out


def test_split_omits_a_rate_the_warehouse_cannot_supply(tmp_path, monkeypatch):
    _synthetic(tmp_path, monkeypatch, [None, None, None], ["W", "W", "L"])
    row = _split(_synthetic_splits()["rows"], "last10")
    assert row["GP"] == 3
    assert row["PPG"] is None
    assert row["PPG_GAMES"] == 0


def test_split_divides_a_rate_by_the_games_that_carry_a_score(
    tmp_path, monkeypatch,
):
    _synthetic(tmp_path, monkeypatch, [120.0, None, 90.0], ["W", "L", "W"])
    row = _split(_synthetic_splits()["rows"], "last10")
    assert row["GP"] == 3
    assert row["PPG_GAMES"] == 2
    assert row["PPG"] == pytest.approx(round((120.0 + 90.0) / 2, 1))


def test_split_does_not_count_an_undecided_game_as_a_loss(
    tmp_path, monkeypatch,
):
    _synthetic(tmp_path, monkeypatch, [120.0, 90.0, 0.0], ["W", "L", None])
    row = _split(_synthetic_splits()["rows"], "last10")
    assert row["GP"] == 3
    assert row["W"] == 1
    assert row["L"] == 1
    assert row["UNDECIDED"] == 1
    assert row["W"] + row["L"] + row["UNDECIDED"] == row["GP"]


def test_warehouse_undecided_game_is_not_published_as_a_loss():
    _skip_without_warehouse()
    with _warehouse() as con:
        undecided = con.execute(
            "SELECT team_abbreviation, _season FROM silver_hist_gamelogs"
            " WHERE season_type = 'regular-season' AND wl IS NULL"
        ).fetchall()
    assert undecided
    for abbr, season in undecided:
        out = team_mod.get_team_splits.invoke(
            {"team": abbr, "season": season})
        assert out["ok"] is True
        row = _split(out["rows"], "last10")
        assert row["UNDECIDED"] == row["GP"] - row["W"] - row["L"]


@pytest.mark.parametrize(
    "a, b, season, round_code",
    [
        ("BOS", "NYK", "2024-25", "2"),
        ("OKC", "DEN", "2024-25", "2"),
    ],
)
def test_season_series_keeps_game_wins_and_series_wins_distinct(
    a, b, season, round_code,
):
    _skip_without_warehouse()
    summary = _brief(a, b, season)["season_series"]["summary"]
    with _warehouse() as con:
        wins_a = _season_games_won(con, a, b, season)
        wins_b = _season_games_won(con, b, a, season)
        series_a, series_games = _playoff_round_wins(
            con, a, b, season, round_code)
        series_b, _ = _playoff_round_wins(con, b, a, season, round_code)
    assert summary["games"] == wins_a + wins_b + series_games
    assert summary["games_won"] == {a: wins_a + series_a,
                                    b: wins_b + series_b}
    assert summary["series_played"] == 1
    assert summary["series_won"] == {
        a: int(series_a > series_b), b: int(series_b > series_a)}
    assert summary["games_by_phase"]["playoffs"] == series_games
    assert summary["games_won_by_phase"]["playoffs"] == {
        a: series_a, b: series_b}
    assert summary["games_won_by_phase"]["regular season"] == {
        a: wins_a, b: wins_b}
    assert summary["series"][0]["games"] == series_games
    assert summary["series"][0]["games_won"] == {a: series_a, b: series_b}
    assert summary["games_undecided"] == 0


def test_a_game_count_never_satisfies_a_series_count():
    _skip_without_warehouse()
    summary = _brief("BOS", "NYK", "2024-25")["season_series"]["summary"]
    assert summary["games_won"]["NYK"] != summary["series_won"]["NYK"]
    assert summary["games_won"]["NYK"] == 4
    assert summary["series_won"]["NYK"] == 1
    assert summary["series_won"] != summary["games_won"]
    assert summary["series_played"] != summary["games"]
    series_games = summary["series"][0]["games_won"]
    assert series_games != summary["games_won"]
    assert sum(summary["series_won"].values()) <= summary["series_played"]


def test_a_pairing_with_no_playoff_meeting_reports_no_series():
    _skip_without_warehouse()
    summary = _brief("LAL", "GSW", "2024-25")["season_series"]["summary"]
    assert summary["series_played"] == 0
    assert summary["series_won"] == {"LAL": 0, "GSW": 0}
    assert summary["series"] == []
    assert summary["games_won"] == {"LAL": 3, "GSW": 1}


def _leader_floor(con, table, season, player):
    return con.execute(
        f"SELECT MIN FROM {table} WHERE _season = ? AND PLAYER = ?",
        [season, player],
    ).fetchone()[0]


def test_leader_qualification_publishes_the_value_the_floor_applies_to():
    _skip_without_warehouse()
    with _warehouse() as con:
        season = con.execute(
            "SELECT _season FROM silver_leaders_ast"
            " WHERE _season IS NOT NULL ORDER BY _season DESC LIMIT 1"
        ).fetchone()[0]
        out = league_mod.get_leaders.invoke(
            {"stat_category": "APG", "season": season})
        assert out["ok"] is True
        lead = out["rows"][0]
        floor = out["meta"]["qualification_floor"]
        assert floor["metric"] == "total_minutes"
        minutes = _leader_floor(con, "silver_leaders_ast", season,
                                lead["PLAYER"])
        assert lead["MIN"] == minutes
        assert minutes >= floor["floor"] == 500
        assert f"{round(minutes):,}" in out["meta"]["deterministic_answer"]
        assert "total minutes" in out["meta"]["deterministic_answer"]


def test_per_game_minutes_cannot_answer_the_total_minutes_floor():
    _skip_without_warehouse()
    with _warehouse() as con:
        season = con.execute(
            "SELECT _season FROM silver_advanced"
            " WHERE _season IS NOT NULL ORDER BY _season DESC LIMIT 1"
        ).fetchone()[0]
    out = league_mod.get_leaders.invoke(
        {"stat_category": "TS_PCT", "season": season})
    assert out["ok"] is True
    lead = out["rows"][0]
    floor = out["meta"]["qualification_floor"]
    assert floor["metric"] == "total_minutes"
    assert lead["TOTAL_MINUTES"] == pytest.approx(
        lead["GP"] * lead["MPG"])
    assert lead["TOTAL_MINUTES"] >= floor["floor"] == 1000
    assert lead["TOTAL_MINUTES"] != lead["MPG"]
    assert f"{round(lead['TOTAL_MINUTES']):,}" in (
        out["meta"]["deterministic_answer"])
    assert "per game" not in out["meta"]["qualification"]


_LEADERS_WITHOUT_MINUTES = (
    "CREATE TABLE silver_leaders_ast ("
    "PLAYER TEXT, TEAM TEXT, GP INTEGER, AST INTEGER, _season VARCHAR)"
)


def _floorless_warehouse(tmp_path, monkeypatch):
    path = tmp_path / "floorless.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(_LEADERS_WITHOUT_MINUTES)
        con.execute(
            "INSERT INTO silver_leaders_ast VALUES "
            "('Sample Guard', 'XYZ', 70, 400, '2024-25')"
        )
    finally:
        con.close()

    def fake_connect(read_only=None):
        if read_only is None:
            read_only = True
        return duckdb.connect(str(path), read_only=read_only)

    monkeypatch.setattr(store, "connect", fake_connect)
    return path


def test_leader_answer_fails_loud_when_the_qualification_value_is_missing(
    tmp_path, monkeypatch,
):
    _floorless_warehouse(tmp_path, monkeypatch)
    out = league_mod.get_leaders.invoke(
        {"stat_category": "APG", "season": "2024-25"})
    assert out["ok"] is False
    assert out["rows"] == []
    assert "total minutes" in out["error"]
    assert "silver_leaders_ast" in out["error"]
    assert "refusing to publish" in out["error"]


def test_leader_board_publishes_the_floor_value_for_every_row():
    _skip_without_warehouse()
    with _warehouse() as con:
        season = con.execute(
            "SELECT _season FROM silver_leaders_ast"
            " ORDER BY _season DESC LIMIT 1"
        ).fetchone()[0]
    out = league_mod.get_leaders.invoke(
        {"stat_category": "APG", "season": season})
    assert out["ok"] is True
    for row in out["rows"]:
        assert row["MIN"] is not None
        assert row["MIN"] >= out["meta"]["qualification_floor"]["floor"]
    lead = out["rows"][0]
    assert f"{lead['MIN']:,.0f} total minutes" in (
        out["meta"]["deterministic_answer"])


def test_leader_rate_in_the_row_and_in_the_answer_are_one_number():
    _skip_without_warehouse()
    with _warehouse() as con:
        season = con.execute(
            "SELECT _season FROM silver_leaders_ast"
            " ORDER BY _season DESC LIMIT 1"
        ).fetchone()[0]
    out = league_mod.get_leaders.invoke(
        {"stat_category": "APG", "season": season})
    lead = out["rows"][0]
    assert f"{lead['APG']:.2f} assists per game" in (
        out["meta"]["deterministic_answer"])