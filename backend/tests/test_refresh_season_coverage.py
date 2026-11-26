import re
from pathlib import Path

import scripts.refresh_warehouse as refresh
import scripts.seed_rosters as rosters

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_current_seeders_not_pinned_to_completed_season() -> None:
    for name in ("seed_hustle_team.py", "seed_shots_2025_26.py",
                 "seed_scoreboard_2025_26.py"):
        text = (SCRIPTS / name).read_text()
        assert 'SEASON = "2025-26"' not in text, name
        assert '"2025-26")' not in text or "current_season" in text, name


def test_refresh_seeders_cover_stale_tables() -> None:
    names = {entry[0] for entry in refresh.SEEDERS}
    for required in ("rapm", "vendor_cap", "hustle_team", "zone_splits",
                     "rosters", "hustle_player", "clutch"):
        assert required in names, required


def test_refresh_seeder_scripts_exist() -> None:
    for _, script, _, _ in refresh.SEEDERS:
        assert (SCRIPTS / script).is_file(), script


def test_rosters_seeder_targets_rosters_table() -> None:
    assert rosters.TABLE == "silver_rosters"
    assert rosters.SOURCE == "nba_api"


def test_rosters_season_dynamic() -> None:
    text = (SCRIPTS / "seed_rosters.py").read_text()
    assert "current_season" in text
    assert '"2025-26"' not in text
