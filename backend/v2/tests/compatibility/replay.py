from __future__ import annotations

import json
from pathlib import Path
import os
import tempfile
from typing import Any

from v2.contracts import EvidenceEnvelope

_ALLOWED_TOP_LEVEL = {"version", "scenario_id", "revision", "turns"}
_ALLOWED_TURN = {"evidence", "tools"}
_FORBIDDEN = {"prompt", "question", "answer", "messages", "transcript"}


def _reject_forbidden(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = sorted(
            str(key) for key in value if str(key).casefold() in _FORBIDDEN)
        if forbidden:
            raise ValueError(f"replay contains forbidden prompt material: {forbidden}")
        for child in value.values():
            _reject_forbidden(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden(child)


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
    _reject_forbidden(payload)
    if path.is_symlink():
        raise ValueError("replay file cannot be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".replay-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_replay(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("replay file cannot be a symlink")
    payload = json.loads(path.read_text())
    _reject_forbidden(payload)
    if not isinstance(payload, dict) or set(payload) != _ALLOWED_TOP_LEVEL:
        raise ValueError("replay contains prompt, missing, or unknown top-level fields")
    if payload["version"] != 2:
        raise ValueError("unsupported replay version")
    for field in ("scenario_id", "revision"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"replay {field} must be non-empty")
    if not isinstance(payload["turns"], list):
        raise ValueError("replay turns must be a list")
    seen_evidence: dict[str, EvidenceEnvelope] = {}
    for turn in payload["turns"]:
        if not isinstance(turn, dict) or set(turn) != _ALLOWED_TURN:
            raise ValueError("replay turn contains prompt, missing, or unknown fields")
        if not isinstance(turn["evidence"], list) or not isinstance(turn["tools"], list):
            raise ValueError("replay evidence and tools must be lists")
        turn["evidence"] = [
            EvidenceEnvelope.model_validate(item) for item in turn["evidence"]
        ]
        for item in turn["evidence"]:
            previous = seen_evidence.get(item.evidence_id)
            if previous is not None and previous != item:
                raise ValueError(
                    f"replay evidence id {item.evidence_id} has conflicting payloads")
            seen_evidence[item.evidence_id] = item
    return payload
