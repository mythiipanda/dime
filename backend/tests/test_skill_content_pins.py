import hashlib
import json
from pathlib import Path

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


def _pin(path):
    data = path.read_bytes()
    data.decode("utf-8")
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _snapshot():
    return {"files": {_relative(path): _pin(path) for path in _skill_paths()}}


def _pins():
    return json.loads(PINS.read_text(encoding="utf-8"))


def test_pin_file_is_canonical_serialization():
    assert PINS.read_bytes() == _serialize(_pins())


def test_every_skill_file_is_pinned():
    assert list(_pins()["files"].keys()) == [_relative(path) for path in _skill_paths()]


def test_skill_content_pins_match_live():
    assert _serialize(_pins()) == _serialize(_snapshot())
