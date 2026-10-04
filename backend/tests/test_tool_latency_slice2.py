import json
import time
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"

EXACT_NAMES = json.loads((FIX / "slice3_scorer_pre.json").read_text())

SLICE2_CASES = {
    "player_points": {"stat": "points", "threshold": 30, "scope": "player",
                      "season": "2025-26", "mode": "longest", "top": 10},
    "player_assists": {"stat": "assists", "threshold": 10, "scope": "player",
                       "season": "2025-26", "mode": "longest", "top": 10},
    "team_wins": {"stat": "wins", "scope": "team", "season": "2025-26",
                  "mode": "longest", "top": 10},
}


def _linear_name(pid, fallback):
    from nba_api.stats.static import players
    for p in players.get_players():
        if p.get("id") == pid:
            return p.get("full_name") or fallback
    return fallback


def test_resolve_name_matches_linear_scan_on_50_ids():
    from shared.tools.splits import _resolve_name
    from nba_api.stats.static import players
    sample = [p["id"] for p in players.get_players()[:48]] + [9999999, -5]
    assert len(sample) == 50
    for pid in sample:
        assert _resolve_name(pid, f"Player {pid}") == _linear_name(pid, f"Player {pid}")


def test_get_streaks_points30_completes_under_15s_nonempty():
    from shared.tools.streaks import get_streaks
    t0 = time.time()
    res = get_streaks.invoke(SLICE2_CASES["player_points"])
    dt = time.time() - t0
    assert dt < 15, f"get_streaks took {dt:.1f}s"
    assert res["ok"] is True
    assert len(res["rows"]["streaks"]) > 0


def test_get_streaks_matches_prechange_output_3_cases():
    from shared.tools.streaks import get_streaks
    for key, kw in SLICE2_CASES.items():
        expected = json.loads((FIX / f"slice2_streaks_{key}_pre.json").read_text())
        res = get_streaks.invoke(dict(kw))
        assert json.loads(json.dumps(res, default=str)) == expected, key


def test_exact_names_agree_with_prechange_scorer():
    from shared.tools._core import score_player_candidates
    names = [q for q in EXACT_NAMES if q not in
             ("james", "curry", "giannis", "luka", "tatum", "embiid", "booker",
              "wemby", "dbook", "ant", "bron", "dame", "joker", "kyrie", "morant")]
    assert len(names) == 30
    for q in names:
        ranked = score_player_candidates(q)
        got = [[s, r.get("id"), r.get("full_name")] for s, r in ranked]
        assert got[0] == EXACT_NAMES[q]["ranked"][0], q


def test_fuzzy_queries_identical_to_prechange_scorer():
    from shared.tools._core import score_player_candidates
    fuzzy = ("james", "curry", "giannis", "luka", "tatum", "embiid", "booker",
             "wemby", "dbook", "ant", "bron", "dame", "joker", "kyrie", "morant")
    for q in fuzzy:
        ranked = score_player_candidates(q)
        got = [[s, r.get("id"), r.get("full_name")] for s, r in ranked]
        assert got == EXACT_NAMES[q]["ranked"], q


def test_resolve_entity_exact_under_40ms_fuzzy_intact():
    from shared.tools import _core as _core
    from shared.tools.shared import resolve_entity
    resolve_entity.invoke({"query": "LeBron James"})
    lat = []
    for _ in range(5):
        _core.score_player_candidates.cache_clear()
        t0 = time.time()
        res = resolve_entity.invoke({"query": "LeBron James"})
        lat.append(time.time() - t0)
        assert res["ok"] is True
        assert res["rows"]["players"][0]["full_name"] == "LeBron James"
    assert max(lat) < 0.040, f"max latency {max(lat)*1000:.0f}ms"
    res = resolve_entity.invoke({"query": "james"})
    assert res["ok"] is True
    assert len(res["rows"]["players"]) > 1
