from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from v2.contracts import EvidenceEnvelope
from v2.tests.compatibility.replay import load_replay, save_replay


def test_replay_round_trip_is_prompt_free(tmp_path):
    item = EvidenceEnvelope(
        evidence_id="ev", capability="ratings", source="fixture",
        observed_at=datetime(2026, 9, 14, tzinfo=UTC), rows={"net": 8.2},
    )
    path = tmp_path / "replay.json"
    save_replay(path, "ratings", "abc123", [([item], [{"call_id": "call", "name": "ratings", "args": {},
                                                  "status": "ok", "error": None}])])
    raw = path.read_text().casefold()
    assert all(key not in raw for key in ('"prompt"', '"question"', '"answer"', '"transcript"'))
    replay = load_replay(path)
    assert replay["turns"][0]["evidence"][0] == item


def test_replay_rejects_prompt_material(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 2, "scenario_id": "x", "revision": "a",
                                "prompt": "hidden", "turns": []}))
    with pytest.raises(ValueError, match="prompt"):
        load_replay(path)


@pytest.mark.parametrize("payload,error", [
    ({"version": 2, "scenario_id": "x", "revision": "r"}, "top-level"),
    ({"version": 2, "scenario_id": " ", "revision": "r", "turns": []},
     "scenario_id"),
    ({"version": 2, "scenario_id": "x", "revision": "r", "turns": {}},
     "turns must be a list"),
    ({"version": 2, "scenario_id": "x", "revision": "r",
      "turns": [{"evidence": []}]}, "replay turn"),
    ({"version": 2, "scenario_id": "x", "revision": "r",
      "turns": [{"evidence": {}, "tools": []}]}, "must be lists"),
])
def test_replay_rejects_partial_or_mistyped_structure(tmp_path, payload, error):
    path = tmp_path / "bad-shape.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=error):
        load_replay(path)


@pytest.mark.parametrize("nested", [
    {"evidence": [], "tools": [{"name": "ratings", "args": {"prompt": "hidden"}}]},
    {"evidence": [{"transcript": "hidden"}], "tools": []},
])
def test_replay_rejects_nested_prompt_material(tmp_path, nested):
    path = tmp_path / "nested.json"
    path.write_text(json.dumps({
        "version": 2, "scenario_id": "x", "revision": "r",
        "turns": [nested],
    }))
    with pytest.raises(ValueError, match="forbidden prompt material"):
        load_replay(path)


def test_save_replay_rejects_prompt_material_in_tool_payload(tmp_path):
    with pytest.raises(ValueError, match="forbidden prompt material"):
        save_replay(
            tmp_path / "bad.json", "x", "r",
            [([], [{"call_id": "call", "name": "tool",
                    "args": {"question": "hidden"}, "status": "ok", "error": None}])],
        )
    assert not (tmp_path / "bad.json").exists()


def test_replay_io_rejects_symlinked_file(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("{}")
    path = tmp_path / "replay.json"
    path.symlink_to(target)
    item = EvidenceEnvelope(
        evidence_id="ev", capability="ratings", source="fixture",
        observed_at=datetime.now(UTC), rows={"net": 8.2},
    )
    for operation in (
        lambda: load_replay(path),
        lambda: save_replay(path, "x", "r", [([item], [])]),
    ):
        with pytest.raises(ValueError, match="file cannot be a symlink"):
            operation()
    assert target.read_text() == "{}"


def test_save_replay_leaves_no_partial_or_temporary_file_on_serialization_failure(
    tmp_path, monkeypatch,
):
    def fail_dump(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("v2.tests.compatibility.replay.json.dump", fail_dump)
    path = tmp_path / "replay.json"
    with pytest.raises(OSError, match="disk full"):
        save_replay(path, "x", "r", [([], [])])
    assert not path.exists()
    assert not list(tmp_path.glob(".replay-*"))


def test_replay_rejects_cross_turn_conflicting_evidence_identity(tmp_path):
    first = EvidenceEnvelope(
        evidence_id="same", capability="ratings", source="fixture",
        observed_at=datetime.now(UTC), rows={"net": 8.2},
    )
    second = first.model_copy(update={"rows": {"net": 2.1}})
    path = tmp_path / "conflict.json"
    save_replay(path, "x", "r", [([first], []), ([second], [])])
    with pytest.raises(ValueError, match="conflicting payloads"):
        load_replay(path)


@pytest.mark.parametrize("tool,error", [
    ({"name": "ratings", "status": "ok"}, "missing or unknown"),
    ({"call_id": " ", "name": "ratings", "args": {}, "status": "ok",
      "error": None}, "call_id must be non-empty"),
    ({"call_id": "call", "name": "ratings", "args": [], "status": "ok",
      "error": None}, "args must be an object"),
    ({"call_id": "call", "name": "ratings", "args": {}, "status": "ok",
      "error": "bad"}, "cannot carry an error"),
    ({"call_id": "call", "name": "ratings", "args": {}, "status": "failed",
      "error": None}, "requires a non-empty error"),
])
def test_replay_rejects_malformed_tool_attempt(tmp_path, tool, error):
    path = tmp_path / "bad-tool.json"
    path.write_text(json.dumps({
        "version": 2, "scenario_id": "x", "revision": "r",
        "turns": [{"evidence": [], "tools": [tool]}],
    }))
    with pytest.raises(ValueError, match=error):
        load_replay(path)


def test_replay_rejects_unknown_cross_turn_evidence_lineage(tmp_path):
    orphan = EvidenceEnvelope(
        evidence_id="child", capability="calculation", source="runtime",
        observed_at=datetime.now(UTC), rows={"gap": 9}, lineage=["missing"],
    )
    path = tmp_path / "orphan.json"
    save_replay(path, "x", "r", [([orphan], [])])
    with pytest.raises(ValueError, match="unknown evidence lineage"):
        load_replay(path)


def test_replay_accepts_lineage_to_evidence_from_earlier_turn(tmp_path):
    parent = EvidenceEnvelope(
        evidence_id="parent", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), rows={"wins": 61},
    )
    child = EvidenceEnvelope(
        evidence_id="child", capability="calculation", source="runtime",
        observed_at=datetime.now(UTC), rows={"gap": 9}, lineage=["parent"],
    )
    path = tmp_path / "lineage.json"
    save_replay(path, "x", "r", [([parent], []), ([child], [])])
    replay = load_replay(path)
    assert replay["turns"][1]["evidence"][0] == child
