from __future__ import annotations

import json
from datetime import datetime

import pytest

from v2.contracts import EvidenceEnvelope
from v2.tests.compatibility.replay import load_replay, save_replay


def test_replay_round_trip_is_prompt_free(tmp_path):
    item = EvidenceEnvelope(
        evidence_id="ev", capability="ratings", source="fixture",
        observed_at=datetime(2026, 9, 14), rows={"net": 8.2},
    )
    path = tmp_path / "replay.json"
    save_replay(path, "ratings", "abc123", [([item], [{"name": "ratings", "status": "ok"}])])
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
