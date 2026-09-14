"""Batch equivalence for _trade_sides team lookups.

_trade_sides used to open one warehouse connection per named player
(SELECT MATCHUP ... WHERE _entity = ? LIMIT 40 via _player_team_abbr).
It now resolves all pids through the cached coerce path and fetches
every MATCHUP in one SELECT with IN plus a per-entity 40-row cap.

These tests run against the real warehouse read-only and assert the
batched path returns byte-identical output to the old per-player loop
on representative trade questions, using exactly one connection.
Timings print via time.perf_counter for the before/after record.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import _player_team_abbr, _trade_sides
from app.tools._core import coerce_player_id

CASES = [
    ("Who wins this trade: Anthony Edwards (MIN) for Luka Doncic (LAL)?",
     ["Anthony Edwards", "Luka Doncic"],
     ["Minnesota Timberwolves", "Los Angeles Lakers"]),
    ("Who wins this three-team trade: Edwards (MIN) vs Doncic (LAL) "
     "vs Jokic (DEN)?",
     ["Anthony Edwards", "Luka Doncic", "Nikola Jokic"],
     ["Minnesota Timberwolves", "Los Angeles Lakers", "Denver Nuggets"]),
    ("Grade the swap: Tatum for Gilgeous-Alexander?",
     ["Jayson Tatum", "Shai Gilgeous-Alexander"],
     ["Boston Celtics", "Oklahoma City Thunder"]),
    ("Who wins the deal: Stephen Curry for Anthony Edwards?",
     ["Stephen Curry", "Anthony Edwards"],
     ["Golden State Warriors", "Minnesota Timberwolves"]),
]


def _needs_gamelogs():
    from app import store

    try:
        con = store.connect()
    except Exception:
        pytest.skip("warehouse unavailable")
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    if "silver_player_gamelogs" not in tables:
        pytest.skip("silver_player_gamelogs absent")


def _reference_trade_sides(question, found_p, found_t, season):
    """The pre-batch algorithm: one _player_team_abbr call per player."""
    import re
    import unicodedata

    from nba_api.stats.static import teams as _static

    def _fold(s):
        return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                       if not unicodedata.combining(c)).lower()

    raw_q = _fold(question)
    named = []
    for p in found_p:
        low = _fold(p)
        last = low.split()[-1]
        if low in raw_q or re.search(r"\b" + re.escape(last) + r"\b", raw_q):
            named.append(p)
    found_p = named
    abbr_of = {t["full_name"]: t["abbreviation"] for t in _static.get_teams()}
    nick_of = {t["full_name"].split()[-1].lower(): t["abbreviation"]
               for t in _static.get_teams()}
    order = []

    def _abbr(full):
        if full in abbr_of:
            return abbr_of[full]
        return nick_of.get(full.split()[-1].lower(), "")

    mentioned = [a for a in (_abbr(f) for f in found_t) if a]
    by_team = {}
    for p in found_p:
        try:
            pid = coerce_player_id(p)
        except Exception:
            continue
        ab = _player_team_abbr(pid, season) if pid else ""
        if not ab:
            continue
        by_team.setdefault(ab, []).append(p)
    for a in mentioned:
        by_team.setdefault(a, [])
        if a not in order:
            order.append(a)
    for a in by_team:
        if a not in order:
            order.append(a)
    if len(order) < 2:
        return None
    side_a, side_b = order[0], order[1]
    players_a = by_team.get(side_a, [])
    players_b = by_team.get(side_b, [])
    if not players_a or not players_b:
        rest = [p for p in found_p
                if p not in players_a and p not in players_b]
        for i, p in enumerate(rest):
            (players_a if i % 2 == 0 else players_b).append(p)
    if not players_a or not players_b:
        return None
    return {"team_a": side_a, "players_a": ", ".join(players_a),
            "team_b": side_b, "players_b": ", ".join(players_b)}


def test_batch_matches_per_player_output():
    _needs_gamelogs()
    for question, found_p, found_t in CASES:
        t0 = time.perf_counter()
        expected = _reference_trade_sides(question, list(found_p),
                                          list(found_t), "2025-26")
        ref_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        actual = _trade_sides(question, list(found_p), list(found_t),
                              "2025-26")
        new_ms = (time.perf_counter() - t0) * 1000
        print(f"\n{question[:60]!r} ref={ref_ms:.1f}ms new={new_ms:.1f}ms")
        assert actual == expected


def test_batch_uses_single_connection():
    _needs_gamelogs()
    from app import store

    real_connect = store.connect
    calls = []

    def counting(*a, **k):
        calls.append(1)
        return real_connect(*a, **k)

    store.connect = counting
    try:
        question, found_p, found_t = CASES[1]
        res = _trade_sides(question, list(found_p), list(found_t), "2025-26")
    finally:
        store.connect = real_connect
    assert res is not None
    assert len(calls) == 1


def test_batch_unknown_player_fallback():
    _needs_gamelogs()
    question = "Who wins this trade: Edwards (MIN) for Unknown (LAL)?"
    found_p = ["Anthony Edwards", "Zzz Unknown"]
    found_t = ["Minnesota Timberwolves", "Los Angeles Lakers"]
    actual = _trade_sides(question, list(found_p), list(found_t), "2025-26")
    # QA #70 contract change: an EMPTY side no longer bails to the
    # planner - the sides are returned and get_trade_value emits the
    # fast informative refusal (unknown/empty side). The pre-QA70
    # reference returned None here, pushing the question down a slow
    # multi-tool planner route for the same refusal.
    assert actual is not None
    assert actual["team_a"] == "MIN"
    assert "Anthony Edwards" in actual["players_a"]
    assert actual["team_b"] == "LAL"
    assert actual["players_b"] == ""
