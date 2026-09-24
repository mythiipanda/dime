"""F88 deterministic qualification and named-team ratings routes."""
import asyncio
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.graph import _triage_seed
from app.tools import get_leaders


def _drain(q):
    async def go():
        state = {"question": q, "history": [], "tool_results": [],
                 "calls_made": [], "round": 0}
        async for _ in _triage_seed(q, "p", "m", state):
            pass
        return state
    return asyncio.run(go())


def test_three_point_percentage_uses_official_makes_floor():
    out = get_leaders.invoke({"stat_category": "FG3_PCT"})
    assert out["ok"] and out["rows"][0]["PLAYER"] == "Luke Kennard"
    assert out["rows"][0]["FG3_PCT"] == 0.478
    assert out["meta"]["qualification"] == "82+ made threes"
    assert out["rows"][0]["FG3A"] == 245
    answer = out["meta"]["deterministic_answer"]
    assert all(name in answer for name in (
        "Luke Kennard", "Bobby Portis", "Cam Spencer",
        "Jaylon Tyson", "Rui Hachimura",
    ))
    assert "47.8%" in answer and "245 attempts" in answer


def test_three_point_prompt_forces_leader_tool():
    st = _drain("Who leads the league in 3P% this season?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_leaders"]
    assert st["tool_results"][0]["rows"][0]["PLAYER"] == "Luke Kennard"


def test_named_team_ratings_is_one_call():
    st = _drain("Warriors ratings?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_ratings"]
    out = st["tool_results"][0]
    assert len(out["rows"]) == 1
    assert out["rows"][0]["TEAM"] == "GSW"
    assert "113.8 offense" in out["meta"]["deterministic_answer"]
    assert "114.4 defense" in out["meta"]["deterministic_answer"]


def test_true_shooting_leader_is_qualified_and_one_call():
    st = _drain("Who leads the league in true shooting percentage this season?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_leaders"]
    out = st["tool_results"][0]
    assert out["meta"]["stat_category"] == "TS_PCT"
    assert out["meta"]["qualification"] == "1,000+ total minutes"
    assert out["rows"][0]["TS_PCT"] == 77.2
    assert "77.2% true shooting" in out["meta"]["deterministic_answer"]


def test_steals_per_game_leader_carries_sample_size():
    st = _drain("Who leads the league in steals per game this season?")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_leaders"]
    out = st["tool_results"][0]
    assert out["meta"]["stat_category"] == "SPG"
    assert out["meta"]["qualification"] == "games played shown; no implicit GP floor"
    assert out["rows"][0]["GP"] > 0
    answer = out["meta"]["deterministic_answer"]
    assert "steals per game" in answer and "games" in answer


def test_fg3_percentage_leaders_carry_direction_volume_and_shooting_counts(monkeypatch):
    class Result:
        @staticmethod
        def fetchall():
            return [
                ("A", "AAA", 70, 1800, 140, 300, 0.467),
                ("B", "BBB", 72, 1900, 150, 350, 0.429),
            ]

    class Connection:
        def execute(self, query, params):
            assert "FG3A >= ?" in query
            assert "FG3_PCT ASC" in query
            assert params == ["2025-26", 0, 300]
            return Result()
        def close(self):
            pass

    monkeypatch.setattr(
        "app.tools.league._warehouse_or_live",
        lambda *args, **kwargs: ([], {"source": "fixture", "rows": 0}),
    )
    monkeypatch.setattr("app.tools.league.store.connect", lambda **_: Connection())
    out = get_leaders.invoke({
        "stat_category": "FG3_PCT", "season": "2025-26",
        "ranking_direction": "asc", "min_attempts": 300,
    })
    assert out["meta"]["stat_category"] == "FG3_PCT"
    assert out["meta"]["ranking_direction"] == "asc"
    assert out["meta"]["min_attempts"] == 300
    assert out["meta"]["qualification"] == "300+ three-point attempts"
    assert out["rows"][0] == {
        "RANK": 1, "PLAYER": "A", "TEAM": "AAA", "FG3_PCT": 0.467,
        "FG3M": 140, "FG3A": 300, "GP": 70, "MIN": 1800,
        "PERCENTILE": 100.0,
    }


def test_leader_routing_rejects_invalid_direction_and_volume():
    with pytest.raises(ValueError, match="ranking_direction"):
        get_leaders.invoke({"ranking_direction": "sideways"})
    with pytest.raises(ValueError, match="min_attempts"):
        get_leaders.invoke({"min_attempts": -1})


@pytest.mark.parametrize(("question", "metric", "direction", "team", "value"), [
    ("Which team has the lowest defensive rating in 2025-26? Give the value.",
     "DEF_RATING", "asc", "Oklahoma City Thunder", "106.5"),
    ("Which team has the highest true shooting in 2025-26? Give the value.",
     "TS_PCT", "desc", "Denver Nuggets", "0.616"),
    ("Which team has the lowest turnover percentage in 2025-26? Give the value.",
     "TM_TOV_PCT", "asc", "Oklahoma City Thunder", "0.124"),
])
def test_team_metric_rank_binds_requested_field_and_direction(
        question, metric, direction, team, value):
    st = _drain(question)
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_ratings"]
    out = st["tool_results"][0]
    assert out["meta"]["requested_metric"] == metric
    assert out["meta"]["ranking_direction"] == direction
    assert out["meta"]["claim_value_field"] == metric
    assert out["rows"][0]["TEAM_NAME"] == team
    answer = out["meta"]["deterministic_answer"]
    assert team in answer and value in answer


def test_blocks_per_game_uses_full_blocks_totals_and_unrounded_sort():
    st = _drain("Who leads the NBA in blocks per game this season? Give the top five with games played.")
    assert [c.split(":")[0] for c in st["calls_made"]] == ["get_leaders"]
    out = st["tool_results"][0]
    assert out["meta"]["stat_category"] == "BPG"
    assert [r["PLAYER"] for r in out["rows"][:5]] == [
        "Victor Wembanyama", "Alex Sarr", "Zach Edey", "Chet Holmgren", "Jay Huff"]
    assert all(r["GP"] for r in out["rows"][:5])
    assert out["rows"][2]["BPG"] > out["rows"][3]["BPG"] > out["rows"][4]["BPG"]


def test_team_rating_tool_enum_and_planner_vocabulary_stay_aligned():
    from app.tools.rating_metrics import TEAM_RATING_METRICS
    assert TEAM_RATING_METRICS == {
        "OFF_RATING": "offensive rating",
        "DEF_RATING": "defensive rating",
        "NET_RATING": "net rating",
        "PACE": "pace",
        "TS_PCT": "true shooting percentage",
        "TM_TOV_PCT": "turnover percentage",
    }

def test_bound_warehouse_read_paths_and_lineage(monkeypatch,tmp_path):
    import hashlib
    from app import store
    from app.tools import _core
    from app.sources.base import FetchResult, FetchMeta
    import polars as pl
    db=tmp_path/'warehouse.duckdb';db.write_bytes(b'initial');monkeypatch.setattr(store,'DB_PATH',db)
    class F:
        height=1;columns=[]
        def head(self,n):return self
        def to_dicts(self):return [{'x':1}]
    monkeypatch.setattr(store,'read_frame',lambda *a,**k:F())
    rows,meta=_core._warehouse_or_live('t','x=?',[1],lambda:None,'2025-26')
    assert meta['warehouse_sha256']==hashlib.sha256(b'initial').hexdigest()
    # Intentional save completes before post-save read identity is captured.
    monkeypatch.setattr(store,'read_frame',lambda *a,**k:None if db.read_bytes()==b'initial' else F())
    live=FetchResult(frame=pl.DataFrame({'x':[1]}),meta=FetchMeta(source='live',season='2025-26',fetched_at='2026-09-19'),ok=True)
    monkeypatch.setattr(store,'save_frame',lambda *a,**k:db.write_bytes(b'post-save'))
    rows,meta=_core._warehouse_or_live('t','x=?',[1],lambda:live,'2026-27',live_first=True)
    assert meta['warehouse_sha256']==hashlib.sha256(b'post-save').hexdigest()
    # Mid-read external mutation fails.
    def mutate(*a,**k):db.write_bytes(b'external');return F()
    monkeypatch.setattr(store,'read_frame',mutate)
    with pytest.raises(RuntimeError,match='identity changed'):_core._bound_warehouse_read('t','x=?',[1])


def test_stale_fallback_binds_fallback_read_and_legitimate_writer_is_serialized(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from app import store
    from app.tools import _core
    from app.sources.base import empty
    db=tmp_path/'warehouse.duckdb';db.write_bytes(b'stable');monkeypatch.setattr(store,'DB_PATH',db)
    class F:
        height=1;columns=[]
        def head(self,n):return self
        def to_dicts(self):return [{'x':1}]
    calls=[]
    @contextmanager
    def guard():calls.append('lock');yield
    monkeypatch.setattr(store,'write_guard',guard)
    monkeypatch.setattr(store,'read_frame',lambda *a,**k:(calls.append('read') or F()))
    rows,meta=_core._warehouse_or_live('t','x=?',[1],lambda:empty('live','2026-27','down'),'2026-27',live_first=True)
    assert meta['stale'] is True and meta['warehouse_sha256']==store.warehouse_identity()['warehouse_sha256']
    assert calls[:2]==['lock','read']


def test_ranked_team_answer_uses_label_not_enum_or_aliases(monkeypatch):
    from app.tools import get_ratings
    rows = [
        {"TEAM_ID": 1, "TEAM_NAME": "Boston Celtics", "GP": 82, "W": 60, "L": 22,
         "DEF_RATING": 104.3, "OFF_RATING": 118.1},
        {"TEAM_ID": 2, "TEAM_NAME": "Oklahoma City Thunder", "GP": 82, "W": 57, "L": 25,
         "DEF_RATING": 106.9, "OFF_RATING": 117.2},
    ]
    monkeypatch.setattr(
        "app.tools.league._warehouse_or_live",
        lambda *args, **kwargs: (rows, {"source": "fixture"}),
    )
    out = get_ratings.invoke({
        "requested_metric": "DEF_RATING", "ranking_direction": "asc",
        "season": "2025-26",
    })
    answer = out["meta"]["deterministic_answer"]
    assert "defensive rating" in answer
    assert "Boston Celtics" in answer and "lowest" in answer
    assert "{" not in answer and "}" not in answer
    assert "DEF_RATING" not in answer
