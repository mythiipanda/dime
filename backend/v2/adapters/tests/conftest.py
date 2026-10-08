import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests_support.synthetic_warehouse import hermetic_warehouse  # noqa: E402
