import json
import sys
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import team as team_mod  # noqa: E402
from v2.adapters import call_capability  # noqa: E402

REPO_WAREHOUSE = (
    Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"
)

REGULAR_TABLES = ("silver_team_games", "silver_hist_gamelogs")
PLAYOFF_TABLES = ("silver_playoffs", "silver_playoff_gamelogs")
SERIES_TABLES = REGULAR_TABLES + PLAYOFF_TABLES

UNCOVERED_SEASON = "2005-06"


@contextmanager
def _warehouse():
    con = duckdb.connect(str(REPO_WAREHOUSE), read_only=True)
    try:
        yield con
    finally:
        con.close()


def _require_warehouse():
    if not REPO_WAREHOUSE.exists():
        pytest.skip(f"no warehouse at {REPO_WAREHOUSE}")


def _rows(con, table, season):
    return con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE _season = ?", [season]
    ).fetchone()[0]


def _meetings(con, a, b, season):
    return con.execute(
        "SELECT COUNT(DISTINCT game_id) FROM silver_hist_gamelogs"
        " WHERE _season = ? AND season_type = 'regular-season'"
        "   AND ((team_abbreviation = ? AND matchup ILIKE ?)"
        "     OR (team_abbreviation = ? AND matchup ILIKE ?))",
        [season, a, f"%{b}%", b, f"%{a}%"],
    ).fetchone()[0]


def _wins(con, a, b, season):
    return con.execute(
        "SELECT COUNT(*) FILTER (WHERE wl = 'W') FROM silver_hist_gamelogs"
        " WHERE _season = ? AND season_type = 'regular-season'"
        "   AND team_abbreviation = ? AND matchup ILIKE ?",
        [season, a, f"%{b}%"],
    ).fetchone()[0]


def _series(a, b, season):
    return team_mod.get_season_series.invoke(
        {"team_a": a, "team_b": b, "season": season})


def _brief_rows(a, b, season):
    env = call_capability("matchup_brief", {"a": a, "b": b, "season": season})
    assert env.capability == "matchup_brief"
    return env.rows


def test_the_uncovered_season_fixture_really_is_uncovered():
    _require_warehouse()
    with _warehouse() as con:
        for table in SERIES_TABLES:
            assert _rows(con, table, UNCOVERED_SEASON) == 0, table


def test_a_season_no_table_covers_fails_loud_naming_the_season():
    _require_warehouse()
    out = _series("CLE", "MIL", UNCOVERED_SEASON)
    assert out["ok"] is False
    assert "rows" not in out
    assert UNCOVERED_SEASON in out["error"]
    for table in SERIES_TABLES:
        assert table in out["error"], table
    assert "holds" in out["error"]


def test_a_pair_that_never_met_in_a_covered_season_names_the_tables_read():
    _require_warehouse()
    with _warehouse() as con:
        assert _rows(con, "silver_hist_gamelogs", "2019-20") > 0
        assert _meetings(con, "ATL", "NOP", "2019-20") == 0
    out = _series("ATL", "NOP", "2019-20")
    assert out["ok"] is False
    assert "rows" not in out
    assert "2019-20" in out["error"]
    for table in SERIES_TABLES:
        assert table in out["error"], table
    assert "do not report a 0-0 record" in out["error"].lower()


def test_a_pair_with_four_regular_season_meetings_reports_all_four():
    _require_warehouse()
    with _warehouse() as con:
        assert _rows(con, "silver_team_games", "2024-25") == 0
        assert _meetings(con, "CLE", "MIL", "2024-25") == 4
    out = _series("CLE", "MIL", "2024-25")
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 4
    assert summary["games_by_phase"] == {"regular season": 4}
    assert summary["games_won"] == {"CLE": 4, "MIL": 0}
    assert out["meta"]["regular_season_source"] == "silver_hist_gamelogs"
    assert len(out["rows"]["games"]) == 4


def test_the_second_battery_pair_reports_its_three_meetings():
    _require_warehouse()
    with _warehouse() as con:
        assert _meetings(con, "MIN", "DAL", "2024-25") == 3
        assert (_wins(con, "MIN", "DAL", "2024-25"),
                _wins(con, "DAL", "MIN", "2024-25")) == (2, 1)
    out = _series("MIN", "DAL", "2024-25")
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 3
    assert summary["games_by_phase"] == {"regular season": 3}
    assert summary["games_won"] == {"MIN": 2, "DAL": 1}


@pytest.mark.parametrize(
    "a, b, season, meetings, wins_a, wins_b",
    [
        ("CLE", "MIL", "2019-20", 3, 0, 3),
        ("CLE", "MIL", "2009-10", 4, 3, 1),
        ("MIN", "DAL", "2009-10", 4, 1, 3),
    ],
)
def test_every_season_counts_from_the_table_that_holds_it(
    a, b, season, meetings, wins_a, wins_b,
):
    _require_warehouse()
    with _warehouse() as con:
        assert _meetings(con, a, b, season) == meetings
        assert _wins(con, a, b, season) == wins_a
        assert _wins(con, b, a, season) == wins_b
    out = _series(a, b, season)
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == meetings
    assert summary["games_by_phase"] == {"regular season": meetings}
    assert summary["games_won"] == {a: wins_a, b: wins_b}
    assert out["meta"]["coverage"]["regular season"]["source"] == (
        "silver_hist_gamelogs")


def test_an_uncovered_playoff_phase_publishes_no_series_record():
    _require_warehouse()
    with _warehouse() as con:
        for table in PLAYOFF_TABLES:
            assert _rows(con, table, "2019-20") == 0, table
    out = _series("CLE", "MIL", "2019-20")
    assert out["ok"] is True
    summary = out["rows"]["summary"]
    assert summary["games"] == 3
    assert summary["series_played"] is None
    assert summary["series_won"] is None
    assert summary["series"] is None
    assert "playoffs" not in summary["games_by_phase"]
    assert out["meta"]["coverage"]["playoffs"]["source"] is None
    assert out["meta"]["coverage"]["playoffs"]["consulted"] == list(
        PLAYOFF_TABLES)


def test_an_unanswerable_section_publishes_no_number_at_all():
    _require_warehouse()
    section = _brief_rows("ATL", "NOP", "2019-20")["season_series"]
    assert section["available"] is False
    assert section["summary"] is None
    assert section["games"] == []
    counts = {key: value for key, value in section.items()
              if isinstance(value, (int, float)) and not isinstance(value, bool)}
    assert counts == {}


def test_the_published_reason_is_the_refusal_the_series_tool_gives():
    _require_warehouse()
    out = _series("ATL", "NOP", "2019-20")
    assert out["ok"] is False
    section = _brief_rows("ATL", "NOP", "2019-20")["season_series"]
    assert section["reason"] == out["error"]
    assert "2019-20" in section["reason"]


def test_a_covered_season_publishes_its_meetings_not_a_refusal():
    _require_warehouse()
    section = _brief_rows("CLE", "MIL", "2024-25")["season_series"]
    assert section["available"] is True
    assert "reason" not in section
    assert section["summary"]["games"] == 4
    assert json.dumps(section).count("silver_hist_gamelogs") >= 0


def test_the_brief_never_publishes_a_count_the_tables_cannot_support():
    _require_warehouse()
    for a, b, season, meetings in [
        ("CLE", "MIL", "2024-25", 4),
        ("MIN", "DAL", "2024-25", 3),
        ("CLE", "MIL", "2009-10", 4),
    ]:
        section = _brief_rows(a, b, season)["season_series"]
        assert section["available"] is True, (a, b, season)
        assert section["summary"]["games"] == meetings, (a, b, season)
        assert section["summary"]["games_by_phase"] == {
            "regular season": meetings}, (a, b, season)