import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import verify_multihop_answers as vma

BROKEN = object()


class FakeRelation:
    """Stand-in for a duckdb relation: just hands back the stubbed rows."""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConnection:
    """In-memory duckdb connection: no warehouse file, no network, deterministic.

    `results` maps a SQL string to the rows it returns, or to BROKEN for SQL that
    must blow up the way a bad query does. Any other SQL is an unknown table.
    """

    def __init__(self, results):
        self._results = dict(results)
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)
        if sql not in self._results:
            raise duckdb.Error("Catalog Error: Table with name %s does not exist!" % sql)
        rows = self._results[sql]
        if rows is BROKEN:
            raise duckdb.Error('Binder Error: Referenced column "nope" not found')
        return FakeRelation(rows)


def make_row(task_id, answer, paths=(), verification_sql=None):
    """A jsonl-shaped eval case."""
    row = {
        "task_id": task_id,
        "answer": answer,
        "expected_paths": [
            {"name": name, "sql": sql} for name, sql in paths
        ],
    }
    if verification_sql:
        row["verification_sql"] = verification_sql
    return row


# the mh3-a-004 shape: the record answer is spread over two separate columns
REBOUNDS_LEADER_SQL = "SELECT PLAYER, TEAM_ID FROM silver_leaders_reb WHERE _season='2025-26' AND RANK=1"
TEAM_RATINGS_SQL = ("SELECT TEAM_NAME, NET_RATING, W, L FROM silver_team_ratings "
                    "WHERE _season='2025-26' AND TEAM_ID=1610612757")


def run_cli(monkeypatch, tmp_path, capsys, rows, results):
    """Run the real CLI end to end against a fake duckdb connection."""
    connection = FakeConnection(results)
    monkeypatch.setattr(vma.duckdb, "connect", lambda *a, **kw: connection)
    case_file = tmp_path / "cases.jsonl"
    case_file.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    # a warehouse path that does not exist: the run only survives the monkeypatch
    with pytest.raises(SystemExit) as exc:
        vma.main(["verify_multihop_answers.py", str(case_file), str(tmp_path / "nope.duckdb")])
    return exc.value.code, capsys.readouterr().out, connection


def summaries(output):
    return [line for line in output.splitlines() if line.startswith("rows=")]


def test_missing_numeral_is_a_failure():
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    evidence = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 41, 40)],
    }

    failures, _ = vma.verify_case(row, lambda sql: evidence[sql])

    assert len(failures) == 1
    task_id, _name, message = failures[0]
    assert task_id == "mh3-a-004"
    assert "42" in message
    assert "Portland Trail Blazers" in message  # observed evidence is reported


def test_mismatched_record_numeral_is_a_failure():
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    evidence = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 43, 40)],
    }

    failures, _ = vma.verify_case(row, lambda sql: evidence[sql])

    assert [f[2] for f in failures] == [
        "MISSING NUMERAL: 42 (evidence: Donovan Clingan 1610612757 "
        "Portland Trail Blazers -0.4 43 40)"]


def test_numeral_supported_by_a_second_expected_path_passes():
    # the mh3-a-010 shape: 1142 is carried only by the second path
    top_salary_sql = "SELECT PLAYER_NAME, SALARY FROM silver_salaries"
    season_points_sql = "SELECT PTS FROM silver_leaders_pts"
    team_ratings_sql = "SELECT TEAM_NAME, NET_RATING FROM silver_team_ratings"
    row = make_row(
        "mh3-a-010", "Stephen Curry, 1142, -0.5",
        [("top_salary", top_salary_sql),
         ("season_points", season_points_sql),
         ("team_ratings", team_ratings_sql)])
    evidence = {
        top_salary_sql: [("Stephen Curry", 62587158)],
        season_points_sql: [(1142,)],
        team_ratings_sql: [("Golden State Warriors", -0.5)],
    }

    failures, _ = vma.verify_case(row, lambda sql: evidence[sql])

    assert failures == []


def test_compound_answer_token_matches_evidence_columns():
    """Regression guard: `42-40` must resolve against cells printing `42` `40`."""
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    evidence = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 42, 40)],
    }

    failures, lines = vma.verify_case(row, lambda sql: evidence[sql])

    assert failures == []
    assert lines == [
        "mh3-a-004     rebounds_leader  -> Donovan Clingan 1610612757",
        "mh3-a-004     team_ratings     -> Portland Trail Blazers -0.4 42 40",
    ]


def test_answer_without_expected_paths_is_a_failure():
    row = make_row("mnba-easy-002", 44)

    failures, lines = vma.verify_case(row, lambda sql: [])

    assert failures == [("mnba-easy-002", "-", "NO EVIDENCE PATHS")]
    assert len(lines) == 1


def test_empty_result_for_a_declared_path_is_a_failure():
    top_salary_sql = "SELECT PLAYER_NAME FROM silver_salaries"
    season_points_sql = "SELECT PTS FROM silver_leaders_pts"
    team_wins_sql = "SELECT W FROM silver_team_ratings"
    row = make_row(
        "mh3-a-009", "Chet Holmgren, 1181",
        [("top_salary", top_salary_sql),
         ("season_points", season_points_sql),
         ("team_wins", team_wins_sql)])
    evidence = {
        top_salary_sql: [("Chet Holmgren",)],
        season_points_sql: [(1181,)],
        team_wins_sql: [],
    }

    failures, _ = vma.verify_case(row, lambda sql: evidence[sql])

    assert failures == [("mh3-a-009", "team_wins", "EMPTY EVIDENCE")]


def test_broken_path_sql_keeps_sql_error_failure():
    steals_sql = "SELECT PLAYER FROM silver_leaders_stl"
    broken_sql = "SELECT NET_RATING FROM silver_team_ratings WHERE nope=1"
    playoff_wins_sql = "SELECT COUNT(*) FROM silver_playoffs"
    row = make_row(
        "mh3-a-003", "Cason Wallace, 64",
        [("steals_leader", steals_sql),
         ("team_ratings", broken_sql),
         ("playoff_wins", playoff_wins_sql)])

    def execute_sql(sql):
        if sql == broken_sql:
            raise duckdb.Error('Binder Error: Referenced column "nope" not found')
        return {"SELECT PLAYER FROM silver_leaders_stl": [("Cason Wallace", 1610612760)],
                "SELECT COUNT(*) FROM silver_playoffs": [(64,)]}[sql]

    failures, _ = vma.verify_case(row, execute_sql)

    assert len(failures) == 1
    task_id, name, message = failures[0]
    assert (task_id, name) == ("mh3-a-003", "team_ratings")
    assert message == 'SQL ERROR: Binder Error: Referenced column "nope" not found'


def test_non_numeral_answer_tokens_are_ignored():
    row = make_row("mh3-a-001", "Nikola Jokic", [("assists_leader", "SELECT PLAYER FROM silver_leaders_ast")])

    failures, _ = vma.verify_case(row, lambda sql: [("Nikola Jokic",)])

    assert failures == []


def test_verification_sql_line_is_still_printed():
    playoff_wins_sql = "SELECT COUNT(*) FROM silver_playoffs"
    answer_check_sql = "SELECT COUNT(*) FROM silver_playoffs WHERE WL='W'"
    row = make_row(
        "mh3-a-001", "Nikola Jokic, Denver Nuggets, 2",
        [("playoff_wins", playoff_wins_sql)],
        verification_sql=answer_check_sql)
    evidence = {
        playoff_wins_sql: [(2,)],
        answer_check_sql: [(2,)],
    }

    failures, lines = vma.verify_case(row, lambda sql: evidence[sql])

    assert failures == []
    assert lines == [
        "mh3-a-001     playoff_wins     -> 2",
        "mh3-a-001     answer_check     -> 2",
    ]


def test_supported_corpus_row_exits_zero(monkeypatch, tmp_path, capsys):
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    results = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 42, 40)],
    }

    code, out, connection = run_cli(monkeypatch, tmp_path, capsys, [row], results)

    assert code == 0
    assert summaries(out) == ["rows=1 failures=0"]
    assert "FAIL" not in out
    assert [sql for sql in connection.executed] == [REBOUNDS_LEADER_SQL, TEAM_RATINGS_SQL]


def test_false_pass_repro_is_caught_by_the_cli(monkeypatch, tmp_path, capsys):
    """The three parent-repro cases must no longer report failures=0 / exit 0."""
    rows = [
        make_row(
            "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
            [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)]),
        make_row(
            "mh3-a-010", "Stephen Curry, 1142, -0.5",
            [("top_salary", "SELECT PLAYER_NAME, SALARY FROM silver_salaries"),
             ("season_points", "SELECT PTS FROM silver_leaders_pts"),
             ("team_ratings", "SELECT TEAM_NAME, NET_RATING FROM silver_team_ratings")]),
        make_row("mnba-easy-002", 44),
    ]
    results = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 42, 40)],
        "SELECT PLAYER_NAME, SALARY FROM silver_salaries": [("Stephen Curry", 62587158)],
        "SELECT PTS FROM silver_leaders_pts": [(1142,)],
        "SELECT TEAM_NAME, NET_RATING FROM silver_team_ratings": [("Golden State Warriors", -0.5)],
    }

    code, out, _ = run_cli(monkeypatch, tmp_path, capsys, rows, results)

    assert code == 1
    assert summaries(out) == ["rows=3 failures=1"]
    assert "FAIL ('mnba-easy-002', '-', 'NO EVIDENCE PATHS')" in out


def test_mismatch_reported_with_exit_1(monkeypatch, tmp_path, capsys):
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    results = {
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 43, 40)],
    }

    code, out, _ = run_cli(monkeypatch, tmp_path, capsys, [row], results)

    assert code == 1
    assert summaries(out) == ["rows=1 failures=1"]
    assert "MISSING NUMERAL: 42" in out


def test_blank_lines_are_skipped(monkeypatch, tmp_path, capsys):
    row = make_row(
        "mh3-a-004", "Donovan Clingan, Portland Trail Blazers, -0.4, 42-40",
        [("rebounds_leader", REBOUNDS_LEADER_SQL), ("team_ratings", TEAM_RATINGS_SQL)])
    connection = FakeConnection({
        REBOUNDS_LEADER_SQL: [("Donovan Clingan", 1610612757)],
        TEAM_RATINGS_SQL: [("Portland Trail Blazers", -0.4, 42, 40)],
    })
    monkeypatch.setattr(vma.duckdb, "connect", lambda *a, **kw: connection)
    case_file = tmp_path / "cases.jsonl"
    case_file.write_text("\n\n" + json.dumps(row) + "\n\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        vma.main(["verify_multihop_answers.py", str(case_file)])
    out = capsys.readouterr().out

    assert exc.value.code == 0
    assert summaries(out) == ["rows=1 failures=0"]
