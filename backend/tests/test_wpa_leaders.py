"""get_wpa_leaders tests. Warehouse reads only; WPA leaderboard shape,
clamps, honest empty states, book conservation, and the 5s season gate."""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.wpa import (  # noqa: E402
    clamp_limit,
    clamp_min_events,
    clamp_season_year,
    get_wpa_leaders,
    score_events,
    season_label,
)
from app.tools.wpamodel import (  # noqa: E402
    TIPOFF_SEC,
    seconds_remaining,
    win_probability,
)

GAME = "0022500001"


def _game_rows(game_id: str = GAME) -> list:
    from app import store

    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_pbp" not in tables:
            pytest.skip("silver_hist_pbp not seeded")
        return con.execute(
            "SELECT game_id, action_number, clock, period, team_tricode,"
            " person_id, player_name, location, score_home, score_away,"
            " action_type FROM silver_hist_pbp WHERE game_id = ?"
            " ORDER BY action_number",
            [game_id],
        ).fetchall()
    finally:
        con.close()


def test_book_balances_per_game():
    rows = _game_rows()
    seen: dict = {}
    for row in rows:
        an = row[1]
        if an not in seen:
            seen[an] = row
        elif not seen[an][10] and row[10]:
            seen[an] = row
    home, away, total = 0, 0, 0.0
    before = win_probability(0, TIPOFF_SEC)
    for an in sorted(seen):
        evt = seen[an]
        try:
            home = int(str(evt[8]))
        except (TypeError, ValueError):
            pass
        try:
            away = int(str(evt[9]))
        except (TypeError, ValueError):
            pass
        sec = seconds_remaining(evt[2], evt[3])
        if sec is None:
            continue
        after = win_probability(home - away, sec)
        total += after - before
        before = after
    assert total == pytest.approx(before - win_probability(0, TIPOFF_SEC), abs=1e-9)
    assert abs(total) < 1.0


def test_makers_credit_positive_bushel():
    players = score_events(_game_rows())
    assert sum(p["wpa"] for p in players.values()) > 0


def test_happy_path_shape():
    out = get_wpa_leaders.invoke({"season": 2025, "limit": 10})
    assert out["ok"] is True
    leaders = out["rows"]["leaders"]
    assert len(leaders) == 10
    for row in leaders:
        assert set(row) >= {"rank", "player", "player_id", "team", "wpa",
                            "events", "plus_events", "minus_events", "games"}
        assert row["events"] >= 100
        assert row["plus_events"] + row["minus_events"] <= row["events"]
        assert row["games"] >= 1
    wpas = [r["wpa"] for r in leaders]
    assert wpas == sorted(wpas, reverse=True)
    assert out["meta"]["season_label"] == "2024-25"
    assert out["meta"]["source"] == "warehouse silver_hist_pbp (documented estimates)"


def test_star_sanity():
    out = get_wpa_leaders.invoke({"season": 2025, "limit": 10})
    assert out["ok"] is True
    names = [r["player"] for r in out["rows"]["leaders"]]
    assert "Gilgeous-Alexander" in names[:5]
    assert "Jokić" in names
    assert out["rows"]["leaders"][0]["wpa"] > 0


def test_limit_clamp():
    assert clamp_limit(100) == 25
    assert clamp_limit(0) == 1
    assert clamp_limit("garbage") == 10
    wide = get_wpa_leaders.invoke({"season": 2025, "limit": 100})
    assert wide["ok"] is True
    assert len(wide["rows"]["leaders"]) == 25
    assert wide["meta"]["limit"] == 25
    narrow = get_wpa_leaders.invoke({"season": 2025, "limit": 0})
    assert len(narrow["rows"]["leaders"]) == 1


def test_season_clamp_and_reject():
    assert season_label(2025) == "2024-25"
    assert clamp_season_year(2020) == (2021, "season 2020 clamped to 2021")
    assert clamp_season_year(2026)[0] is None
    low = get_wpa_leaders.invoke({"season": 2020, "limit": 3})
    assert low["ok"] is True
    assert low["meta"]["season"] == 2021
    assert "clamped" in low["meta"]["warning"]
    high = get_wpa_leaders.invoke({"season": 2026, "limit": 3})
    assert high["ok"] is False
    assert "no WPA coverage" in high["error"]
    fallback = get_wpa_leaders.invoke({"season": "garbage", "limit": 3})
    assert fallback["ok"] is True
    assert fallback["meta"]["season"] == 2025


def test_empty_honesty():
    out = get_wpa_leaders.invoke({"season": 2025, "limit": 10, "min_events": 999999})
    assert out["ok"] is False
    assert "no players" in out["error"]
    assert clamp_min_events("garbage") == 100
    assert clamp_min_events(0) == 1


def test_season_timing_gate():
    start = time.time()
    out = get_wpa_leaders.invoke({"season": 2025, "limit": 10})
    assert out["ok"] is True
    assert time.time() - start < 5


def test_tool_registered():
    from app import tools

    assert "get_wpa_leaders" in tools.TOOL_NAMES
