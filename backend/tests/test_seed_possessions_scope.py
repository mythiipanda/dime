import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_possessions  # noqa: E402


def test_regular_and_playoff_games_are_in_scope():
    assert seed_possessions.scope_reason("0022400001") is None
    assert seed_possessions.scope_reason("0032400001") is None
    assert seed_possessions.scope_reason("0042400001") is None


def test_exhibition_games_are_out_of_scope():
    assert seed_possessions.scope_reason("0012400001") == \
        "exhibition/preseason out of scope"
    assert seed_possessions.scope_reason("0052400001") == \
        "exhibition/preseason out of scope"
    assert seed_possessions.scope_reason("0062400001") == \
        "exhibition/preseason out of scope"
