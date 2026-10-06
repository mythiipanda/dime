import json
import re
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_bbref_awards as seed
from shared import store
from shared.sources import bbref_awards as src

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bbref_awards"

SEASON_ROWS_2023_24 = {
    "MVP": 9, "ROY": 6, "DPOY": 13, "6MOY": 12, "MIP": 14,
    "COY": 11, "ALL_NBA": 25, "ALL_DEFENSE": 34, "ALL_ROOKIE": 21,
}

def _page(year: int) -> str:
    return (FIXTURES / f"awards_{year}.html").read_text(encoding="utf-8")

def _index() -> str:
    return (FIXTURES / "awards_index.html").read_text(encoding="utf-8")

def _frame(year: int):
    return src.parse_season_page(_page(year), year)

def _drop_section(text: str, table_id: str) -> str:
    return re.sub(r'<div id="all_%s".*?(?=<div id="all_|\Z)' % table_id, "",
                  text, flags=re.S)

def _rename_stat(text: str, stat: str) -> str:
    return text.replace('data-stat="%s"' % stat, 'data-stat="retired_%s"' % stat)

def _scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "awards.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()

def test_full_season_parses_every_award_section():
    frame = _frame(2024)
    assert frame.height == sum(SEASON_ROWS_2023_24.values())
    counts = frame.group_by("AWARD").len().sort("AWARD").to_dicts()
    assert {row["AWARD"]: row["len"] for row in counts} == SEASON_ROWS_2023_24

def test_parsed_frame_carries_the_declared_schema():
    frame = _frame(2024)
    assert frame.schema == src.SCHEMA
    assert frame.columns == src.COLUMNS

def test_every_recorded_season_parses():
    for year, season in ((1977, "1976-77"), (1998, "1997-98"), (2015, "2014-15"),
                         (2024, "2023-24"), (2026, "2025-26")):
        frame = _frame(year)
        assert frame.height > 0, year
        assert set(frame["SEASON"]) == {season}, year

def test_season_and_source_url_on_every_row():
    frame = _frame(2024)
    assert set(frame["SEASON"]) == {"2023-24"}
    url = "https://www.basketball-reference.com/awards/awards_2024.html"
    assert set(frame["SOURCE_URL"]) == {url}

def test_comment_only_award_tables_are_parsed_not_skipped():
    frame = _frame(2024)
    parsed = set(frame["AWARD"].to_list())
    assert {"DPOY", "6MOY", "MIP", "COY"} <= parsed
    assert frame.filter(pl.col("AWARD") == "DPOY").height == SEASON_ROWS_2023_24["DPOY"]

def test_known_values_1997_98():
    frame = _frame(1998)
    assert frame["SEASON"].unique().to_list() == ["1997-98"]
    mvp = frame.filter((pl.col("AWARD") == "MVP") & (pl.col("RANK") == 1)).row(0, named=True)
    assert mvp["PLAYER"] == "Michael Jordan"
    assert mvp["TEAM"] == "CHI"
    assert mvp["AGE"] == 34
    assert mvp["POINTS_WON"] == 1084
    assert mvp["POINTS_MAX"] == 1160
    assert mvp["AWARD_SHARE"] == pytest.approx(0.934)
    assert mvp["VOTES_FIRST"] == 92
    roy = frame.filter((pl.col("AWARD") == "ROY") & (pl.col("RANK") == 1)).row(0, named=True)
    assert roy["PLAYER"] == "Tim Duncan"
    assert roy["POINTS_WON"] == 113
    assert roy["AWARD_SHARE"] == pytest.approx(0.974)
    dpoy = frame.filter((pl.col("AWARD") == "DPOY") & (pl.col("RANK") == 1)).row(0, named=True)
    assert dpoy["PLAYER"] == "Dikembe Mutombo"
    assert dpoy["AWARD_SHARE"] == pytest.approx(0.336)
    coach = frame.filter((pl.col("AWARD") == "COY") & (pl.col("RANK") == 1)).row(0, named=True)
    assert coach["COACH"] == "Larry Bird"
    assert coach["TEAM"] == "IND"

def test_known_values_2014_15():
    frame = _frame(2015)
    assert frame["SEASON"].unique().to_list() == ["2014-15"]
    mvp = frame.filter((pl.col("AWARD") == "MVP") & (pl.col("RANK") == 1)).row(0, named=True)
    assert mvp["PLAYER"] == "Stephen Curry"
    assert mvp["TEAM"] == "GSW"
    assert mvp["AGE"] == 26
    assert mvp["POINTS_WON"] == 1198
    assert mvp["POINTS_MAX"] == 1300
    assert mvp["AWARD_SHARE"] == pytest.approx(0.922)
    assert mvp["VOTES_FIRST"] == 100
    sixth = frame.filter((pl.col("AWARD") == "6MOY") & (pl.col("RANK") == 2)).row(0, named=True)
    assert sixth["PLAYER"] == "Isaiah Thomas"
    assert sixth["TEAM"] == "TOT"
    assert sixth["AWARD_SHARE"] == pytest.approx(0.498)
    roy = frame.filter((pl.col("AWARD") == "ROY") & (pl.col("RANK") == 2)).row(0, named=True)
    assert roy["PLAYER"] == "Nikola Mirotić"
    assert roy["POINTS_MAX"] == 650

def test_known_values_2025_26():
    frame = _frame(2026)
    mvp = frame.filter((pl.col("AWARD") == "MVP") & (pl.col("RANK") == 1)).row(0, named=True)
    assert mvp["PLAYER"] == "Shai Gilgeous-Alexander"
    assert mvp["TEAM"] == "OKC"
    assert mvp["POINTS_WON"] == 939
    assert mvp["POINTS_MAX"] == 1000
    assert mvp["AWARD_SHARE"] == pytest.approx(0.939)
    dpoy = frame.filter((pl.col("AWARD") == "DPOY") & (pl.col("RANK") == 1)).row(0, named=True)
    assert dpoy["PLAYER"] == "Victor Wembanyama"
    assert dpoy["AWARD_SHARE"] == pytest.approx(1.0)

def test_coach_rows_name_a_coach_and_carry_no_player():
    frame = _frame(2024)
    coy = frame.filter(pl.col("AWARD") == "COY")
    assert coy.height == SEASON_ROWS_2023_24["COY"]
    assert coy["COACH"].is_not_null().all()
    assert coy["PLAYER"].is_null().all()
    assert coy["AGE"].is_null().all()
    first = coy.filter(pl.col("RANK") == 1).row(0, named=True)
    assert first["COACH"] == "Mark Daigneault"
    assert first["TEAM"] == "OKC"
    assert first["POINTS_WON"] == 473
    assert first["AWARD_SHARE"] == pytest.approx(0.956)

def test_player_awards_carry_no_coach():
    frame = _frame(2024)
    players = frame.filter(pl.col("AWARD") != "COY")
    assert players["COACH"].is_null().all()
    assert players["PLAYER"].is_not_null().all()

def test_all_nba_rank_is_the_team_number():
    frame = _frame(2024)
    all_nba = frame.filter(pl.col("AWARD") == "ALL_NBA")
    assert sorted(all_nba["RANK"].drop_nulls().unique().to_list()) == [1, 2, 3]
    assert sorted(all_nba["RANK_LABEL"].unique().to_list()) == ["1T", "2T", "3T", "ORV"]
    first = all_nba.filter(pl.col("RANK") == 1)
    assert first.height == 5
    assert first["VOTES_FIRST"].max() == 99
    assert first["VOTES_SECOND"].max() == 34
    assert first["VOTES_THIRD"].max() == 0
    assert (first["VOTES_FIRST"] + first["VOTES_SECOND"] + first["VOTES_THIRD"]).max() == 99

def test_all_nba_team_code_change_still_maps_to_rank():
    for year, expected_first in ((2015, 129), (2024, 99)):
        frame = _frame(year)
        first = frame.filter((pl.col("AWARD") == "ALL_NBA") & (pl.col("RANK") == 1))
        assert first.height == 5, year
        assert first["VOTES_FIRST"].max() == expected_first, year

def test_other_votes_rows_are_kept_without_a_team_rank():
    frame = _frame(2024)
    orv = frame.filter(pl.col("RANK_LABEL") == "ORV")
    assert orv.height > 0
    assert set(orv["AWARD"].to_list()) == {"ALL_NBA", "ALL_DEFENSE", "ALL_ROOKIE"}
    assert orv["RANK"].is_null().all()
    assert orv["PLAYER"].is_not_null().all()
    assert orv["POINTS_WON"].is_not_null().all()

def test_tied_ranks_collapse_to_one_ordinal():
    frame = _frame(2024)
    tied = frame.filter((pl.col("AWARD") == "DPOY") & (pl.col("RANK_LABEL") == "10T"))
    assert tied.height == 4
    assert set(tied["RANK"].to_list()) == {10}
    assert set(tied["POINTS_WON"].to_list()) == {1}

def test_all_defense_carries_no_ballot_vote_counts():
    frame = _frame(2024)
    defense = frame.filter(pl.col("AWARD") == "ALL_DEFENSE")
    assert defense.height == SEASON_ROWS_2023_24["ALL_DEFENSE"]
    assert defense["VOTES_FIRST"].is_null().all()
    assert defense["VOTES_SECOND"].is_null().all()
    assert defense["VOTES_THIRD"].is_null().all()
    first = defense.filter(pl.col("RANK") == 1).row(0, named=True)
    assert first["RANK_LABEL"] == "1st"
    assert first["PLAYER"] == "Anthony Davis"
    assert first["POINTS_WON"] == 151
    assert first["AWARD_SHARE"] == pytest.approx(0.763)

def test_non_ascii_player_names_survive_parsing():
    frame = _frame(2024)
    names = set(frame["PLAYER"].drop_nulls().to_list())
    assert {"Nikola Jokić", "Luka Dončić"} <= names

def test_all_rookie_records_two_team_vote_columns():
    frame = _frame(2024)
    rookie = frame.filter(pl.col("AWARD") == "ALL_ROOKIE")
    assert rookie["VOTES_FIRST"].is_not_null().all()
    assert rookie["VOTES_SECOND"].is_not_null().all()
    assert rookie["VOTES_THIRD"].is_null().all()

def test_awards_predate_their_invention_and_are_absent_not_faked():
    frame = _frame(1977)
    assert set(frame["SEASON"]) == {"1976-77"}
    assert set(frame["AWARD"].to_list()) == {
        "MVP", "ROY", "COY", "ALL_NBA", "ALL_DEFENSE", "ALL_ROOKIE"}

def test_missing_required_section_raises_naming_season_and_award():
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page(_drop_section(_page(2024), "mvp"), 2024)
    message = str(excinfo.value)
    assert "2023-24" in message
    assert "MVP" in message

def test_missing_optional_ballot_raises_naming_the_column():
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page(_rename_stat(_page(2024), "award_share"), 2024)
    message = str(excinfo.value)
    assert "award_share" in message
    assert "2023-24" in message

def test_award_absent_before_it_existed_is_not_an_error():
    frame = _frame(1977)
    assert "6MOY" not in set(frame["AWARD"].to_list())

def test_page_with_no_award_sections_raises_naming_the_season():
    page = "<html><body><h1>2023-24 NBA Awards Voting</h1></body></html>"
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page(page, 2024)
    assert "2023-24" in str(excinfo.value)

def test_non_html_page_raises_rather_than_writing_nothing():
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page("<html><body>rate limited</body></html>", 2024)
    assert "2023-24" in str(excinfo.value)

def test_page_season_disagreeing_with_url_year_raises():
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page(_page(2024), 2023)
    assert "2023-24" in str(excinfo.value)

def test_season_label_and_year_round_trip():
    assert src.season_label(2024) == "2023-24"
    assert src.season_label(1977) == "1976-77"
    assert src.season_label(2000) == "1999-00"
    assert src.season_year("2023-24") == 2024
    assert src.season_url(2024) == (
        "https://www.basketball-reference.com/awards/awards_2024.html")

def test_index_page_lists_the_published_season_pages():
    years = src.published_years(_index())
    assert min(years) == 1956
    assert max(years) == 2026
    assert {1977, 1998, 2015, 2024} <= set(years)

def test_index_page_without_season_links_raises():
    with pytest.raises(src.AwardsPageError):
        src.published_years("<html><body>nothing here</body></html>")

def test_fetch_season_asks_transport_for_the_season_page():
    asked: list[str] = []

    def transport(url: str) -> str:
        asked.append(url)
        return _page(2024)

    result = src.fetch_season(2024, transport=transport, min_interval_s=0.0)
    assert asked == [src.season_url(2024)]
    assert result.ok is True
    assert result.meta.source == "basketball-reference"
    assert result.meta.season == "2023-24"
    assert result.frame.height == sum(SEASON_ROWS_2023_24.values())

def test_fetch_season_retries_a_throttled_page_then_succeeds():
    calls: list[str] = []

    def transport(url: str) -> str:
        calls.append(url)
        if len(calls) < 3:
            raise src.Throttled(url)
        return _page(2024)

    result = src.fetch_season(2024, transport=transport, min_interval_s=0.0,
                              backoff_s=0.0)
    assert len(calls) == 3
    assert result.frame.height == sum(SEASON_ROWS_2023_24.values())

def test_fetch_season_raises_when_every_attempt_is_throttled():
    def transport(url: str) -> str:
        raise src.Throttled(url)

    with pytest.raises(src.Throttled):
        src.fetch_season(2024, transport=transport, min_interval_s=0.0,
                         backoff_s=0.0, attempts=2)

def test_fetch_season_does_not_retry_a_broken_page():
    calls: list[str] = []

    def transport(url: str) -> str:
        calls.append(url)
        return "<html><body/></html>"

    with pytest.raises(src.AwardsPageError):
        src.fetch_season(2024, transport=transport, min_interval_s=0.0,
                         backoff_s=0.0, attempts=4)
    assert len(calls) == 1

def test_default_pacing_stays_under_the_source_request_limit():
    assert src.MIN_INTERVAL_S * src.REQUESTS_PER_MINUTE_LIMIT >= 60.0
    assert src.MIN_INTERVAL_S > 3.0

def test_transport_never_carries_credentials(monkeypatch):
    assert "cookie" not in {k.lower() for k in src.HEADERS}
    assert "authorization" not in {k.lower() for k in src.HEADERS}
    monkeypatch.setattr(src.requests, "get", lambda *a, **k: _Response(_page(2024)))
    assert "Nikola Jokić" in src.paced_transport(min_interval_s=0.0)(src.season_url(2024))

class _Response:
    def __init__(self, body: str, status_code: int = 200):
        self.content = body.encode("utf-8")
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

def test_paced_transport_turns_a_429_into_a_throttle(monkeypatch):
    monkeypatch.setattr(src.requests, "get",
                        lambda *a, **k: _Response("", status_code=429))
    with pytest.raises(src.Throttled):
        src.paced_transport(min_interval_s=0.0)(src.season_url(2024))

def test_seeder_writes_nothing_for_a_malformed_page(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")

    with pytest.raises(src.AwardsPageError):
        seed.seed_season("2023-24",
                         transport=lambda url: "<html><body>throttled</body></html>",
                         min_interval_s=0.0)
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert seed.TABLE not in tables

def test_seed_season_is_idempotent(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")

    def transport(url: str) -> str:
        return _page(2024)

    first = seed.seed_season("2023-24", transport=transport, min_interval_s=0.0,
                             winners=_winner_index())
    second = seed.seed_season("2023-24", transport=transport, min_interval_s=0.0,
                              winners=_winner_index())
    assert first == second == sum(SEASON_ROWS_2023_24.values())
    con = store.connect()
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {seed.TABLE}").fetchone()[0]
        provenance = con.execute(
            f"SELECT DISTINCT _season, _source, _entity FROM {seed.TABLE}").fetchall()
        stamps = con.execute(
            f"SELECT COUNT(DISTINCT _fetched_at) FROM {seed.TABLE}").fetchone()[0]
    finally:
        con.close()
    assert count == sum(SEASON_ROWS_2023_24.values())
    assert provenance == [("2023-24", "basketball-reference", "season:2023-24")]
    assert stamps == 1

def test_seeder_resumes_from_the_progress_file(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    progress = tmp_path / "progress.json"

    def transport(url: str) -> str:
        return _page(2024)

    seed.seed_season("2023-24", transport=transport, min_interval_s=0.0,
                     winners=_winner_index())
    seed.mark_done(progress, "2023-24")
    seed.mark_failed(progress, "2024-25", "rate limited")
    assert seed.pending_seasons(["2023-24", "2024-25"], progress) == ["2024-25"]
    con = store.connect()
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {seed.TABLE}").fetchone()[0]
    finally:
        con.close()
    assert count == sum(SEASON_ROWS_2023_24.values())

def test_progress_file_names_the_failing_season(tmp_path):
    progress = tmp_path / "progress.json"
    seed.mark_failed(progress, "2023-24", "no award tables on page")
    state = json.loads(progress.read_text())
    assert state["failed"]["2023-24"] == "no award tables on page"
    assert state["done"] == []
    assert seed.pending_seasons(["2023-24"], progress) == ["2023-24"]

def _run_main(tmp_path, monkeypatch, pages: dict, argv: list[str]) -> int:
    _scratch(tmp_path, monkeypatch)
    seasons = [src.season_label(year) for year in sorted(pages)]
    _write_spine(seasons)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    monkeypatch.setattr(src, "paced_transport",
                        lambda min_interval_s=0.0: _page_router(pages))
    monkeypatch.setattr(src, "fetch_index", lambda transport=None: sorted(pages))
    monkeypatch.setattr(src, "BACKOFF_S", 0.0)
    return seed.main(["seed_bbref_awards.py",
                      "--progress", str(tmp_path / "progress.json")] + argv)

def _write_spine(seasons: list[str]) -> None:
    import duckdb

    con = duckdb.connect(str(store.DB_PATH))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS silver_spine (_season VARCHAR)")
        con.execute("DELETE FROM silver_spine")
        con.executemany("INSERT INTO silver_spine VALUES (?)",
                        [(season,) for season in seasons])
    finally:
        con.close()
    store.warehouse_tables_cache_clear()

def _winner_fixture_for(url: str) -> str:
    for page in src.WINNER_PAGES:
        if page.url == url:
            return WINNER_FIXTURES[page.award]
    raise AssertionError(f"no recorded fixture for {url}")

def _page_router(pages: dict):
    def transport(url: str) -> str:
        if url in src.WINNER_URLS:
            return (FIXTURES / _winner_fixture_for(url)).read_text(encoding="utf-8")
        year = int(url.rsplit("_", 1)[-1].split(".")[0])
        if year not in pages:
            raise RuntimeError(f"404 for {url}")
        return (FIXTURES / pages[year]).read_text(encoding="utf-8")

    return transport

def test_main_lands_every_season_it_plans_and_reports_success(
        tmp_path, monkeypatch):
    pages = {2024: "awards_2024.html", 2026: "awards_2026.html"}
    assert _run_main(tmp_path, monkeypatch, pages, []) == 0
    con = store.connect()
    try:
        landed = con.execute(
            f"SELECT _season, COUNT(*) FROM {seed.TABLE} GROUP BY 1 ORDER BY 1"
        ).fetchall()
    finally:
        con.close()
    assert landed == [("2023-24", 145), ("2025-26", 135)]

def test_main_second_run_fetches_nothing_and_returns_zero(tmp_path, monkeypatch):
    pages = {2024: "awards_2024.html"}
    assert _run_main(tmp_path, monkeypatch, pages, []) == 0
    assert _run_main(tmp_path, monkeypatch, pages, []) == 0
    con = store.connect()
    try:
        count = con.execute(f"SELECT COUNT(*) FROM {seed.TABLE}").fetchone()[0]
    finally:
        con.close()
    assert count == 145

def test_main_stops_after_consecutive_failures_and_names_them(
        tmp_path, monkeypatch):
    stale = {2023: "awards_1998.html", 2024: "awards_1998.html",
             2025: "awards_1998.html", 2026: "awards_1998.html"}
    assert _run_main(tmp_path, monkeypatch, stale, []) == 1
    state = json.loads((tmp_path / "progress.json").read_text())
    assert sorted(state["failed"]) == ["2022-23", "2023-24", "2024-25"]
    assert state["done"] == []
    log = (tmp_path / "seed.log").read_text()
    assert "stopping after 3 consecutive failures" in log
    assert "2025-26" not in state["failed"]
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert seed.TABLE not in tables

def test_main_respects_the_seasons_flag(tmp_path, monkeypatch):
    assert _run_main(tmp_path, monkeypatch,
                     {2024: "awards_2024.html", 2026: "awards_2026.html"},
                     ["--seasons", "2025-26"]) == 0
    con = store.connect()
    try:
        landed = con.execute(
            f"SELECT DISTINCT _season FROM {seed.TABLE}").fetchall()
    finally:
        con.close()
    assert landed == [("2025-26",)]

def test_plan_targets_warehouse_seasons_that_bbref_publishes(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    _write_spine(["2019-20", "2020-21", "2021-22"])
    assert seed.plan_seasons(published=[2020, 2021, 2022]) == [
        "2019-20", "2020-21", "2021-22"]
    assert seed.plan_seasons(published=[2020, 2021]) == ["2019-20", "2020-21"]

def test_plan_drops_seasons_bbref_does_not_publish_yet(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    _write_spine(["2025-26", "2026-27"])
    assert seed.plan_seasons(published=[2026]) == ["2025-26"]

def test_plan_slices_by_from_and_to_season(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    _write_spine(["2018-19", "2019-20", "2020-21", "2021-22"])
    assert seed.plan_seasons([2019, 2020, 2021, 2022], from_season="2019-20",
                             to_season="2020-21") == ["2019-20", "2020-21"]

def test_plan_on_a_warehouse_with_no_season_column_raises(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    with pytest.raises(seed.SeasonPlanError):
        seed.plan_seasons(published=[2024])

def _write_award_tool_fixture(path, season: str = "2023-24") -> None:
    import duckdb

    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE TABLE silver_boxscores (GAME_ID VARCHAR, _season VARCHAR)")
        con.executemany("INSERT INTO silver_boxscores VALUES (?, ?)",
                        [(f"002230000{i}", season) for i in range(6)])
        con.execute("CREATE TABLE silver_leaders_pts (PLAYER_ID INTEGER, "
                    "PLAYER VARCHAR, TEAM VARCHAR, TEAM_ID INTEGER, GP INTEGER, "
                    "MIN DOUBLE, PTS DOUBLE, REB DOUBLE, DREB DOUBLE, AST DOUBLE, "
                    "STL DOUBLE, BLK DOUBLE, EFF DOUBLE, _season VARCHAR)")
        con.execute("CREATE TABLE silver_advanced (PLAYER_ID INTEGER, AGE DOUBLE, "
                    "TS_PCT DOUBLE, NET_RATING DOUBLE, DEF_RATING DOUBLE, "
                    "_season VARCHAR)")
        con.execute("CREATE TABLE silver_standings (TeamID INTEGER, WINS INTEGER, "
                    "LOSSES INTEGER, OppPointsPG DOUBLE, _season VARCHAR)")
        pool = [
            (2544, "Nikola Jokic", "DEN", 15, 79, 3083, 26.4, 12.4, 10.4, 9.0, 1.4, 0.9, 29.0, 29.0, .579, 12.4, 113.7),
            (201939, "Shai Gilgeous-Alexander", "OKC", 10, 75, 2882, 32.7, 5.5, 4.6, 6.2, 2.0, 0.5, 28.4, 25.0, .526, 4.6, 119.1),
            (1628363, "Luka Doncic", "DAL", 13, 70, 2704, 33.9, 9.2, 7.5, 9.8, 1.4, 0.5, 32.7, 24.0, .507, 3.4, 114.0),
            (203076, "Giannis Antetokounmpo", "MIL", 17, 63, 2270, 30.4, 11.5, 9.4, 6.5, 1.2, 1.1, 28.8, 29.0, .606, 8.2, 118.0),
            (1628383, "Jayson Tatum", "BOS", 2, 78, 2894, 26.9, 8.1, 6.6, 4.9, 1.0, 0.4, 27.0, 26.0, .471, 5.0, 110.2),
            (203110, "Anthony Davis", "LAL", 14, 76, 2700, 24.7, 12.1, 10.3, 3.6, 1.0, 1.9, 25.5, 31.0, .554, 5.5, 115.5),
        ]
        for (pid, name, team, tid, gp, mins, pts, reb, dreb, ast, stl, blk, eff,
             age, ts, net, dft) in pool:
            con.execute(
                "INSERT INTO silver_leaders_pts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [pid, name, team, tid, gp, mins, pts, reb, dreb, ast, stl, blk,
                 eff, season])
            con.execute("INSERT INTO silver_advanced VALUES (?,?,?,?,?,?)",
                        [pid, age, ts, net, dft, season])
        records = [(15, 57, 25, 113.8), (10, 55, 27, 114.6), (13, 50, 32, 114.9),
                   (17, 49, 33, 115.3), (2, 24, 58, 117.1), (14, 19, 63, 117.6)]
        con.executemany("INSERT INTO silver_standings VALUES (?,?,?,?,?)",
                        [(tid, wins, losses, opp, season)
                         for tid, wins, losses, opp in records])
    finally:
        con.close()
    from shared.tools import _core

    _core.last_completed_season_cache_clear()
    store.warehouse_tables_cache_clear()

def test_landed_table_answers_a_vote_share_question_the_award_tool_refuses(
        tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    _write_award_tool_fixture(store.DB_PATH)
    seed.seed_season("2023-24", transport=lambda url: _page(2024),
                     min_interval_s=0.0, winners=_winner_index())
    from shared.tools.awards import get_award_race

    race = get_award_race.invoke({"award": "MVP", "season": "2023-24"})
    assert race["ok"] is True, race
    assert "not points, probability, vote share, or an official award result" in (
        race["meta"]["score_definition"])
    assert "score_unit" in race["meta"]

    con = store.connect()
    try:
        rows = con.execute(
            f"""SELECT PLAYER, AWARD_SHARE, POINTS_WON, POINTS_MAX, VOTES_FIRST
            FROM {seed.TABLE}
            WHERE AWARD = 'MVP' AND _season = '2023-24' AND RANK = 1"""
        ).fetchall()
        cited = con.execute(
            f"""SELECT PLAYER, AWARD_SHARE, _source, _fetched_at, SOURCE_URL
            FROM {seed.TABLE}
            WHERE AWARD = '6MOY' AND _season = '2023-24' AND RANK = 1"""
        ).fetchall()
    finally:
        con.close()
    assert rows == [("Nikola Jokić", 0.935, 926, 990, 79)]
    player, share, source, fetched_at, url = cited[0]
    assert player == "Naz Reid"
    assert share == pytest.approx(0.711)
    assert source == "basketball-reference"
    assert fetched_at
    assert url.endswith("/awards/awards_2024.html")

def test_landed_awards_table_answers_a_season_no_award_ballot_touches(tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    seed.seed_season("1997-98", transport=lambda url: _page(1998),
                     min_interval_s=0.0, winners=_winner_index())
    con = store.connect()
    try:
        rows = con.execute(
            f"""SELECT PLAYER, AWARD_SHARE, TEAM, VOTES_FIRST
            FROM {seed.TABLE}
            WHERE AWARD = 'ALL_NBA' AND _season = '1997-98' AND RANK = 1
            ORDER BY VOTES_FIRST DESC"""
        ).fetchall()
    finally:
        con.close()
    assert {row[0]: row[1:] for row in rows} == {
        "Karl Malone": (1.0, "UTA", 116),
        "Michael Jordan": (1.0, "CHI", 116),
        "Gary Payton": (0.967, "SEA", 108),
        "Shaquille O'Neal": (0.938, "LAL", 103),
        "Tim Duncan": (0.638, "SAS", 45)}

WINNER_FIXTURES = {
    "MVP": "winners_mvp.html",
    "ROY": "winners_roy.html",
    "DPOY": "winners_dpoy.html",
    "6MOY": "winners_smoy.html",
    "MIP": "winners_mip.html",
    "COY": "winners_coy.html",
}

RECORDED_SEASONS = ((1977, "1976-77"), (1981, "1980-81"), (1998, "1997-98"),
                    (2004, "2003-04"), (2015, "2014-15"), (2024, "2023-24"),
                    (2026, "2025-26"))

CONTESTED_RANK_ONE = (
    ("1976-77", "MVP", "Kareem Abdul-Jabbar", 159, 247, 0.644, 159),
    ("1976-77", "ROY", "Adrian Dantley", 44, 66, 0.667, 44),
    ("1976-77", "COY", "Tom Nissalke", 26, 59, 0.441, 26),
    ("1980-81", "MVP", "Julius Erving", 454, 690, 0.658, 28),
    ("1980-81", "ROY", "Darrell Griffith", 19, 69, 0.275, 19),
    ("1980-81", "COY", "Jack McKinney", 27, 69, 0.391, 27),
    ("1997-98", "MVP", "Michael Jordan", 1084, 1160, 0.934, 92),
    ("1997-98", "ROY", "Tim Duncan", 113, 116, 0.974, 113),
    ("1997-98", "DPOY", "Dikembe Mutombo", 39, 116, 0.336, 39),
    ("1997-98", "6MOY", "Danny Manning", 57, 116, 0.491, 57),
    ("1997-98", "MIP", "Alan Henderson", 33, 116, 0.284, 33),
    ("1997-98", "COY", "Larry Bird", 50, 116, 0.431, 50),
    ("2003-04", "MVP", "Kevin Garnett", 1219, 1230, 0.991, 120),
    ("2003-04", "ROY", "LeBron James", 508, 590, 0.861, 78),
    ("2003-04", "DPOY", "Metta World Peace", 476, 605, 0.787, 80),
    ("2003-04", "6MOY", "Antawn Jamison", 338, 600, 0.563, 43),
    ("2003-04", "MIP", "Zach Randolph", 379, 605, 0.626, 59),
    ("2003-04", "COY", "Hubie Brown", 466, 610, 0.764, 62),
    ("2014-15", "MVP", "Stephen Curry", 1198, 1300, 0.922, 100),
    ("2014-15", "ROY", "Andrew Wiggins", 604, 650, 0.929, 110),
    ("2014-15", "DPOY", "Kawhi Leonard", 333, 645, 0.516, 37),
    ("2014-15", "6MOY", "Lou Williams", 502, 650, 0.772, 78),
    ("2014-15", "MIP", "Jimmy Butler", 535, 645, 0.829, 92),
    ("2014-15", "COY", "Mike Budenholzer", 513, 650, 0.789, 67),
    ("2023-24", "MVP", "Nikola Jokić", 926, 990, 0.935, 79),
    ("2023-24", "ROY", "Victor Wembanyama", 495, 495, 1.0, 99),
    ("2023-24", "DPOY", "Rudy Gobert", 433, 495, 0.875, 72),
    ("2023-24", "6MOY", "Naz Reid", 352, 495, 0.711, 45),
    ("2023-24", "MIP", "Tyrese Maxey", 319, 495, 0.644, 51),
    ("2023-24", "COY", "Mark Daigneault", 473, 495, 0.956, 89),
    ("2025-26", "MVP", "Shai Gilgeous-Alexander", 939, 1000, 0.939, 83),
    ("2025-26", "ROY", "Cooper Flagg", 412, 500, 0.824, 56),
    ("2025-26", "DPOY", "Victor Wembanyama", 500, 500, 1.0, 100),
    ("2025-26", "6MOY", "Keldon Johnson", 404, 500, 0.808, 63),
    ("2025-26", "MIP", "Nickeil Alexander-Walker", 396, 500, 0.792, 66),
    ("2025-26", "COY", "Joe Mazzulla", 392, 500, 0.784, 62),
)

IDENTITY_STATS = ("player", "coach", "age", "team_id")

def _winner_index() -> dict:
    return src.load_winner_index({
        award: (FIXTURES / name).read_text(encoding="utf-8")
        for award, name in WINNER_FIXTURES.items()})

def _offset_identities(text: str, label: str, table_ids: tuple[str, ...]) -> str:
    from lxml import etree

    doc = src._document(text, label)
    tables = src._award_tables(doc)
    for table_id in table_ids:
        rows = tables[table_id].xpath("./tbody/tr")
        identity = [[cell for cell in row.xpath("./th|./td")
                     if cell.get("data-stat") in IDENTITY_STATS] for row in rows]
        carried = [[(cell.text, [etree.tostring(child, encoding="unicode")
                                 for child in cell])
                    for cell in cells] for cells in identity]
        for index, cells in enumerate(identity):
            donor = carried[(index + 1) % len(rows)]
            for cell, (content, children) in zip(cells, donor):
                for child in list(cell):
                    cell.remove(child)
                cell.text = content
                for child in children:
                    cell.append(etree.fromstring(child))
    return etree.tostring(doc, encoding="unicode")

def test_winner_index_names_one_winner_per_published_season():
    winners = _winner_index()
    assert set(winners) == set(WINNER_FIXTURES)
    assert winners["MVP"]["1980-81"] == ("Julius Erving",)
    assert winners["MVP"]["2003-04"] == ("Kevin Garnett",)
    assert winners["COY"]["2003-04"] == ("Hubie Brown",)
    assert winners["6MOY"]["2023-24"] == ("Naz Reid",)
    assert len(winners["MVP"]) >= 70
    assert all(re.fullmatch(r"\d{4}-\d{2}", season)
               for season in winners["ROY"])

def test_a_tied_award_keeps_both_of_the_source_winners():
    tied = _winner_index()["ROY"]["1999-00"]
    assert tied == ("Steve Francis", "Elton Brand")

def test_winner_index_page_without_the_winners_table_raises():
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.winner_index('<html><body><h1>x</h1><table id="other">'
                         '<tbody><tr><td data-stat="season">2003-04</td>'
                         '</tr></tbody></table></body></html>', "MVP")
    assert "MVP" in str(excinfo.value)
    assert "mvp.html" in str(excinfo.value)

def test_every_recorded_season_matches_the_source_winner_index():
    winners = _winner_index()
    for year, season in RECORDED_SEASONS:
        frame = src.parse_season_page(_page(year), year)
        src.verify_ballots(frame, winners)

def test_every_recorded_contested_award_names_its_real_winner():
    for season, award, winner, won, top, share, firsts in CONTESTED_RANK_ONE:
        year = src.season_year(season)
        frame = src.parse_season_page(_page(year), year)
        row = frame.filter((pl.col("AWARD") == award)
                           & (pl.col("RANK") == 1)).row(0, named=True)
        assert (row["PLAYER"] or row["COACH"]) == winner, (season, award)
        assert row["POINTS_WON"] == won, (season, award)
        assert row["POINTS_MAX"] == top, (season, award)
        assert row["AWARD_SHARE"] == pytest.approx(share), (season, award)
        assert row["VOTES_FIRST"] == firsts, (season, award)

def test_the_seasons_reported_as_corrupt_publish_their_true_winner():
    frame = src.parse_season_page(_page(2004), 2004)
    garnett = frame.filter((pl.col("AWARD") == "MVP")
                           & (pl.col("RANK") == 1)).row(0, named=True)
    assert garnett["PLAYER"] == "Kevin Garnett"
    assert garnett["TEAM"] == "MIN"
    assert (garnett["POINTS_WON"], garnett["POINTS_MAX"],
            garnett["AWARD_SHARE"], garnett["VOTES_FIRST"]) == (
        1219, 1230, 0.991, 120)
    frame = src.parse_season_page(_page(1981), 1981)
    erving = frame.filter((pl.col("AWARD") == "MVP")
                         & (pl.col("RANK") == 1)).row(0, named=True)
    assert erving["PLAYER"] == "Julius Erving"
    assert erving["TEAM"] == "PHI"
    assert (erving["POINTS_WON"], erving["POINTS_MAX"],
            erving["AWARD_SHARE"], erving["VOTES_FIRST"]) == (
        454, 690, 0.658, 28)

def test_a_page_whose_identity_column_is_offset_from_its_ballot_is_refused():
    broken = _offset_identities(_page(2004), "2003-04",
                                ("mvp", "roy", "dpoy", "smoy", "mip", "coy"))
    frame = src.parse_season_page(broken, 2004)
    rank_one = frame.filter((pl.col("AWARD") == "MVP")
                            & (pl.col("RANK") == 1)).row(0, named=True)
    assert rank_one["PLAYER"] == "Tim Duncan"
    assert rank_one["POINTS_WON"] == 1219
    assert rank_one["VOTES_FIRST"] == 120
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(frame, _winner_index())
    message = str(excinfo.value)
    assert "2003-04" in message
    assert "MVP" in message
    assert "Kevin Garnett" in message
    assert "Tim Duncan" in message

def test_a_season_the_winner_index_does_not_cover_is_refused():
    frame = src.parse_season_page(_page(2004), 2004)
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(frame, {"MVP": {"1999-00": "Shaquille O'Neal"}})
    assert "2003-04" in str(excinfo.value)

def test_a_ballot_whose_points_rise_with_rank_is_refused():
    rank_one = (pl.col("AWARD") == "MVP") & (pl.col("RANK") == 1)
    demoted = src.parse_season_page(_page(2004), 2004).with_columns(
        pl.when(rank_one).then(pl.lit(100, dtype=pl.Int64))
        .otherwise(pl.col("POINTS_WON")).alias("POINTS_WON"),
        pl.when(rank_one).then(pl.lit(round(100 / 1230, 3)))
        .otherwise(pl.col("AWARD_SHARE")).alias("AWARD_SHARE"))
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(demoted, _winner_index())
    message = str(excinfo.value)
    assert "MVP" in message
    assert "716" in message and "100" in message

def test_a_ballot_whose_share_disagrees_with_its_points_is_refused():
    frame = src.parse_season_page(_page(2004), 2004)
    doctored = frame.with_columns(
        pl.when(pl.col("AWARD") == "MVP").then(0.5)
        .otherwise(pl.col("AWARD_SHARE")).alias("AWARD_SHARE"))
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(doctored, _winner_index())
    assert "0.5" in str(excinfo.value) or "share" in str(excinfo.value).lower()

def test_a_ballot_whose_first_place_votes_exceed_the_voter_count_is_refused():
    frame = src.parse_season_page(_page(2004), 2004)
    doctored = frame.with_columns(
        pl.when(pl.col("AWARD") == "MVP").then(pl.lit(9000, dtype=pl.Int64))
        .otherwise(pl.col("VOTES_FIRST")).alias("VOTES_FIRST"))
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(doctored, _winner_index())
    assert "first" in str(excinfo.value).lower()

def test_a_ballot_whose_rows_disagree_about_the_voter_count_is_refused():
    frame = src.parse_season_page(_page(2004), 2004)
    doctored = frame.with_columns(
        pl.when((pl.col("AWARD") == "MVP") & (pl.col("RANK") == 1))
        .then(pl.lit(999, dtype=pl.Int64))
        .otherwise(pl.col("POINTS_MAX")).alias("POINTS_MAX"))
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(doctored, _winner_index())
    assert "999" in str(excinfo.value)

def _second_row_claims_rank_one(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when((pl.col("AWARD") == "MVP") & (pl.col("RANK") == 2))
        .then(pl.lit(1, dtype=pl.Int64)).otherwise(pl.col("RANK")).alias("RANK"))

def test_a_second_row_claiming_rank_1_is_refused_unless_the_source_published_a_tie():
    doctored = _second_row_claims_rank_one(
        src.parse_season_page(_page(2004), 2004))
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.verify_ballots(doctored, _winner_index())
    message = str(excinfo.value)
    assert "Tim Duncan" in message
    assert "Kevin Garnett" in message

def test_a_source_published_tie_admits_every_joined_winner():
    doctored = _second_row_claims_rank_one(
        src.parse_season_page(_page(2004), 2004))
    winners = _winner_index()
    winners["MVP"] = dict(winners["MVP"],
                          **{"2003-04": ("Kevin Garnett", "Tim Duncan")})
    src.verify_ballots(doctored, winners)

def test_team_ballots_are_not_ranked_by_points_they_earned():
    frame = src.parse_season_page(_page(2024), 2024)
    all_nba = frame.filter(pl.col("AWARD") == "ALL_NBA")
    assert all_nba.filter(pl.col("RANK") == 1)["POINTS_WON"].to_list() != sorted(
        all_nba.filter(pl.col("RANK") == 1)["POINTS_WON"].to_list(), reverse=True)
    src.verify_ballots(frame, _winner_index())

def test_a_row_with_two_cells_for_one_stat_is_refused():
    doubled = _page(2004).replace(
        '<td class="left " data-append-csv="garneke01" data-stat="player"',
        '<td class="left " data-stat="player">Kevin Garnett</td>'
        '<td class="left " data-append-csv="garneke01" data-stat="player"', 1)
    assert doubled != _page(2004)
    with pytest.raises(src.AwardsPageError) as excinfo:
        src.parse_season_page(doubled, 2004)
    assert "player" in str(excinfo.value)

def test_seeder_writes_nothing_when_the_winner_index_names_someone_else(
        tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    wrong = _winner_index()
    wrong["MVP"] = dict(wrong["MVP"], **{"2023-24": ("Joel Embiid",)})
    with pytest.raises(src.AwardsPageError) as excinfo:
        seed.seed_season("2023-24", transport=lambda url: _page(2024),
                         min_interval_s=0.0, winners=wrong)
    assert "Joel Embiid" in str(excinfo.value)
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert seed.TABLE not in tables
    state = json.loads((tmp_path / "progress.json").read_text()) \
        if (tmp_path / "progress.json").exists() else {"done": [], "failed": {}}
    assert "2023-24" not in state["done"]

def test_a_direct_season_write_without_a_winner_index_is_logged_as_unverified(
        tmp_path, monkeypatch):
    _scratch(tmp_path, monkeypatch)
    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed.log")
    written = seed.seed_season("2023-24", transport=lambda url: _page(2024),
                               min_interval_s=0.0)
    assert written == sum(SEASON_ROWS_2023_24.values())
    assert "unverified" in (tmp_path / "seed.log").read_text()

def test_main_refuses_to_seed_when_the_winner_index_cannot_be_read(
        tmp_path, monkeypatch):
    pages = {2024: "awards_2024.html"}

    def broken_router(pages_map):
        router = _page_router(pages_map)

        def transport(url: str) -> str:
            if url in src.WINNER_URLS:
                raise RuntimeError(f"503 for {url}")
            return router(url)

        return transport

    monkeypatch.setattr(seed, "LOG_FILE", tmp_path / "seed2.log")
    monkeypatch.setattr(src, "paced_transport", lambda min_interval_s=0.0: broken_router(pages))
    monkeypatch.setattr(src, "fetch_index", lambda transport=None: sorted(pages))
    progress = tmp_path / "progress2.json"
    code = seed.main(["seed_bbref_awards.py", "--progress", str(progress)])
    assert code == 1
    assert "winner" in (tmp_path / "seed2.log").read_text()
    con = store.connect()
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert seed.TABLE not in tables
    assert not progress.exists()
