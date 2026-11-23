from shared.tools import _core


def test_resolve_season_canonicalizes_bare_year():
    assert _core.resolve_season("2025") == "2024-25"
    assert _core.resolve_season(2021) == "2020-21"
    assert _core.resolve_season("2024-25") == "2024-25"


def test_coerce_team_id_accepts_media_aliases():
    assert _core.coerce_team_id("BRK") == 1610612751
    assert _core.coerce_team_id("PHO") == 1610612756
    assert _core.coerce_team_id("1610612743") == 1610612743
    assert _core.coerce_team_id("MIL") == 1610612749
    assert _core.coerce_team_id("Phoenix Suns") == 1610612756


def test_empty_and_league_scope_team_errors_name_the_aggregate_path():
    for raw in ("", "ALL", "league", "every"):
        try:
            _core.coerce_team_id(raw)
        except ValueError as exc:
            msg = str(exc)
            assert "leaders" in msg or "sql_exec" in msg, msg
        else:
            raise AssertionError(f"expected ValueError for {raw!r}")


def test_metric_and_direction_aliases():
    from shared.tools.league.ratings import _METRIC_ALIASES, _DIRECTION_ALIASES
    assert _METRIC_ALIASES["NET"] == "NET_RATING"
    assert _METRIC_ALIASES["off".upper()] == "OFF_RATING"
    assert _METRIC_ALIASES["TS%"] == "TS_PCT"
    assert _DIRECTION_ALIASES["highest"] == "desc"
    assert _DIRECTION_ALIASES["worst"] == "asc"
