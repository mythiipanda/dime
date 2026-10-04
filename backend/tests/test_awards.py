
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools import _core

AWARD_TABLES = {"silver_leaders_pts", "silver_advanced", "silver_standings"}


def _warehouse_has_awards() -> bool:
    try:
        from shared import store

        con = store.connect()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
        if not AWARD_TABLES <= tables:
            return False
        n = store._read_df(
            "SELECT COUNT(*) AS n FROM silver_leaders_pts WHERE _season = ?",
            ["2025-26"])[0]["n"]
        return int(n) > 100
    except Exception:
        return False


KNOWN_STARS = {
    "Nikola Joki", "Luka Don", "Shai Gilgeous", "Victor Wembanyama",
    "Giannis Antetokounmpo", "Joel Embiid", "Jayson Tatum", "Kevin Durant",
    "Stephen Curry", "LeBron James", "Anthony Edwards", "Jalen Brunson",
    "Donovan Mitchell", "Devin Booker", "Anthony Davis", "Cade Cunningham",
}


def test_award_race_mvp_shape_and_formula():
    if not _warehouse_has_awards():
        return
    from shared.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "MVP", "season": "2025-26"})
    assert res["ok"] is True
    cands = res["rows"]["candidates"]
    assert len(cands) == 5
    assert [c["rank"] for c in cands] == [1, 2, 3, 4, 5]
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)
    for c in cands:
        assert c["player"] and c["team"]
        assert len(c["drivers"]) == 3
        assert c["case_for"] and c["case_against"]
    formula = res["meta"]["formula"]
    assert formula == ("0.35*z(PPG) + 0.2*z(team win%) + 0.15*z(net rating)"
                       " + 0.15*z(APG) + 0.15*z(RPG)")
    blob = formula + " ".join(c["player"] for c in cands)
    for bad in ("EPM", "LEBRON", "DARKO", "RAPTOR"):
        assert bad not in blob
    assert "not fabricated" in res["meta"]["advanced_metrics"]
    names = " ".join(c["player"] for c in cands)
    assert sum(1 for s in KNOWN_STARS if s in names) >= 3


def test_award_race_alias_normalization():
    if not _warehouse_has_awards():
        return
    from shared.tools.awards import get_award_race

    assert get_award_race.invoke({"award": "mvp"})["meta"]["award"] == "MVP"
    assert get_award_race.invoke(
        {"award": "best defender"})["meta"]["award"] == "DPOY"
    assert get_award_race.invoke(
        {"award": "rookie of the year"})["meta"]["award"] == "ROY"
    assert get_award_race.invoke(
        {"award": "sixth man"})["meta"]["award"] == "6MOY"


def test_award_race_unknown_award():
    from shared.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "coach of the year"})
    assert res["ok"] is False
    assert "MVP" in res["error"] and "DPOY" in res["error"]


def test_award_race_mip_degrades_honestly():
    if not _warehouse_has_awards():
        return
    from shared.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "MIP", "season": "2025-26"})
    assert res["ok"] is False
    assert "prior-season" in res["error"]


def test_award_race_registered_and_labeled():
    from shared import tools
    from app.graph import tool_label
    from app.subagents import _desk_tool_label

    assert "get_award_race" in tools.TOOL_NAMES
    assert tool_label("get_award_race") == "Ranking award races"
    assert _desk_tool_label("get_award_race") == "Ranking award races"


SCRATCH_SEASONS = ("2018-19", "2019-20", "2023-24", "2024-25")

SCRATCH_POOL = (
    (1, "Alpha Guard", "AAA", 11, 27.4, 6.1, 5.0, 7.8, 1.3, 0.4, 26.2),
    (2, "Beta Forward", "BBB", 12, 24.9, 10.2, 8.1, 4.2, 1.6, 1.2, 24.1),
    (3, "Gamma Wing", "CCC", 13, 22.6, 8.4, 6.9, 5.1, 1.1, 0.7, 22.0),
    (4, "Delta Center", "DDD", 14, 20.3, 12.7, 9.8, 2.8, 0.9, 2.1, 21.5),
    (5, "Epsilon Bench", "EEE", 15, 18.4, 7.2, 5.8, 3.6, 1.0, 0.6, 19.8),
    (6, "Zeta Rookie", "FFF", 16, 16.1, 6.4, 5.1, 3.1, 0.8, 0.5, 18.2),
)

SCRATCH_ADVANCED = (
    (1, 24.0, .585, 5.8, 101.2),
    (2, 25.0, .551, 3.1, 111.9),
    (3, 26.0, .549, 4.4, 115.2),
    (4, 27.0, .541, 2.2, 108.6),
    (5, 28.0, .533, 3.9, 117.4),
    (6, 29.0, .521, 4.7, 114.8),
)

HIST_RECORDS = (
    (11, 15, 67, 120.4),
    (12, 52, 30, 112.1),
    (13, 20, 62, 118.9),
    (14, 47, 35, 114.6),
    (15, 24, 58, 119.7),
    (16, 60, 22, 110.3),
)

CURRENT_RECORDS = (
    (11, 62, 20, 110.8),
    (12, 21, 61, 119.3),
    (13, 45, 37, 114.0),
    (14, 8, 74, 121.9),
    (15, 33, 49, 117.1),
    (16, 50, 32, 112.6),
)


def _write_scratch(path, hist_opp_pg: bool = True, qualifying: int = 6) -> None:
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE silver_boxscores "
                    "(GAME_ID VARCHAR, _season VARCHAR)")
        for season in SCRATCH_SEASONS:
            con.executemany("INSERT INTO silver_boxscores VALUES (?, ?)",
                            [(f"002{season[:4]}{i:04d}", season) for i in range(4)])
        con.execute("CREATE TABLE silver_leaders_pts (PLAYER_ID INTEGER, "
                    "PLAYER VARCHAR, TEAM VARCHAR, TEAM_ID INTEGER, GP INTEGER, "
                    "MIN DOUBLE, PTS DOUBLE, REB DOUBLE, DREB DOUBLE, AST DOUBLE, "
                    "STL DOUBLE, BLK DOUBLE, EFF DOUBLE, _season VARCHAR)")
        con.execute("CREATE TABLE silver_advanced (PLAYER_ID INTEGER, AGE DOUBLE, "
                    "TS_PCT DOUBLE, NET_RATING DOUBLE, DEF_RATING DOUBLE, "
                    "_season VARCHAR)")
        for season in ("2018-19", "2019-20", "2023-24", "2024-25"):
            for index, (pid, name, team, tid, pts, reb, dreb, ast, stl, blk,
                        eff) in enumerate(SCRATCH_POOL):
                starter = season != "2023-24" or index < qualifying
                gp = 70 - index if starter else 9
                mins = 2600 - index * 40 if starter else 150
                con.execute(
                    "INSERT INTO silver_leaders_pts VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [pid, name, team, tid, gp, mins, pts * gp, reb * gp,
                     dreb * gp, ast * gp, stl * gp, blk * gp, eff * gp,
                     season])
                age, ts, net, dft = SCRATCH_ADVANCED[index][1:]
                con.execute("INSERT INTO silver_advanced VALUES (?,?,?,?,?,?)",
                            [pid, age, ts, net, dft, season])
        opp = "DOUBLE"
        con.execute("CREATE TABLE silver_standings (TeamID INTEGER, WINS INTEGER, "
                    f"LOSSES INTEGER, OppPointsPG {opp}, _season VARCHAR)")
        hist = ["team_id", "wins", "losses"]
        if hist_opp_pg:
            hist.append("opp_points_pg")
        con.execute("CREATE TABLE silver_hist_standings ("
                    + ", ".join(
                        f"{c} {opp if c.startswith('opp') else 'INTEGER'}"
                        for c in hist)
                    + ", _season VARCHAR)")
        for tid, wins, losses, opp_pg in CURRENT_RECORDS:
            con.execute("INSERT INTO silver_standings VALUES (?,?,?,?,?)",
                        [tid, wins, losses, opp_pg, "2024-25"])
            con.execute("INSERT INTO silver_standings VALUES (?,?,?,?,?)",
                        [tid, wins, losses, opp_pg, "2023-24"])
        for tid, wins, losses, opp_pg in HIST_RECORDS:
            values = dict(zip(("team_id", "wins", "losses", "opp_points_pg"),
                              (tid, wins, losses, opp_pg)))
            con.execute("INSERT INTO silver_hist_standings ("
                        + ", ".join([*hist, "_season"])
                        + ") VALUES (" + ", ".join(["?"] * (len(hist) + 1)) + ")",
                        [values[column] for column in hist] + ["2019-20"])
    finally:
        con.close()


@pytest.fixture()
def scratch(monkeypatch, tmp_path):
    def _build(**kwargs):
        path = tmp_path / "awards.duckdb"
        _write_scratch(path, **kwargs)
        monkeypatch.setattr(store, "DB_PATH", path)
        monkeypatch.setattr(
            store, "connect",
            lambda **_kw: duckdb.connect(str(path), read_only=True))
        _core.last_completed_season_cache_clear()
        store.warehouse_tables_cache_clear()
        return path

    yield _build
    _core.last_completed_season_cache_clear()
    store.warehouse_tables_cache_clear()


def _table_seasons(table: str) -> set[str]:
    con = store.connect(read_only=True)
    try:
        return {r[0] for r in con.execute(
            f"SELECT DISTINCT _season FROM {table}").fetchall() if r[0]}
    finally:
        con.close()


def _rows(sql: str, params: list) -> list[tuple]:
    con = store.connect(read_only=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _win_pct(wins: int, losses: int) -> float:
    return wins / (wins + losses)


def _player_by_team_id() -> dict[int, str]:
    return {tid: name for _, name, _, tid, *_ in SCRATCH_POOL}


def _team_context(season: str) -> dict[str, tuple[float, float]]:
    from shared.tools.awards import _pool

    return {row["player"]: (row["team_win_pct"], row["team_opp_ppg"])
            for row in _pool(season)}


def test_historical_only_season_resolves_team_context(scratch):
    from shared.tools.awards import get_award_race

    scratch()
    res = get_award_race.invoke({"award": "MVP", "season": "2019-20"})
    assert res["ok"] is True, res
    assert len(res["rows"]["candidates"]) == 5
    assert res["meta"]["standings_coverage"] == "historical"
    context = _team_context("2019-20")
    players = _player_by_team_id()
    for tid, wins, losses, opp_pg in HIST_RECORDS:
        win_pct, opp_ppg = context[players[tid]]
        assert win_pct == pytest.approx(_win_pct(wins, losses))
        assert opp_ppg == pytest.approx(opp_pg)


def test_season_neither_standings_table_covers_fails_naming_both(scratch):
    from shared.tools.awards import get_award_race

    scratch()
    res = get_award_race.invoke({"award": "MVP", "season": "2018-19"})
    assert res["ok"] is False
    assert "2018-19" in res["error"]
    assert "silver_standings" in res["error"]
    assert "silver_hist_standings" in res["error"]
    assert res["rows"] == {}


def test_historical_standings_missing_a_needed_column_fails_naming_season_and_column(
        scratch):
    from shared.tools.awards import get_award_race

    scratch(hist_opp_pg=False)
    res = get_award_race.invoke({"award": "DPOY", "season": "2019-20"})
    assert res["ok"] is False
    assert "2019-20" in res["error"]
    assert "silver_hist_standings" in res["error"]
    assert "opp_points_pg" in res["error"]


def test_current_season_still_reads_the_current_standings_table(scratch):
    from shared.tools.awards import get_award_race

    scratch()
    res = get_award_race.invoke({"award": "MVP", "season": "2024-25"})
    assert res["ok"] is True, res
    assert res["meta"]["standings_coverage"] == "current"
    context = _team_context("2024-25")
    players = _player_by_team_id()
    for tid, wins, losses, opp_pg in CURRENT_RECORDS:
        win_pct, opp_ppg = context[players[tid]]
        assert win_pct == pytest.approx(_win_pct(wins, losses))
        assert opp_ppg == pytest.approx(opp_pg)


def test_one_qualifier_yields_a_defined_score_not_a_crash(scratch):
    from shared.tools.awards import get_award_race

    scratch(qualifying=1)
    res = get_award_race.invoke({"award": "MVP", "season": "2023-24"})
    assert res["ok"] is True, res
    candidates = res["rows"]["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["player"] == SCRATCH_POOL[0][1]
    assert candidates[0]["score"] == 0.0
    assert all(d["z"] == 0.0 for d in candidates[0]["drivers"])
    assert res["meta"]["qualified_pool"] == 1
    assert "no comparison pool" in res["meta"]["note"]


def test_zero_qualifiers_fails_loudly(scratch):
    from shared.tools.awards import get_award_race

    scratch()
    res = get_award_race.invoke({"award": "ROY", "season": "2024-25"})
    assert res["ok"] is False
    assert "ROY" in res["error"]
    assert "2024-25" in res["error"]
    assert res["rows"] == {}


def test_a_full_pool_is_unchanged(scratch):
    from shared.tools.awards import get_award_race

    scratch()
    res = get_award_race.invoke({"award": "MVP", "season": "2024-25"})
    scores = [c["score"] for c in res["rows"]["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > 0.0
    assert res["meta"]["qualified_pool"] == 6
    assert "single_candidate_pool" not in res["meta"]


def test_missing_advanced_component_is_reported_not_silently_dropped(
        monkeypatch, scratch):
    from shared.tools import awards

    scratch()
    real_pool = awards._pool

    def _hole_for(names):
        def _pool_with_a_hole(season):
            rows = real_pool(season)
            for row in rows:
                if row["player"] in names:
                    row["net_rating"] = float("nan")
            return rows
        return _pool_with_a_hole

    monkeypatch.setattr(awards, "_pool", _hole_for(
        {name for _, name, *_ in SCRATCH_POOL}))
    res = awards.get_award_race.invoke({"award": "MVP", "season": "2024-25"})
    assert res["ok"] is False
    assert "net rating" in res["error"]
    assert "2024-25" in res["error"]
    assert res["rows"] == {}

    monkeypatch.setattr(awards, "_pool", _hole_for({SCRATCH_POOL[0][1]}))
    res = awards.get_award_race.invoke({"award": "MVP", "season": "2024-25"})
    assert res["ok"] is True, res
    assert res["meta"]["qualified_pool"] == 5
    assert SCRATCH_POOL[0][1] not in {
        c["player"] for c in res["rows"]["candidates"]}


def test_warehouse_team_context_matches_the_standings_rows_behind_it():
    from shared.tools.awards import get_award_race

    if not _warehouse_has_awards():
        return
    seasons = sorted(_table_seasons("silver_standings"))
    checked: list[tuple[str, str]] = []
    for award in ("MVP", "DPOY"):
        for season in seasons:
            res = get_award_race.invoke({"award": award, "season": season})
            if not res["ok"]:
                continue
            assert res["meta"]["standings_coverage"] == "current"
            expected = {
                row[0]: (_win_pct(row[1], row[2]), float(row[3]))
                for row in _rows(
                    "SELECT l.PLAYER, s.WINS, s.LOSSES, s.OppPointsPG "
                    "FROM silver_leaders_pts l "
                    "JOIN silver_standings s ON s.TeamID = l.TEAM_ID "
                    "AND s._season = l._season WHERE l._season = ?", [season])}
            assert len(expected) > 100
            for player, (win_pct, opp_ppg) in _team_context(season).items():
                assert win_pct == pytest.approx(
                    expected[player][0], abs=1e-9), (season, player)
                assert opp_ppg == pytest.approx(
                    expected[player][1], abs=1e-9), (season, player)
                checked.append((award, season))
    assert checked, "no season of this warehouse answers an award race"


def test_warehouse_historical_season_reads_historical_standings():
    from shared.tools.awards import get_award_race

    if not _warehouse_has_awards():
        return
    scorable = _table_seasons("silver_leaders_pts") & _table_seasons("silver_advanced")
    historical = sorted(scorable - _table_seasons("silver_standings"))
    if not historical:
        pytest.skip("silver_advanced covers no season outside silver_standings, "
                    "so the standings fallback is not observable here")
    for season in historical:
        res = get_award_race.invoke({"award": "MVP", "season": season})
        assert res["ok"] is True, res
        assert res["meta"]["standings_coverage"] == "historical"
        expected = {
            row[0]: (_win_pct(row[1], row[2]), float(row[3]))
            for row in _rows(
                "SELECT l.PLAYER, h.wins, h.losses, h.opp_points_pg "
                "FROM silver_leaders_pts l "
                "JOIN silver_hist_standings h ON h.team_id = l.TEAM_ID "
                "AND h._season = l._season WHERE l._season = ?", [season])}
        assert len(expected) > 100
        for player, (win_pct, opp_ppg) in _team_context(season).items():
            assert win_pct == pytest.approx(
                expected[player][0], abs=1e-9), (season, player)
            assert opp_ppg == pytest.approx(
                expected[player][1], abs=1e-9), (season, player)


def test_warehouse_answers_award_history_for_at_least_two_seasons():
    from shared.tools.awards import get_award_race

    if not _warehouse_has_awards():
        return
    answerable = sorted(_table_seasons("silver_leaders_pts")
                        & _table_seasons("silver_advanced")
                        & (_table_seasons("silver_standings")
                           | _table_seasons("silver_hist_standings")))
    if len(answerable) < 2:
        pytest.skip(f"silver_advanced covers {answerable} only, so this "
                    "warehouse cannot answer two seasons of award history")
    for season in answerable[:2]:
        for award in ("MVP", "DPOY"):
            res = get_award_race.invoke({"award": award, "season": season})
            assert res["ok"] is True, res
            assert len(res["rows"]["candidates"]) == 5
            assert res["meta"]["qualified_pool"] > 1
