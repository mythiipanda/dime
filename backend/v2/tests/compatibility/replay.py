from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from v2.contracts import EvidenceEnvelope

_ALLOWED_TOP_LEVEL = {"version", "scenario_id", "revision", "turns"}
_ALLOWED_TURN = {"evidence", "tools"}
_FORBIDDEN = {"prompt", "question", "answer", "messages", "transcript"}


def save_replay(path: Path, scenario_id: str, revision: str,
                turns: list[tuple[list[EvidenceEnvelope], list[dict[str, Any]]]]) -> None:
    payload = {
        "version": 2,
        "scenario_id": scenario_id,
        "revision": revision,
        "turns": [
            {"evidence": [item.model_dump(mode="json") for item in evidence], "tools": tools}
            for evidence, tools in turns
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_replay(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if set(payload) - _ALLOWED_TOP_LEVEL or set(payload).intersection(_FORBIDDEN):
        raise ValueError("replay contains prompt or unknown top-level fields")
    if payload.get("version") != 2:
        raise ValueError("unsupported replay version")
    for turn in payload.get("turns", []):
        if set(turn) - _ALLOWED_TURN or set(turn).intersection(_FORBIDDEN):
            raise ValueError("replay turn contains prompt or unknown fields")
        turn["evidence"] = [EvidenceEnvelope.model_validate(item) for item in turn["evidence"]]
    return payload
