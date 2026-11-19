import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.phases import FAMILY_SQL, get_phase_shot_splits


def test_team_rs_vs_playoffs_rows():
    res = get_phase_shot_splits.invoke(
        {"team": "BOS", "season": "2023-24"})
    assert res["ok"] is True
    zones = [r for r in res["rows"] if r["kind"] == "zone"]
    families = [r for r in res["rows"] if r["kind"] == "family"]
    assert len(zones) == 5
    assert len(families) == 4
    rim = next(r for r in zones if r["bucket"] == "rim")
    assert rim["rs_fga"] > 0 and rim["po_fga"] > 0
    assert 0 < rim["rs_share"] < 1
    assert rim["efg_delta_pp"] is not None


def test_player_splits():
    res = get_phase_shot_splits.invoke(
        {"player": "Jayson Tatum", "season": "2023-24"})
    assert res["ok"] is True
    assert res["meta"]["playoff_games_sample"] > 0
    pull = next(r for r in res["rows"]
                if r["kind"] == "family" and r["bucket"] == "pull_up")
    assert pull["po_fga"] > 0


def test_sources_cited():
    res = get_phase_shot_splits.invoke(
        {"team": "BOS", "season": "2023-24"})
    srcs = res["meta"]["sources"]
    assert srcs and srcs[0]["table"] == "silver_hist_shots"
    assert srcs[0]["provider"]
    assert srcs[0]["covers"] == "regular season + playoffs"
    assert "tracking" in res["meta"]


def test_no_playoff_team_warns_not_fails():
    res = get_phase_shot_splits.invoke(
        {"team": "CHI", "season": "2023-24"})
    assert res["ok"] is True
    assert res["meta"]["playoff_games_sample"] == 0
    assert "no playoff shots" in res["meta"]["warning"]


def test_requires_exactly_one_subject():
    res = get_phase_shot_splits.invoke({"player": "Tatum", "team": "BOS"})
    assert res["ok"] is False
    res = get_phase_shot_splits.invoke({})
    assert res["ok"] is False


def test_family_sql_buckets():
    from shared.tools.phases import _pair
    rows = [
        {"bucket": "pull_up", "phase": "regular_season",
         "fga": 10, "fgm": 4, "tpm": 1},
        {"bucket": "pull_up", "phase": "playoffs",
         "fga": 5, "fgm": 1, "tpm": 0},
        {"bucket": "catch_and_shoot", "phase": "regular_season",
         "fga": 10, "fgm": 6, "tpm": 4},
        {"bucket": "catch_and_shoot", "phase": "playoffs",
         "fga": 5, "fgm": 4, "tpm": 3},
    ]
    out = _pair(rows, "family", ("catch_and_shoot", "pull_up"))
    assert len(out) == 2
    pull = next(r for r in out if r["bucket"] == "pull_up")
    assert pull["rs_fga"] == 10 and pull["po_fga"] == 5
    assert pull["rs_share"] == 0.5
    assert pull["efg_delta_pp"] == -25.0
    assert FAMILY_SQL
