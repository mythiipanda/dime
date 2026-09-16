from app.tools.league import get_team_trajectory


class FakeResult:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows


class FakeConnection:
    def execute(self, sql, params=None):
        if sql == "SHOW TABLES":
            return FakeResult([("silver_hist_standings",)])
        if sql.startswith("PRAGMA"):
            return FakeResult([(0, "team_id"), (1, "season_type")])
        assert "season_type = 'regular-season'" in sql
        assert params == ["1610612738", "2025-26", 3]
        return FakeResult([
            ("2025-26", 56, 26, .683),
            ("2024-25", 61, 21, .744),
            ("2023-24", 64, 18, .780),
        ])
    def close(self): pass


def test_team_trajectory_returns_bounded_regular_season_records(monkeypatch):
    monkeypatch.setattr("app.tools._core.coerce_team_id", lambda team: 1610612738)
    monkeypatch.setattr("app.store.connect", lambda read_only=True: FakeConnection())
    result = get_team_trajectory.invoke({"team": "Boston Celtics"})
    assert result["ok"] is True
    assert [row["record"] for row in result["rows"]] == [
        "56-26", "61-21", "64-18"
    ]
    assert all(row["team"] == "Boston Celtics" for row in result["rows"])
    assert all(row["team_id"] == "1610612738" for row in result["rows"])
    assert result["meta"]["coverage"].startswith("regular-season")
