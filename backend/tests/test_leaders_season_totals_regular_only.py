import duckdb

from backend.shared.tools.league import leaders


def test_completed_season_totals_excludes_playoff_games(monkeypatch, tmp_path):
    db = tmp_path / "w.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE silver_boxscores (PLAYER_ID INTEGER, firstName VARCHAR, "
        "familyName VARCHAR, GAME_ID VARCHAR, teamTricode VARCHAR, points INTEGER, "
        "comment VARCHAR, _season VARCHAR)"
    )
    rows = [
        (1, "Shai", "Gilgeous-Alexander", f"002240{i:04d}", "OKC", 30, None, "2024-25")
        for i in range(76)
    ]
    rows += [
        (1, "Shai", "Gilgeous-Alexander", f"004240{i:04d}", "OKC", 30, None, "2024-25")
        for i in range(23)
    ]
    con.executemany(
        "INSERT INTO silver_boxscores VALUES (?,?,?,?,?,?,?,?)", rows
    )
    con.close()

    import backend.shared.tools.league.leaders as mod
    pkg = mod._pkg()
    monkeypatch.setattr(pkg.store, "connect", lambda read_only=None: duckdb.connect(str(db), read_only=bool(read_only)))

    rows_out, _meta = mod._completed_season_totals("PTS", "2024-25")
    sga = [r for r in rows_out if r["PLAYER_ID"] == 1]
    assert sga and sga[0]["GP"] == 76, f"SGA GP should be 76 regular-season games, got {sga[0]['GP'] if sga else 'none'}"
    assert sga[0]["PTS"] == 76 * 30
