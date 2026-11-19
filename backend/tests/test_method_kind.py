import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import league as league_mod


def _rows_meta(rows):
    return rows, {"source": "fixture"}


def test_warehouse_ratings_emit_official_kind(monkeypatch):
    rows = [{"TEAM_ID": 1, "TEAM_NAME": "Boston Celtics", "GP": 82, "W": 60,
             "L": 22, "OFF_RATING": 118.1, "DEF_RATING": 106.9,
             "NET_RATING": 11.2, "PACE": 99.0, "TS_PCT": 0.6,
             "TM_TOV_PCT": 0.12}]
    monkeypatch.setattr(
        league_mod, "_warehouse_or_live",
        lambda *args, **kwargs: _rows_meta(rows))
    out = league_mod.get_ratings.invoke({"season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["method_kind"] == "official"


def test_playoff_estimated_possessions_emit_estimate_kind(monkeypatch):
    from shared.tools import _core as core_mod

    class _FakeCon:
        def execute(self, *args, **kwargs):
            class _Cur:
                def fetchall(self):
                    return [("Boston Celtics", 5, 118.1, 106.9, 11.2)]
                def fetchone(self):
                    return (None,)
            return _Cur()
        def close(self):
            pass

    monkeypatch.setattr(
        league_mod, "resolve_season", lambda season, *args, **kwargs: season)
    monkeypatch.setattr(core_mod, "clamp_season", lambda season: season)
    monkeypatch.setattr(league_mod.store, "connect",
                        lambda read_only=True: _FakeCon())
    out = league_mod.get_playoff_team_ratings.invoke({"season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["method"] == "NBA box-score estimated possessions"
    assert out["meta"]["method_kind"] == "estimate"
