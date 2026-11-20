import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backfill
from shared.tools._core import completed_season_for_date

def test_default_backfill_range_covers_last_completed_season():
    frontier = completed_season_for_date(dt.date.today())
    assert frontier is not None
    assert frontier in backfill.parse_seasons(backfill.default_seasons())

def test_default_end_derives_from_completed_season():
    assert backfill.default_seasons().endswith(
        completed_season_for_date(dt.date.today()))

def test_missing_core_module_falls_back_loudly(monkeypatch, caplog):
    import logging
    monkeypatch.setitem(sys.modules, "shared.tools._core", None)
    with caplog.at_level(logging.WARNING, logger=backfill.logger.name):
        assert backfill.default_seasons() == f"{backfill.FIRST_SEASON}:2025-26"
    assert any("default_seasons" in r.message and "2025-26" in r.message
               for r in caplog.records)

def test_unexpected_import_failure_propagates(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def boom(name, *args, **kwargs):
        if name == "shared.tools._core":
            raise RuntimeError("synthetic import failure")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", boom)
    try:
        backfill.default_seasons()
    except RuntimeError as exc:
        assert "synthetic import failure" in str(exc)
    else:
        raise AssertionError("unexpected import failure was swallowed")
