import hashlib
import importlib.util
import json
import subprocess
import sys

import pytest
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "publish_warehouse.py"


def _load():
    spec = importlib.util.spec_from_file_location("publish_warehouse", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


class EntryNotFoundError(Exception):
    pass


class FakeApi:
    def __init__(self, manifest_path=None):
        self.manifest_path = manifest_path
        self.created = []
        self.visibility = []
        self.commits = []

    def hf_hub_download(self, **kwargs):
        if self.manifest_path is None:
            raise EntryNotFoundError("missing")
        return str(self.manifest_path)

    def create_repo(self, **kwargs):
        self.created.append(kwargs)

    def update_repo_visibility(self, **kwargs):
        self.visibility.append(kwargs)

    def create_commit(self, **kwargs):
        self.commits.append(kwargs)
        return SimpleNamespace(commit_url="https://huggingface.co/datasets/acme/warehouse/commit/abc")


def test_build_manifest_and_checksum(tmp_path):
    pw = _load()
    warehouse = tmp_path / "warehouse.duckdb"
    warehouse.write_bytes(b"warehouse-bytes")
    sha = _sha256(warehouse)
    manifest = pw.build_manifest("acme/warehouse", "main", warehouse, sha, warehouse.stat().st_size,
                                 published_at="2026-01-02T03:04:05+00:00")
    assert manifest["dataset"] == "acme/warehouse"
    assert manifest["revision"] == "main"
    assert manifest["warehouse_file"] == "warehouse.duckdb"
    assert manifest["sha256"] == sha
    assert manifest["size"] == warehouse.stat().st_size
    assert manifest["published_at"] == "2026-01-02T03:04:05+00:00"
    assert json.loads(pw.manifest_text(manifest))["sha256"] == sha
    assert pw.checksum_text(sha) == f"{sha}  warehouse.duckdb\n"


def test_publish_dry_run_cli(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    warehouse.write_bytes(b"dry-run-warehouse")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--warehouse", str(warehouse),
         "--dataset", "acme/warehouse", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    verdict = json.loads(proc.stdout)
    assert verdict["dry_run"] is True
    assert verdict["skipped"] is False
    assert verdict["sha256"] == _sha256(warehouse)
    assert verdict["size"] == warehouse.stat().st_size
    assert verdict["manifest"]["warehouse_file"] == "warehouse.duckdb"


def test_publish_uploads_warehouse_manifest_and_checksum(tmp_path):
    pw = _load()
    warehouse = tmp_path / "warehouse.duckdb"
    warehouse.write_bytes(b"upload-warehouse")
    api = FakeApi()
    verdict = pw.publish(warehouse, dataset="acme/warehouse", token="token", api=api,
                         published_at="2026-01-02T03:04:05+00:00")
    assert verdict["skipped"] is False
    assert verdict["commit"].endswith("/commit/abc")
    assert api.created == [{"repo_id": "acme/warehouse", "repo_type": "dataset", "private": True,
                            "exist_ok": True, "token": "token"}]
    assert api.visibility == [{"repo_id": "acme/warehouse", "private": True, "repo_type": "dataset",
                               "token": "token"}]
    assert len(api.commits) == 1
    commit = api.commits[0]
    assert commit["repo_id"] == "acme/warehouse"
    assert commit["repo_type"] == "dataset"
    assert commit["revision"] == "main"
    assert commit["token"] == "token"
    paths = [op.path_in_repo for op in commit["operations"]]
    assert paths == ["warehouse.duckdb", "warehouse.duckdb.sha256", "manifest.json", "README.md"]
    assert commit["operations"][0].path_or_fileobj == str(warehouse.resolve())
    checksum = commit["operations"][1].path_or_fileobj.decode()
    manifest = json.loads(commit["operations"][2].path_or_fileobj.decode())
    card = commit["operations"][3].path_or_fileobj.decode()
    assert card.startswith("---\nlicense:")
    assert _sha256(warehouse) in card
    assert checksum == f"{_sha256(warehouse)}  warehouse.duckdb\n"
    assert manifest["sha256"] == _sha256(warehouse)
    assert manifest["published_at"] == "2026-01-02T03:04:05+00:00"


def test_dataset_card_lists_tables_and_sources(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    pw = _load()
    warehouse = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute("CREATE TABLE silver_test (x INTEGER, _season VARCHAR, _source VARCHAR)")
    con.execute("INSERT INTO silver_test VALUES (1, '2024-25', 'nba_api'), (2, '2025-26', 'nba_api')")
    con.close()
    manifest = {"size": warehouse.stat().st_size, "sha256": "deadbeef",
                "published_at": "2026-01-02T00:00:00+00:00"}
    card = pw.build_dataset_card(warehouse, manifest)
    assert card.startswith("---\nlicense:")
    assert "| `silver_test` | 2 | 2024-25 – 2025-26 | nba_api |" in card
    assert "sha256: `deadbeef`" in card
    assert "Last updated: 2026-01-02T00:00:00+00:00" in card
    assert "`nba_api`" in card
    assert "fetch-data.sh" in card
    assert "publish_warehouse.py" in card


def test_publish_skips_when_remote_sha_matches(tmp_path):
    pw = _load()
    warehouse = tmp_path / "warehouse.duckdb"
    warehouse.write_bytes(b"same-warehouse")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"sha256": _sha256(warehouse)}))
    api = FakeApi(manifest_path=manifest_path)
    verdict = pw.publish(warehouse, dataset="acme/warehouse", token="token", api=api)
    assert verdict["skipped"] is True
    assert verdict["commit"] is None
    assert api.commits == []
