import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.sources.hist_salaries import parse_rows, team_abbr

PLAYERS = "\n".join([
    "player_id,name",
    "dumardi01,Joe Dumars",
    "jordami01,Michael Jordan",
    "curryst01,Stephen Curry",
    "",
])

SALARIES = "\n".join([
    "league,player_id,salary,season,season_end,season_start,team",
    "NBA,dumardi01,400000,1989-90,1990,1989,Detroit Pistons",
    "NBA,jordami01,30140000,1996-97,1997,1996,Chicago Bulls",
    "NBA,curryst01,12112359,2016-17,2017,2016,Golden State Warriors",
    "NBA,dumardi01,999999,2000-01,2001,2000,Seattle SuperSonics",
    "NBA,jordami01,100000,1990-91,1991,1990,Charlotte Hornets",
    "NBA,curryst01,100000,2015-16,2016,2015,Charlotte Hornets",
    "NBA,curryst01,100000,2010-11,2011,2010,Charlotte Bobcats",
    "NBA,dumardi01,100000,1984-85,1985,1984,Kansas City Kings",
    "ABA,dumardi01,100000,1975-76,1976,1975,Kentucky Colonels",
    "NBA,dumardi01,bad,1989-90,1990,1989,Detroit Pistons",
    "",
])


def test_parse_rows_filters_and_joins():
    rows = parse_rows(SALARIES, PLAYERS)
    assert len(rows) == 8
    by_season = {(r["SEASON"], r["PLAYER_ID"]): r for r in rows}
    assert by_season[("1996-97", "jordami01")]["SALARY"] == 30_140_000
    assert by_season[("1996-97", "jordami01")]["PLAYER_NAME"] == "Michael Jordan"
    assert by_season[("1989-90", "dumardi01")]["TEAM_ABBREVIATION"] == "DET"


def test_defunct_team_mappings():
    rows = parse_rows(SALARIES, PLAYERS)
    by_team = {r["TEAM_NAME"]: r["TEAM_ABBREVIATION"] for r in rows}
    assert by_team["Seattle SuperSonics"] == "SEA"
    assert by_team["Kansas City Kings"] == "KCK"
    assert by_team["Charlotte Bobcats"] == "CHO"


def test_charlotte_hornets_era_split():
    rows = parse_rows(SALARIES, PLAYERS)
    charlotte = {r["SEASON_YEAR"]: r["TEAM_ABBREVIATION"]
                 for r in rows if r["TEAM_NAME"] == "Charlotte Hornets"}
    assert charlotte[1990] == "CHO"
    assert charlotte[2015] == "CHA"


def test_non_nba_and_bad_salary_dropped():
    rows = parse_rows(SALARIES, PLAYERS)
    assert all(r["SALARY"] != "bad" for r in rows)
    assert not any(r["SEASON"] == "1975-76" for r in rows)


def test_team_abbr_fallback():
    assert team_abbr("New Orleans/Oklahoma City Hornets", 2006) == "NOK"
    assert team_abbr("Washington Bullets", 1995) == "WSB"
    assert team_abbr("Nowhere Kings", 2000) is None
