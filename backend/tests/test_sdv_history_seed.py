import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.seed_sdv_history as seed

TABLES = {s["table"] for s in seed.SOURCES}


def test_covers_three_sources() -> None:
    assert TABLES == {"silver_hist_hustle", "silver_coaches_history",
                      "silver_officials"}


def test_ranges_and_min_rows() -> None:
    for s in seed.SOURCES:
        assert s["last"] - s["first"] >= 5
        assert s["min_rows"] > 0
        assert "{y}" in s["pattern"]


def test_label() -> None:
    assert seed.label(2025) == "2024-25"
