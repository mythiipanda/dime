import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import backfill


def _fake_dated(rows):
    return list(rows)


def test_incremental_picks_missing_oldest_first(monkeypatch):
    dated = [("0022600001", "2026-10-20"), ("0022600002", "2026-10-21"),
             ("0022600003", "2026-10-22"), ("0022600004", "2026-10-23")]
    monkeypatch.setattr(backfill, "season_games_dated", lambda s, sl: _fake_dated(dated))
    monkeypatch.setattr(backfill, "watermarked_entities", lambda t, s: {"0022600001", "0022600002"})
    picked, info = backfill.incremental_game_list("2026-27", 0, 60, correction_days=3)
    assert picked[:2] == ["0022600003", "0022600004"] or set(picked) >= {"0022600003", "0022600004"}
    assert info["missing"] == 2
    assert info["present"] == 2


def test_incremental_correction_window_refetches_recent(monkeypatch):
    dated = [("0022600001", "2026-10-18"), ("0022600002", "2026-10-21"),
             ("0022600003", "2026-10-22")]
    monkeypatch.setattr(backfill, "season_games_dated", lambda s, sl: _fake_dated(dated))
    monkeypatch.setattr(backfill, "watermarked_entities", lambda t, s: {"0022600001", "0022600002", "0022600003"})
    picked, info = backfill.incremental_game_list("2026-27", 0, 60, correction_days=3)
    assert info["missing"] == 0
    assert info["corrections"] == 2
    assert "0022600001" not in picked
    assert set(picked) == {"0022600002", "0022600003"}


def test_incremental_max_games_caps_oldest_first(monkeypatch):
    dated = [(f"0022600{i:03d}", f"2026-10-{10 + i:02d}") for i in range(100)]
    monkeypatch.setattr(backfill, "season_games_dated", lambda s, sl: _fake_dated(dated))
    monkeypatch.setattr(backfill, "watermarked_entities", lambda t, s: set())
    picked, info = backfill.incremental_game_list("2026-27", 0, 10, correction_days=3)
    assert len(picked) == 10
    assert picked[0] == "0022600000"
    assert info["missing"] == 100


def test_incremental_correction_window_counts_against_cap(monkeypatch):
    dated = [(f"0022600{i:03d}", "2026-10-22") for i in range(20)]
    monkeypatch.setattr(backfill, "season_games_dated", lambda s, sl: _fake_dated(dated))
    present = {f"0022600{i:03d}" for i in range(5)}
    monkeypatch.setattr(backfill, "watermarked_entities", lambda t, s: present)
    picked, info = backfill.incremental_game_list("2026-27", 0, 8, correction_days=3)
    assert info["corrections"] == 5
    assert len(picked) == 8
    assert sum(1 for g in picked if g in present) == 5
