import shared.tools.today as today_mod
from shared.tools.today import (
    _scoreboards,
    _warehouse_games,
    _warehouse_has_games,
    get_morning_briefing,
    get_today,
)


class _Frame:
    def __init__(self, rows):
        self._rows = rows
        self.height = len(rows)

    def to_dicts(self):
        return [dict(r) for r in self._rows]


class _Invoke:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, _args):
        return self._payload


def _stub_deltas(monkeypatch, payload=None):
    import shared.tools.league as league

    payload = payload if payload is not None else {"ok": False, "error": "boom"}
    monkeypatch.setattr(league, "get_leaderboard_deltas", _Invoke(payload))


def _stub_watchlist(monkeypatch):
    import shared.tools.watchlist as watchlist

    monkeypatch.setattr(
        watchlist,
        "get_watchlist",
        _Invoke({"ok": True, "rows": [], "meta": {"count": 0}}),
    )


def test_warehouse_games_empty_is_read_ok(monkeypatch):
    import shared.store as store
    import shared.tools.team as team

    monkeypatch.setattr(store, "read_frame", lambda *a, **k: _Frame([]))
    monkeypatch.setattr(team, "game_links", lambda gid: {})
    rows, read_ok = _warehouse_games("09/28/2026", "2024-25")
    assert rows == []
    assert read_ok is True


def test_warehouse_games_rows_is_read_ok(monkeypatch):
    import shared.store as store
    import shared.tools.team as team

    monkeypatch.setattr(
        store, "read_frame", lambda *a, **k: _Frame([{"GAME_ID": "1"}])
    )
    monkeypatch.setattr(team, "game_links", lambda gid: {"nba": gid})
    rows, read_ok = _warehouse_games("09/28/2026", "2024-25")
    assert rows == [{"GAME_ID": "1", "LINKS": {"nba": "1"}}]
    assert read_ok is True


def test_warehouse_games_failure_is_not_empty(monkeypatch):
    import shared.store as store

    def _raise(*a, **k):
        raise RuntimeError("warehouse down")

    monkeypatch.setattr(store, "read_frame", _raise)
    rows, read_ok = _warehouse_games("09/28/2026", "2024-25")
    assert rows == []
    assert read_ok is False


def test_scoreboards_static_failure_flags_degraded(monkeypatch):
    monkeypatch.setattr(today_mod, "_live_scores_needed", lambda s, d: False)

    calls = []

    def _fake(date_str, season):
        assert season == "2024-25"
        calls.append(date_str)
        if len(calls) == 1:
            return ([{"GAME_ID": "1"}], True)
        return ([], False)

    monkeypatch.setattr(today_mod, "_warehouse_games", _fake)
    last, tonight, ok = _scoreboards("2024-25")
    assert last == [{"GAME_ID": "1"}]
    assert tonight == []
    assert ok is False


def test_scoreboards_static_empty_flags_ok(monkeypatch):
    monkeypatch.setattr(today_mod, "_live_scores_needed", lambda s, d: False)
    monkeypatch.setattr(today_mod, "_warehouse_games", lambda d, s: ([], True))
    last, tonight, ok = _scoreboards("2024-25")
    assert (last, tonight, ok) == ([], [], True)


def test_scoreboards_live_path_unchanged(monkeypatch):
    monkeypatch.setattr(today_mod, "_live_scores_needed", lambda s, d: True)
    monkeypatch.setattr(today_mod, "_games", lambda d, s: [{"GAME_ID": "9"}])
    last, tonight, ok = _scoreboards("2026-27")
    assert last == tonight == [{"GAME_ID": "9"}]
    assert ok is True


def test_get_today_marks_warehouse_failure(monkeypatch):
    _stub_deltas(monkeypatch)
    monkeypatch.setattr(today_mod, "_scoreboards", lambda s: ([], [], False))
    monkeypatch.setattr(today_mod, "_streaks", lambda s: [])
    out = get_today.invoke({"season": "2024-25"})
    assert out["ok"] is True
    assert out["rows"]["last_night"] == []
    assert out["rows"]["tonight"] == []
    assert out["meta"]["scoreboard_ok"] is False


def test_get_today_marks_warehouse_ok(monkeypatch):
    _stub_deltas(monkeypatch)
    monkeypatch.setattr(
        today_mod, "_scoreboards", lambda s: ([{"GAME_ID": "1"}], [], True)
    )
    monkeypatch.setattr(today_mod, "_streaks", lambda s: [])
    out = get_today.invoke({"season": "2024-25"})
    assert out["rows"]["last_night"] == [{"GAME_ID": "1"}]
    assert out["meta"]["scoreboard_ok"] is True


def test_briefing_marks_warehouse_failure(monkeypatch):
    _stub_deltas(monkeypatch)
    _stub_watchlist(monkeypatch)
    monkeypatch.setattr(today_mod, "_scoreboards", lambda s: ([], [], False))
    monkeypatch.setattr(today_mod, "_streaks", lambda s: [])
    out = get_morning_briefing.invoke({"season": "2024-25"})
    assert out["rows"]["today"]["last_night"] == []
    assert out["meta"]["scoreboard_ok"] is False


def test_briefing_marks_warehouse_ok(monkeypatch):
    _stub_deltas(monkeypatch)
    _stub_watchlist(monkeypatch)
    monkeypatch.setattr(
        today_mod, "_scoreboards", lambda s: ([{"GAME_ID": "1"}], [], True)
    )
    monkeypatch.setattr(today_mod, "_streaks", lambda s: [])
    out = get_morning_briefing.invoke({"season": "2024-25"})
    assert out["rows"]["today"]["last_night"] == [{"GAME_ID": "1"}]
    assert out["meta"]["scoreboard_ok"] is True


def test_warehouse_has_games_fails_open(monkeypatch):
    import shared.store as store

    def _raise(*a, **k):
        raise RuntimeError("warehouse down")

    monkeypatch.setattr(store, "read_frame", _raise)
    assert _warehouse_has_games("2026-27", ["09/28/2026"]) is True
    monkeypatch.setattr(store, "read_frame", lambda *a, **k: _Frame([]))
    assert _warehouse_has_games("2026-27", ["09/28/2026"]) is False
    monkeypatch.setattr(
        store, "read_frame", lambda *a, **k: _Frame([{"GAME_ID": "1"}])
    )
    assert _warehouse_has_games("2026-27", ["09/28/2026"]) is True
