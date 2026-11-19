import duckdb
import pytest

from shared import store
from shared.tools.shared import run_python


@pytest.fixture
def warehouse(monkeypatch, tmp_path):
    db = tmp_path / "names.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE salaries(PLAYER_NAME VARCHAR, SALARY DOUBLE)")
    con.execute("INSERT INTO salaries VALUES ('Nikola Jokic', 55.2), ('Larry Nance Jr.', 2.1), ('A.J. Green', 2.3)")
    con.execute("CREATE TABLE rapm(name VARCHAR, rapm DOUBLE)")
    con.execute("INSERT INTO rapm VALUES ('Nikola Jokić', 7.1), ('Larry Nance Jr', 1.0), ('AJ Green', 0.4), ('1642396', 0.2)")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setenv("DIME_WAREHOUSE", str(db))
    store.warehouse_pool_clear()
    yield db
    store.warehouse_pool_clear()


def test_name_key_joins_names_across_spellings(warehouse):
    con = store.connect(read_only=True)
    rows = con.execute(
        "SELECT s.PLAYER_NAME, r.rapm FROM salaries s JOIN rapm r ON name_key(s.PLAYER_NAME) = name_key(r.name) ORDER BY 1"
    ).fetchall()
    assert rows == [("A.J. Green", 0.4), ("Larry Nance Jr.", 1.0), ("Nikola Jokic", 7.1)]


def test_name_key_is_null_for_names_without_letters(warehouse):
    con = store.connect(read_only=True)
    assert con.execute("SELECT name_key('1642396'), name_key(NULL)").fetchone() == (None, None)


def test_run_python_connection_has_name_key(warehouse):
    res = run_python.invoke({"code": "print(con.execute(\"SELECT name_key('Dennis Schröder')\").fetchone()[0])"})
    assert res["ok"] is True
    assert "dennisschroder" in str(res)
