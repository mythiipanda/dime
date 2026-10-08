import polars as pl

from shared import store
from shared.tools import _core as core


def _use_scratch(tmp_path, monkeypatch):
    db = tmp_path / "scratch.duckdb"
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    core.last_completed_season_cache_clear()
    return db


def _unit(frame_rows, entity):
    return pl.DataFrame(frame_rows), entity


def _seed(tmp_path, monkeypatch):
    _use_scratch(tmp_path, monkeypatch)
    tatum_off_t, e1 = _unit([{
        "subject_kind": "player", "subject_id": 1628369,
        "subject_name": "Jayson Tatum", "team_id": 1610612738,
        "team_abbreviation": "BOS", "side": "offense",
        "play_type": "Transition", "percentile": 0.725, "gp": 72,
        "poss_pct": 0.114, "ppp": 1.237, "fg_pct": 0.586,
        "efg_pct": 0.676, "poss": 211, "pts": 261,
        "fgm": 95, "fga": 162,
    }], "playtypes:P:offensive:Transition")
    tatum_off_i, e2 = _unit([{
        "subject_kind": "player", "subject_id": 1628369,
        "subject_name": "Jayson Tatum", "team_id": 1610612738,
        "team_abbreviation": "BOS", "side": "offense",
        "play_type": "Isolation", "percentile": 0.786, "gp": 72,
        "poss_pct": 0.259, "ppp": 1.008, "fg_pct": 0.42,
        "efg_pct": 0.48, "poss": 480, "pts": 484,
        "fgm": 169, "fga": 402,
    }], "playtypes:P:offensive:Isolation")
    tatum_def_i, e3 = _unit([{
        "subject_kind": "player", "subject_id": 1628369,
        "subject_name": "Jayson Tatum", "team_id": 1610612738,
        "team_abbreviation": "BOS", "side": "defense",
        "play_type": "Isolation", "percentile": 0.389, "gp": 72,
        "poss_pct": 0.088, "ppp": 0.964, "fg_pct": 0.396,
        "efg_pct": 0.438, "poss": 56, "pts": 54,
        "fgm": 19, "fga": 48,
    }], "playtypes:P:defensive:Isolation")
    celts_off_t, e4 = _unit([{
        "subject_kind": "team", "subject_id": 1610612738,
        "subject_name": "Boston Celtics", "team_id": 1610612738,
        "team_abbreviation": "BOS", "side": "offense",
        "play_type": "Transition", "percentile": 0.414, "gp": 82,
        "poss_pct": 0.16, "ppp": 1.13, "fg_pct": 0.507,
        "efg_pct": 0.604, "poss": 1442, "pts": 1630,
        "fgm": 606, "fga": 1196,
    }], "playtypes:T:offensive:Transition")
    for frame, entity in ((tatum_off_t, e1), (tatum_off_i, e2),
                          (tatum_def_i, e3), (celts_off_t, e4)):
        store.write_unit("silver_playtypes", frame, "2024-25", "nba_api",
                         entity, "_entity = ?", [entity])


def test_player_offense_profile_pinned_values(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "Jayson Tatum", "kind": "player",
        "side": "offense", "season": "2024-25"})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["subject_id"] == 1628369
    assert rows["subject"] == "Jayson Tatum"
    assert rows["kind"] == "player"
    assert rows["side"] == "offense"
    assert rows["season"] == "2024-25"
    by_type = {p["play_type"]: p for p in rows["play_types"]}
    assert by_type["Transition"]["ppp"] == 1.237
    assert by_type["Transition"]["poss_pct"] == 0.114
    assert by_type["Transition"]["percentile"] == 0.725
    assert by_type["Transition"]["gp"] == 72
    assert by_type["Isolation"]["ppp"] == 1.008
    assert by_type["Isolation"]["poss_pct"] == 0.259
    assert by_type["Isolation"]["percentile"] == 0.786
    assert [p["play_type"] for p in rows["play_types"]] == [
        "Isolation", "Transition"]
    assert out["meta"]["season"] == "2024-25"


def test_team_offense_profile_pinned_values(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "Boston Celtics", "kind": "team",
        "side": "offense", "season": "2024-25"})
    assert out["ok"] is True
    assert out["rows"]["subject_id"] == 1610612738
    entry = out["rows"]["play_types"][0]
    assert entry["play_type"] == "Transition"
    assert entry["ppp"] == 1.13
    assert entry["poss_pct"] == 0.16
    assert entry["percentile"] == 0.414
    assert entry["gp"] == 82


def test_numeric_id_subject(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "1628369", "kind": "player",
        "side": "defense", "season": "2024-25"})
    assert out["ok"] is True
    assert out["rows"]["subject_id"] == 1628369
    entry = out["rows"]["play_types"][0]
    assert entry["play_type"] == "Isolation"
    assert entry["ppp"] == 0.964
    assert entry["poss_pct"] == 0.088
    assert entry["percentile"] == 0.389


def test_schema_and_provenance(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    frame = store.read_frame("silver_playtypes", "_entity = ?",
                             ["playtypes:P:offensive:Transition"])
    required = {"subject_kind", "subject_id", "subject_name", "side",
                "play_type", "percentile", "gp", "poss_pct", "ppp",
                "_source", "_season", "_fetched_at", "_entity"}
    assert required.issubset(set(frame.columns))
    row = frame.to_dicts()[0]
    assert row["_source"] == "nba_api"
    assert row["_season"] == "2024-25"
    assert row["_fetched_at"]
    assert row["_entity"] == "playtypes:P:offensive:Transition"
    assert row["subject_kind"] == "player"
    assert row["side"] == "offense"


def test_unknown_season_refusal(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "Jayson Tatum", "kind": "player",
        "side": "offense", "season": "1998-99"})
    assert out["ok"] is False
    assert "error" in out and out["error"]


def test_unknown_subject_refusal(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "Quux Nonexistent Player", "kind": "player",
        "side": "offense", "season": "2024-25"})
    assert out["ok"] is False
    assert "error" in out and out["error"]


def test_unbackfilled_season_refusal(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    from shared.tools import playtypes
    out = playtypes.get_playtype_profile.invoke({
        "subject": "Jayson Tatum", "kind": "player",
        "side": "offense", "season": "2023-24"})
    assert out["ok"] is False
    assert "2024-25" in out["error"] or "2023-24" in out["error"]
