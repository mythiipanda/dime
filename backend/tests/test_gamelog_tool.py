

def test_missing_player_playoff_rows_name_player_gap_and_team_slice(monkeypatch):
    from app.tools import gamelog

    class Result:
        def __init__(self, rows):
            self.rows = rows
        def fetchall(self):
            return self.rows
        def fetchone(self):
            return self.rows[0]

    class Connection:
        def execute(self, query, params=None):
            if query == "SHOW TABLES":
                return Result([
                    ("silver_playoff_gamelogs",), ("silver_hist_gamelogs",),
                ])
            if "DISTINCT _season FROM silver_playoff_gamelogs" in query:
                return Result([("2025-26",)])
            if "PRAGMA table_info" in query:
                return Result([(0, "season_type")])
            if "count(*) FROM silver_hist_gamelogs" in query:
                assert params == ["2023-24"]
                return Result([(164,)])
            raise AssertionError(query)
        def close(self):
            pass

    monkeypatch.setattr(gamelog.store, "connect", lambda **_: Connection())
    monkeypatch.setattr(gamelog, "_load_games", lambda *args: [])
    monkeypatch.setattr(gamelog, "coerce_player_id", lambda player: 1629029)
    monkeypatch.setattr(gamelog, "playoff_inactive_note", lambda *args: None)

    out = gamelog.search_game_logs.invoke({
        "player": "Luka Doncic", "playoffs": True, "season": "2023-24",
    })
    assert out["ok"] is False
    assert "no playoff gamelog data for Luka Doncic" in out["error"]
    assert "player gamelog coverage: 2025-26" in out["error"]
    assert "team playoff game slice exists for 2023-24 (164 team-game rows)" in out["error"]
