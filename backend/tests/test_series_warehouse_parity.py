import socket
import sys
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402
from shared.tools import team as team_mod  # noqa: E402
from v2.adapters import coverage  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BASELINE = store.CANONICAL_DB_PATH
SEASON_WIDE_TABLES = (
    "silver_team_games",
    "silver_hist_gamelogs",
    "silver_playoffs",
    "silver_playoff_gamelogs",
)
SEASONS_SAMPLED = 4
IDENTITY_META = ("warehouse_id", "warehouse_sha256")


class WarehouseWouldBeWritten(RuntimeError):
    pass


def _warehouse_files():
    return sorted(path for path in DATA_DIR.glob("warehouse*.duckdb")
                  if path.is_file())


def _require_several_warehouses():
    paths = _warehouse_files()
    if len(paths) < 2:
        pytest.skip(f"parity needs at least two warehouse files under "
                    f"{DATA_DIR}, found {len(paths)}")
    if not BASELINE.exists():
        pytest.skip(f"no baseline warehouse at {BASELINE}")
    return paths


@contextmanager
def _read_only_file(path):
    con = duckdb.connect(str(path), read_only=True)
    try:
        yield con
    finally:
        con.close()


@contextmanager
def _warehouse_open(path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", path)
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    coverage.coverage_cache_clear()
    try:
        yield
    finally:
        store.warehouse_pool_clear()
        store.warehouse_tables_cache_clear()
        coverage.coverage_cache_clear()


@contextmanager
def _no_writes(monkeypatch):
    real = store._connect_once

    def guarded(read_only):
        if not read_only:
            raise WarehouseWouldBeWritten(
                f"{store.DB_PATH.name} was opened for writing by a read-only "
                f"question")
        return real(read_only)

    monkeypatch.setattr(store, "_connect_once", guarded)


@contextmanager
def _no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("the warehouse already holds this season, so the "
                             "answer must not cost a network call")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


def _comparable(out):
    meta = {key: value for key, value in (out.get("meta") or {}).items()
            if key not in IDENTITY_META}
    return {"ok": out.get("ok"), "error": out.get("error"),
            "rows": out.get("rows"), "meta": meta}


def _opponent(team, matchup):
    text = str(matchup or "").upper().replace("@", " ").replace("VS.", " ")
    for token in text.split():
        token = token.strip(".")
        if len(token) == 3 and token.isalpha() and token != team:
            return token
    return ""


def _supported_questions(path):
    questions = []
    with _read_only_file(path) as con:
        seasons = [row[0] for row in con.execute(
            "SELECT DISTINCT _season FROM silver_hist_gamelogs"
            " WHERE _season IS NOT NULL ORDER BY _season DESC LIMIT ?",
            [SEASONS_SAMPLED]).fetchall()]
        for season in seasons:
            counts: dict[tuple[str, str], int] = {}
            for team, matchup in con.execute(
                "SELECT team_abbreviation, matchup FROM silver_hist_gamelogs"
                " WHERE _season = ? AND season_type = 'regular-season'",
                [season]).fetchall():
                home = str(team or "").upper()
                other = _opponent(home, matchup)
                if not other:
                    continue
                key = tuple(sorted((home, other)))
                counts[key] = counts.get(key, 0) + 1
            if not counts:
                continue
            pair, meetings = max(counts.items(), key=lambda item: item[1])
            if meetings > 0:
                questions.append((pair[0], pair[1], season))
    return questions


def _uncovered_season(paths):
    earliest_per_file = []
    for path in paths:
        starts = []
        with _read_only_file(path) as con:
            present = set()
            for table in SEASON_WIDE_TABLES:
                present.update(
                    row[0] for row in con.execute(
                        f"SELECT DISTINCT _season FROM {table}"
                        f" WHERE _season IS NOT NULL").fetchall())
        for season in present:
            start = coverage.parse_season_start(season)
            if start is not None:
                starts.append(start)
        if starts:
            earliest_per_file.append(min(starts))
    if not earliest_per_file:
        return None
    start = max(earliest_per_file) - 1
    return f"{start}-{start % 100 + 1:02d}"


def _holds_no_rows(path, season):
    with _read_only_file(path) as con:
        for table in SEASON_WIDE_TABLES:
            count = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE _season = ?",
                [season]).fetchone()[0]
            if count:
                return False
    return True


def _answer(path, a, b, season, monkeypatch):
    with _warehouse_open(path, monkeypatch):
        return team_mod.get_season_series.invoke(
            {"team_a": a, "team_b": b, "season": season})


def _fingerprint(path):
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def _baseline_questions():
    questions = _supported_questions(BASELINE)
    if not questions:
        pytest.skip(f"no covered pair derived from {BASELINE}")
    return questions


def test_the_same_covered_question_answers_the_same_from_every_warehouse(
        monkeypatch):
    paths = _require_several_warehouses()
    _no_writes(monkeypatch)
    before = {path: _fingerprint(path) for path in paths}
    for a, b, season in _baseline_questions():
        answers = {path.name: _comparable(
            _answer(path, a, b, season, monkeypatch)) for path in paths}
        for name, answer in answers.items():
            assert answer["ok"] is True, (name, a, b, season, answer["error"])
        baseline_answer = answers[BASELINE.name]
        for name, answer in answers.items():
            assert answer == baseline_answer, (name, a, b, season)
    for path in paths:
        assert _fingerprint(path) == before[path], f"{path.name} was written"


def test_a_season_no_table_holds_is_refused_the_same_from_every_warehouse(
        monkeypatch):
    paths = _require_several_warehouses()
    _no_writes(monkeypatch)
    season = _uncovered_season(paths)
    if season is None:
        pytest.skip("no season boundary to probe")
    for path in paths:
        assert _holds_no_rows(path, season), (path.name, season)
    a, b, _ = _baseline_questions()[0]
    answers = {path.name: _comparable(
        _answer(path, a, b, season, monkeypatch)) for path in paths}
    for name, answer in answers.items():
        assert answer["ok"] is False, (name, season)
        assert season in answer["error"], (name, season)
        for table in SEASON_WIDE_TABLES:
            assert table in answer["error"], (name, table)
    for name, answer in answers.items():
        assert answer == answers[BASELINE.name], (name, season)


def test_a_covered_season_is_answered_without_any_network_call(monkeypatch):
    paths = _require_several_warehouses()
    _no_writes(monkeypatch)
    _no_network(monkeypatch)
    a, b, season = _baseline_questions()[0]
    for path in paths:
        out = _answer(path, a, b, season, monkeypatch)
        assert out["ok"] is True, (path.name, out.get("error"))
        assert out["rows"]["summary"]["games"] > 0, path.name


def test_every_warehouse_reports_a_covered_season_it_reads_rows_for(
        monkeypatch):
    paths = _require_several_warehouses()
    _no_writes(monkeypatch)
    for a, b, season in _baseline_questions():
        for path in paths:
            with _read_only_file(path) as con:
                rows = con.execute(
                    "SELECT COUNT(*) FROM silver_hist_gamelogs"
                    " WHERE _season = ? AND season_type = 'regular-season'"
                    " AND ((team_abbreviation = ? AND matchup ILIKE ?)"
                    "   OR (team_abbreviation = ? AND matchup ILIKE ?))",
                    [season, a, f"%{b}%", b, f"%{a}%"]).fetchone()[0]
            assert rows > 0, (path.name, a, b, season)
            out = _answer(path, a, b, season, monkeypatch)
            assert out["ok"] is True, (path.name, a, b, season,
                                       out.get("error"))
            assert "no recorded meetings" not in str(out.get("error") or "")
