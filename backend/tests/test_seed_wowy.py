import polars as pl

import scripts.seed_wowy as seed


def _frame(rows):
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def test_parse_self_row_preferred_for_single() -> None:
    rows = [
        {"EntityId": "2544", "Minutes": 3941, "PlusMinus": 144},
        {"EntityId": "2544-123", "Minutes": 226, "PlusMinus": -25},
    ]
    parsed = seed.parse_wowy_frame(_frame(rows), 2544, "2026-27", "ts", "wowy:2544")
    assert parsed is not None
    single, multi, wl, source, season, fetched_at, entity = parsed
    assert single["EntityId"] == "2544"
    assert len(multi) == 2
    assert wl is None
    assert source == "pbpstats"
    assert entity == "wowy:2544"


def test_parse_falls_back_to_unhyphenated_row() -> None:
    rows = [
        {"EntityId": "2544-123", "Minutes": 226},
        {"EntityId": "2544", "Minutes": 100},
    ]
    parsed = seed.parse_wowy_frame(_frame(rows), 9999, "2026-27", "ts", "wowy:9999")
    assert parsed[0]["EntityId"] == "2544"


def test_parse_empty_frame_returns_none() -> None:
    assert seed.parse_wowy_frame(None, 2544, "2026-27", "ts", "wowy:2544") is None
    assert seed.parse_wowy_frame(pl.DataFrame(), 2544, "2026-27", "ts", "wowy:2544") is None


def test_row_shape_matches_existing_warehouse_row() -> None:
    rows = [{"EntityId": "2544", "Minutes": 1}]
    parsed = seed.parse_wowy_frame(_frame(rows), 2544, "2026-27", "ts", "wowy:2544")
    assert len(parsed) == 7
    assert isinstance(parsed[0], dict)
    assert isinstance(parsed[1], list)
    assert isinstance(parsed[1][0], dict)
