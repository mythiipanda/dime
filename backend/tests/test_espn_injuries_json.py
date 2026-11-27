import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl


def _sample_blob_entries():
    return [
        {
            "id": "-56292",
            "longComment": "Gueye will be re-evaluated by medical staff in 7-10 days.",
            "status": "Out",
            "athlete": {"displayName": "Mouhamed Gueye", "active": True},
            "nullable": None,
        }
    ]


def test_serialize_object_columns_produces_valid_json():
    from shared.sources.espn import serialize_object_columns

    frame = pl.DataFrame(
        {"id": [1], "injuries": [_sample_blob_entries()]},
        schema={"id": pl.Int64, "injuries": pl.Object},
    )
    out = serialize_object_columns(frame)
    assert out.schema["injuries"] == pl.Utf8
    cell = out.row(0, named=True)["injuries"]
    parsed = json.loads(cell)
    assert isinstance(parsed, list)
    assert parsed[0]["id"] == "-56292"
    assert parsed[0]["athlete"]["active"] is True
    assert parsed[0]["nullable"] is None


def test_parse_roundtrip_through_injury_entries():
    from shared.sources.espn import serialize_object_columns
    from shared.tools.league.standings import _injury_entries

    frame = pl.DataFrame(
        {"injuries": [_sample_blob_entries()]},
        schema={"injuries": pl.Object},
    )
    cell = serialize_object_columns(frame).row(0, named=True)["injuries"]
    entries = _injury_entries(cell)
    assert len(entries) == 1
    assert entries[0]["status"] == "Out"


def test_scalar_and_none_cells_untouched():
    from shared.sources.espn import serialize_object_columns

    frame = pl.DataFrame(
        {"id": [1, 2], "misc": ["plain", None]},
        schema={"id": pl.Int64, "misc": pl.Utf8},
    )
    out = serialize_object_columns(frame)
    assert out.row(0, named=True)["misc"] == "plain"
    assert out.row(1, named=True)["misc"] is None
    assert out.schema["misc"] == pl.Utf8
