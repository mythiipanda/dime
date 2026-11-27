import hashlib
import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
PINS = Path(__file__).resolve().parent / "skill_content_pins.json"
SKILLS = BACKEND / "analyst" / "skills"


def _serialize(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _skill_paths():
    return sorted(SKILLS.glob("*/SKILL.md"))


def _relative(path):
    return path.relative_to(ROOT).as_posix()


def _lf_bytes(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def _pin(path):
    data = _lf_bytes(path)
    data.decode("utf-8")
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _normalized_snapshot():
    return {"files": {_relative(path): _pin(path) for path in _skill_paths()}}


def _pins():
    return json.loads(PINS.read_text(encoding="utf-8"))


def test_pin_file_is_canonical_serialization():
    assert PINS.read_bytes() == _serialize(_pins())


def test_every_skill_file_is_pinned():
    assert list(_pins()["files"].keys()) == [_relative(path) for path in _skill_paths()]


@pytest.mark.parametrize(
    "path",
    _skill_paths(),
    ids=[_relative(path) for path in _skill_paths()],
)
def test_skill_content_pin_matches_live(path):
    name = _relative(path)
    expected = _pins()["files"].get(name)
    actual = _pin(path)
    expected_sha256 = expected["sha256"] if expected else "<missing>"
    expected_bytes = expected["bytes"] if expected else "<missing>"
    assert actual == expected, (
        f"{name} drifted\n"
        f"expected sha256={expected_sha256} bytes={expected_bytes}\n"
        f"actual sha256={actual['sha256']} bytes={actual['bytes']}"
    )
