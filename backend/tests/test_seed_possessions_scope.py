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


def _loc_row(team_id, location):
    return {"team_id": team_id, "location": location}


def test_home_away_resolves_from_location_column():
    rows = [
        _loc_row(0, "h"),
        _loc_row(1610612738, "h"),
        _loc_row(1610612737, "v"),
        _loc_row(0, ""),
    ]
    assert seed_possessions.resolve_home_away(rows) == (1610612738, 1610612737)


def test_home_away_unresolvable_without_sides():
    assert seed_possessions.resolve_home_away([_loc_row(0, "h")]) is None
    assert seed_possessions.resolve_home_away([]) is None


def test_main_dry_run_prints_pilot_plan(monkeypatch, tmp_path, capsys):
    game_id = "0022400001"
    parquet = tmp_path / "season.parquet"
    monkeypatch.setattr(seed_possessions, "season_for_game", lambda value: 2024)
    monkeypatch.setattr(seed_possessions, "ensure_parquet", lambda year, path: parquet)
    monkeypatch.setattr(seed_possessions, "season_games", lambda path: [game_id])
    target = tmp_path / "target.duckdb"
    parquet_dir = tmp_path / "parquet"
    result = seed_possessions.main([
        "--target", str(target), "--parquet-dir", str(parquet_dir),
        "--source-db", str(tmp_path / "source.duckdb"), "--pilot-game", game_id,
        "--dry-run",
    ])
    assert result == 0
    assert capsys.readouterr().out.splitlines()[-2:] == [
        f"{seed_possessions.TABLE} 2023-24 {game_id}",
        "games: 1",
    ]
