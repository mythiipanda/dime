

def _isolated_store(monkeypatch, tmp_path):
    from shared import store

    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.duckdb")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", tmp_path / ".state.lock")
    return store

def test_save_and_list_run_id_round_trip(monkeypatch, tmp_path):
    store = _isolated_store(monkeypatch, tmp_path)
    store.save_run("thread", "q", "a", [], [], owner="owner", run_id="run-abc123")
    runs = store.list_runs("thread", "owner")
    assert len(runs) == 1
    assert runs[0]["id"] == "run-abc123"

def test_run_without_id_omits_id_field(monkeypatch, tmp_path):
    store = _isolated_store(monkeypatch, tmp_path)
    store.save_run("thread", "q", "a", [], [], owner="owner")
    runs = store.list_runs("thread", "owner")
    assert "id" not in runs[0]

def test_migration_adds_run_id_to_old_schema(monkeypatch, tmp_path):
    store = _isolated_store(monkeypatch, tmp_path)
    con = store.state_connect()
    try:
        con.execute(
            """CREATE TABLE runs(
            thread VARCHAR, question VARCHAR, answer VARCHAR,
            tables VARCHAR, suggestions VARCHAR, created_at VARCHAR,
            owner VARCHAR)"""
        )
        con.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
            ["thread", "q", "a", "[]", "[]", "2026-09-27T20:00:00+00:00", "owner"],
        )
    finally:
        con.close()
    store.save_run("thread", "q2", "a2", [], [], owner="owner", run_id="run-new")
    runs = {r["question"]: r for r in store.list_runs("thread", "owner")}
    assert runs["q2"]["id"] == "run-new"
    assert "id" not in runs["q"]
