import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools._core import coerce_team_id

def _without_nba_teams(monkeypatch):
    monkeypatch.setitem(sys.modules, "nba_api.stats.static.teams", None)

def test_aliases_resolve_without_nba_api(monkeypatch):
    _without_nba_teams(monkeypatch)
    assert coerce_team_id("BOS") == 1610612738
    assert coerce_team_id("Boston Celtics") == 1610612738
    assert coerce_team_id("boston-celtics") == 1610612738
    assert coerce_team_id("1610612738") == 1610612738
    assert coerce_team_id("ATL") == 1610612737

def test_unknown_team_still_raises_without_nba_api(monkeypatch):
    _without_nba_teams(monkeypatch)
    with pytest.raises(ValueError, match="unknown team"):
        coerce_team_id("London Lions")

def test_blank_team_name_is_rejected(monkeypatch):
    _without_nba_teams(monkeypatch)
    for probe in ("", "   "):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_blank_team_name_is_rejected_with_live_lookup():
    for probe in ("", "   "):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_short_fragments_are_not_guessed_as_teams(monkeypatch):
    _without_nba_teams(monkeypatch)
    for probe in ("a", "LA", "NY"):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_short_fragments_are_not_guessed_with_live_lookup():
    for probe in ("a", "LA", "NY"):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_fabricated_longer_names_are_rejected(monkeypatch):
    _without_nba_teams(monkeypatch)
    for probe in ("Springfield Thunder", "Queens Cobras", "Hawk",
                  "Los Angeles", "Los", "New"):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_fabricated_longer_names_are_rejected_with_live_lookup():
    for probe in ("Springfield Thunder", "Queens Cobras", "Hawk",
                  "Los Angeles", "Los", "New"):
        with pytest.raises(ValueError, match="unknown team"):
            coerce_team_id(probe)

def test_legit_city_and_nickname_aliases_resolve(monkeypatch):
    _without_nba_teams(monkeypatch)
    assert coerce_team_id("Boston") == 1610612738
    assert coerce_team_id("Atlanta") == 1610612737
    assert coerce_team_id("New York") == 1610612752
    assert coerce_team_id("San Antonio") == 1610612759
    assert coerce_team_id("Oklahoma City") == 1610612760
    assert coerce_team_id("Trail Blazers") == 1610612757
    assert coerce_team_id("Warriors") == 1610612744
    assert coerce_team_id("Golden") == 1610612744
    assert coerce_team_id("State Warriors") == 1610612744
    assert coerce_team_id("Boston Celtics") == 1610612738
    assert coerce_team_id("dubs") == 1610612744

def test_static_aliases_match_live_lookup_for_all_teams():
    from nba_api.stats.static import teams as live

    for row in live.get_teams():
        assert coerce_team_id(row["abbreviation"]) == int(row["id"])
        assert coerce_team_id(row["full_name"]) == int(row["id"])
