import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.tools import get_leaders, get_ratings

def test_three_point_percentage_uses_official_makes_floor():
    out = get_leaders.invoke({"stat_category": "FG3_PCT"})
    assert out["ok"] and out["rows"]
    assert out["meta"]["qualification"] == "82+ made threes"
    lead = out["rows"][0]
    assert lead["FG3A"] >= 82
    assert all(r["FG3_PCT"] <= lead["FG3_PCT"] for r in out["rows"])
    answer = out["meta"]["deterministic_answer"]
    assert lead["PLAYER"] in answer
    assert f"{lead['FG3A']} attempts" in answer

def test_named_team_ratings_is_one_call():
    out = get_ratings.invoke({"team": "Warriors", "season": "2025-26"})
    assert out["ok"]
    assert len(out["rows"]) == 1
    assert out["rows"][0]["TEAM"] == "GSW"
    row = out["rows"][0]
    answer = out["meta"]["deterministic_answer"]
    assert str(row["OFF_RATING"]) in answer
    assert str(row["DEF_RATING"]) in answer

def test_true_shooting_leader_is_qualified_and_one_call():
    out = get_leaders.invoke({"stat_category": "TS_PCT", "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["stat_category"] == "TS_PCT"
    assert out["meta"]["qualification"] == "1,000+ total minutes"
    assert out["rows"][0]["TS_PCT"] == 77.2
    assert "77.2% true shooting" in out["meta"]["deterministic_answer"]

def test_true_shooting_answer_names_the_minutes_behind_the_floor():
    st = _drain("Who leads the league in true shooting percentage this season?")
    out = st["tool_results"][0]
    lead = out["rows"][0]
    con = store.connect(read_only=True)
    try:
        total_minutes = con.execute(
            "SELECT GP * MIN FROM silver_advanced WHERE _season = ? "
            "AND PLAYER_NAME = ?",
            [out["meta"]["season"], lead["PLAYER"]]).fetchone()[0]
    finally:
        con.close()
    answer = out["meta"]["deterministic_answer"]
    assert lead["TOTAL_MINUTES"] == pytest.approx(total_minutes)
    assert f"{total_minutes:,.0f} total minutes" in answer
    assert f"({lead['GP']} games; {total_minutes:,.0f} total minutes)" in answer
    assert "games; 1,000+ total minutes" not in answer

def test_steals_per_game_leader_carries_sample_size():
    from shared import store
    out = get_leaders.invoke({"stat_category": "SPG", "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["stat_category"] == "SPG"
    assert out["meta"]["qualification"] == "500+ total minutes"
    assert out["meta"]["min_attempts"] == 0
    assert out["meta"]["ranking_direction"] == "desc"
    assert out["meta"]["season"] == "2025-26"
    assert out["meta"]["rows"] == len(out["rows"])
    lead = out["rows"][0]
    assert set(lead) == {"RANK", "PLAYER", "TEAM", "SPG", "GP", "MIN",
                         "PLAYER_NAME"}
    assert out["meta"]["qualification_floor"] == {
        "metric": "total_minutes", "floor": 500,
        "label": "500+ total minutes", "cleared_column": "MIN"}
    assert all(r["MIN"] >= 500 for r in out["rows"])
    assert f"{lead['MIN']:,.0f} total minutes" in (
        out["meta"]["deterministic_answer"])
    assert [r["RANK"] for r in out["rows"]] == list(
        range(1, len(out["rows"]) + 1))
    assert all(isinstance(r["GP"], int) and r["GP"] > 0 for r in out["rows"])
    assert len({r["GP"] for r in out["rows"]}) > 1
    rates = [r["SPG"] for r in out["rows"]]
    assert rates == sorted(rates, reverse=True)
    assert any(rate != round(rate, 2) for rate in rates)
    con = store.connect(read_only=True)
    try:
        raw = {player: (rate, gp, minutes) for player, rate, gp, minutes in
            con.execute(
                "SELECT PLAYER, STL * 1.0 / GP, GP, MIN "
                "FROM silver_leaders_stl WHERE _season = '2025-26' "
                "AND GP > 0 AND MIN >= 500").fetchall()}
    finally:
        con.close()
    assert len(raw) == len(out["rows"])
    assert [(r["SPG"], r["GP"], r["MIN"]) for r in out["rows"]] == [
        (raw[r["PLAYER"]][0], raw[r["PLAYER"]][1], raw[r["PLAYER"]][2])
        for r in out["rows"]]
    answer = out["meta"]["deterministic_answer"]
    assert f"{lead['SPG']:.2f} steals per game" in answer
    assert f"{lead['GP']} games" in answer

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
        "shared.tools.league._warehouse_or_live",
        lambda *args, **kwargs: ([], {"source": "fixture", "rows": 0}),
    )
    monkeypatch.setattr("shared.store.connect", lambda **_: Connection())
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
        "FG3M": 140, "FG3A": 300, "FG3M_PER_GAME": 2.0,
        "FG3A_PER_GAME": 4.3, "GP": 70, "MPG": 1800,
        "PLAYER_NAME": "A",
    }

def test_leader_routing_rejects_invalid_direction_and_volume():
    with pytest.raises(ValueError, match="ranking_direction"):
        get_leaders.invoke({"ranking_direction": "sideways"})
    with pytest.raises(ValueError, match="min_attempts"):
        get_leaders.invoke({"min_attempts": -1})

@pytest.mark.parametrize(("metric", "direction"), [
    ("DEF_RATING", "asc"),
    ("TS_PCT", "desc"),
    ("TM_TOV_PCT", "asc"),
])
def test_team_metric_rank_binds_requested_field_and_direction(
        metric, direction):
    out = get_ratings.invoke({
        "requested_metric": metric, "ranking_direction": direction,
        "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["requested_metric"] == metric
    assert out["meta"]["ranking_direction"] == direction
    assert out["meta"]["claim_value_field"] == metric
    values = [r[metric] for r in out["rows"]]
    assert values == sorted(values, reverse=(direction == "desc"))
    answer = out["meta"]["deterministic_answer"]
    assert out["rows"][0]["TEAM_NAME"] in answer

def test_blocks_per_game_uses_full_blocks_totals_and_unrounded_sort():
    out = get_leaders.invoke({"stat_category": "BPG", "season": "2025-26"})
    assert out["ok"] is True
    assert out["meta"]["stat_category"] == "BPG"
    assert out["meta"]["qualification"] == "500+ total minutes"
    assert [r["PLAYER"] for r in out["rows"][:5]] == [
        "Victor Wembanyama", "Alex Sarr", "Chet Holmgren", "Jay Huff", "Evan Mobley"]
    assert all(r["GP"] for r in out["rows"][:5])
    assert out["rows"][2]["BPG"] > out["rows"][3]["BPG"] > out["rows"][4]["BPG"]
    con = store.connect(read_only=True)
    try:
        full_totals = dict(con.execute(
            "SELECT PLAYER, BLK * 1.0 / GP FROM silver_leaders_blk "
            "WHERE _season = '2025-26' AND GP > 0 AND MIN >= 500").fetchall())
    finally:
        con.close()
    assert [r["BPG"] for r in out["rows"][:5]] == [
        full_totals[r["PLAYER"]] for r in out["rows"][:5]]
    rates = [r["BPG"] for r in out["rows"]]
    assert all(a >= b for a, b in zip(rates, rates[1:]))

def test_team_rating_tool_enum_and_planner_vocabulary_stay_aligned():
    from shared.tools.rating_metrics import TEAM_RATING_METRICS
    assert TEAM_RATING_METRICS == {
        "OFF_RATING": {"label": "offensive rating", "format": "general", "direction": "desc"},
        "DEF_RATING": {"label": "defensive rating", "format": "general", "direction": "asc"},
        "NET_RATING": {"label": "net rating", "format": "general", "direction": "desc"},
        "PACE": {"label": "pace", "format": "general", "direction": "desc"},
        "TS_PCT": {"label": "true shooting percentage", "format": "decimal3", "direction": "desc"},
        "TM_TOV_PCT": {"label": "turnover percentage", "format": "decimal3", "direction": "asc"},
    }

def test_bound_warehouse_read_paths_and_lineage(monkeypatch,tmp_path):
    import hashlib
    from shared import store
    from shared.tools import _core
    from shared.sources.base import FetchResult, FetchMeta
    import polars as pl
    db=tmp_path/'warehouse.duckdb';db.write_bytes(b'initial');monkeypatch.setattr(store,'DB_PATH',db)
    class F:
        height=1;columns=[]
        def head(self,n):return self
        def to_dicts(self):return [{'x':1}]
    monkeypatch.setattr(store,'read_frame',lambda *a,**k:F())
    rows,meta=_core._warehouse_or_live('t','x=?',[1],lambda:None,'2025-26')
    assert meta['warehouse_sha256']==hashlib.sha256(
        (7).to_bytes(8,'little')+b'initial'+b'tial'+b'initial').hexdigest()
    monkeypatch.setattr(store,'read_frame',lambda *a,**k:None if db.read_bytes()==b'initial' else F())
    live=FetchResult(frame=pl.DataFrame({'x':[1]}),meta=FetchMeta(source='live',season='2025-26',fetched_at='2026-09-19'),ok=True)
    monkeypatch.setattr(store,'save_frame',lambda *a,**k:db.write_bytes(b'post-save'))
    rows,meta=_core._warehouse_or_live('t','x=?',[1],lambda:live,'2026-27',live_first=True)
    assert meta['warehouse_sha256']==hashlib.sha256(
        (9).to_bytes(8,'little')+b'post-save'+b'-save'+b'post-save').hexdigest()
    def mutate(*a,**k):db.write_bytes(b'external');return F()
    monkeypatch.setattr(store,'read_frame',mutate)
    with pytest.raises(RuntimeError,match='identity changed'):_core._bound_warehouse_read('t','x=?',[1])

def test_stale_fallback_binds_fallback_read_and_legitimate_writer_is_serialized(monkeypatch,tmp_path):
    from contextlib import contextmanager
    from shared import store
    from shared.tools import _core
    from shared.sources.base import empty
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
    from shared.tools import get_ratings
    rows = [
        {"TEAM_ID": 1, "TEAM_NAME": "Boston Celtics", "GP": 82, "W": 60, "L": 22,
         "DEF_RATING": 104.3, "OFF_RATING": 118.1},
        {"TEAM_ID": 2, "TEAM_NAME": "Oklahoma City Thunder", "GP": 82, "W": 57, "L": 25,
         "DEF_RATING": 106.9, "OFF_RATING": 117.2},
    ]
    monkeypatch.setattr(
        "shared.tools.league._warehouse_or_live",
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
