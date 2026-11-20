import duckdb
import pytest

from analyst import dataset_engine
from shared import store


@pytest.mark.parametrize("populated", [True, False])
def test_freshness_uses_a_read_only_connection(monkeypatch, tmp_path, populated):
    path = tmp_path / "freshness.duckdb"
    with duckdb.connect(str(path)) as con:
        if populated:
            con.execute("CREATE TABLE silver_sample(value INTEGER)")
            con.execute("INSERT INTO silver_sample VALUES (1)")
    modes = []

    def connect(*, read_only=False):
        modes.append(read_only)
        return duckdb.connect(str(path), read_only=read_only)

    monkeypatch.setattr(store, "connect", connect)
    with duckdb.connect(str(path), read_only=True):
        payload = dataset_engine._datasets_freshness_payload()
    assert modes == [True]
    assert payload["ok"] is True
    assert len(payload["rows"]) == int(populated)
    if populated:
        assert payload["rows"][0]["rows"] == 1


def test_freshness_closes_connection_on_query_failure(monkeypatch):
    class BrokenConnection:
        closed = False

        def execute(self, _query):
            raise RuntimeError("query failed")

        def close(self):
            self.closed = True

    connection = BrokenConnection()
    monkeypatch.setattr(store, "connect", lambda **_kwargs: connection)
    with pytest.raises(RuntimeError, match="query failed"):
        dataset_engine._datasets_freshness_payload()
    assert connection.closed
