from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from v2.api import routes


def dataset(name, **params):
    return routes.dataset(name=name, season="2025-26", player_id=201939,
                          team_id=0, game_id="", game_date="", stat="PTS",
                          ids="", player_a="", player_b="", fmt="json", **params)


@pytest.mark.parametrize("rows", [[{"LOC_X": 10, "LOC_Y": 20}], []])
def test_shots_live_does_not_write_canonical_warehouse(monkeypatch, rows):
    monkeypatch.setattr(store, "DB_PATH", store.CANONICAL_DB_PATH)
    monkeypatch.setattr(store, "read_frame", lambda *args: pl.DataFrame())
    save = Mock(side_effect=AssertionError("canonical warehouse write"))
    monkeypatch.setattr(store, "save_frame", save)
    monkeypatch.setattr(routes, "_datasets_fetch_live", lambda *args: FetchResult(
        pl.DataFrame(rows), FetchMeta("nba_stats", "2025-26")))
    result = dataset("shots")
    assert result["ok"] is True
    assert len(result["data"]) == len(rows)
    assert result["meta"]["cached"] is False
    if rows:
        assert result["meta"]["source"] == "nba_stats"
    save.assert_not_called()


def test_shots_live_failure_is_structured(monkeypatch):
    monkeypatch.setattr(store, "read_frame", lambda *args: pl.DataFrame())
    monkeypatch.setattr(routes, "_datasets_fetch_live", lambda *args: FetchResult(
        pl.DataFrame(), FetchMeta("nba_stats", "2025-26"), False, "upstream unavailable"))
    result = dataset("shots")
    assert result["ok"] is False
    assert result["error"] == "upstream unavailable"


def test_shots_writable_cache_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "cache.duckdb")
    reads = iter([pl.DataFrame(), pl.DataFrame(), pl.DataFrame({"LOC_X": [10]})])
    monkeypatch.setattr(store, "read_frame", lambda *args: next(reads))
    save = Mock()
    monkeypatch.setattr(store, "save_frame", save)
    monkeypatch.setattr(routes, "_datasets_fetch_live", lambda *args: FetchResult(
        pl.DataFrame({"LOC_X": [10]}), FetchMeta("nba_stats", "2025-26")))
    assert dataset("shots")["data"] == [{"LOC_X": 10}]
    assert save.call_args.args[0] == "silver_shots"
    assert save.call_args.args[2] == "player:201939"


@pytest.mark.parametrize("payload", [
    {"ok": True, "rows": [{"zone": "rim", "FGM": 3, "FGA": 5, "FG_PCT": 0.6}],
     "meta": {"source": "warehouse"}},
    {"ok": True, "rows": [], "meta": {}},
    {"ok": False, "error": "no shot coverage", "meta": {"coverage": "none"}},
])
def test_zone_splits_uses_existing_warehouse_tool(monkeypatch, payload):
    invoke = Mock(return_value=payload)
    monkeypatch.setitem(sys.modules, "shared.tools.player", SimpleNamespace(
        get_shot_zones=SimpleNamespace(invoke=invoke)))
    result = dataset("zone_splits")
    invoke.assert_called_once_with({"player_id": 201939, "season": "2025-26"})
    assert result["ok"] is payload["ok"]
    assert result["meta"] == payload["meta"]
    if payload["ok"]:
        assert result["data"] == payload["rows"]
    else:
        assert result["error"] == payload["error"]
