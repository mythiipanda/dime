import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

DEFAULT_DATASET = "mythiix/dime-warehouse"
DEFAULT_REVISION = "main"
WAREHOUSE_FILE = "warehouse.duckdb"
MANIFEST_FILE = "manifest.json"
CHECKSUM_FILE = "warehouse.duckdb.sha256"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(dataset, revision, warehouse_path, sha256, size, published_at=None):
    return {
        "dataset": dataset,
        "revision": revision,
        "warehouse_file": WAREHOUSE_FILE,
        "sha256": sha256,
        "size": size,
        "warehouse_path": str(warehouse_path),
        "published_at": published_at or datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def manifest_text(manifest):
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def checksum_text(sha256):
    return f"{sha256}  {WAREHOUSE_FILE}\n"


def default_warehouse_path():
    configured = os.environ.get("DIME_WAREHOUSE")
    if configured:
        return Path(configured).expanduser().resolve()
    return REPO_ROOT / "backend" / "data" / "warehouse.duckdb"


def _is_not_found(exc):
    name = type(exc).__name__
    return name in {"EntryNotFoundError", "RepositoryNotFoundError"} or "not found" in str(exc).lower()


def _remote_sha256(api, dataset, revision, token):
    try:
        path = api.hf_hub_download(
            repo_id=dataset,
            filename=MANIFEST_FILE,
            repo_type="dataset",
            revision=revision,
            token=token,
        )
    except Exception as exc:
        if _is_not_found(exc):
            return None
        raise
    try:
        manifest = json.loads(Path(path).read_text())
    except Exception:
        return None
    return manifest.get("sha256")


def _ensure_private_dataset(api, dataset, token):
    api.create_repo(repo_id=dataset, repo_type="dataset", private=True, exist_ok=True, token=token)
    settings = getattr(api, "update_repo_settings", None)
    if settings is not None:
        settings(repo_id=dataset, private=True, repo_type="dataset", token=token)
        return
    update = getattr(api, "update_repo_visibility", None)
    if update is not None:
        update(repo_id=dataset, private=True, repo_type="dataset", token=token)


def _commit_label(info):
    for attr in ("commit_url", "sha", "oid"):
        value = getattr(info, attr, None)
        if value:
            return str(value)
    return str(info)


def publish(warehouse_path, dataset=DEFAULT_DATASET, revision=DEFAULT_REVISION, token=None,
            dry_run=False, commit_message=None, api=None, published_at=None):
    warehouse_path = Path(warehouse_path).expanduser().resolve()
    if not warehouse_path.is_file():
        raise FileNotFoundError(f"warehouse file not found: {warehouse_path}")
    sha256 = sha256_file(warehouse_path)
    size = warehouse_path.stat().st_size
    manifest = build_manifest(dataset, revision, warehouse_path, sha256, size, published_at)
    verdict = {
        "dataset": dataset,
        "revision": revision,
        "warehouse": str(warehouse_path),
        "warehouse_file": WAREHOUSE_FILE,
        "manifest_file": MANIFEST_FILE,
        "checksum_file": CHECKSUM_FILE,
        "sha256": sha256,
        "size": size,
        "dry_run": bool(dry_run),
        "skipped": False,
        "commit": None,
    }
    if dry_run:
        verdict["manifest"] = manifest
        return verdict
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi()
    remote_sha = _remote_sha256(api, dataset, revision, token)
    if remote_sha == sha256:
        verdict["skipped"] = True
        return verdict
    _ensure_private_dataset(api, dataset, token)
    from huggingface_hub import CommitOperationAdd
    operations = [
        CommitOperationAdd(path_in_repo=WAREHOUSE_FILE, path_or_fileobj=str(warehouse_path)),
        CommitOperationAdd(path_in_repo=CHECKSUM_FILE, path_or_fileobj=checksum_text(sha256).encode()),
        CommitOperationAdd(path_in_repo=MANIFEST_FILE, path_or_fileobj=manifest_text(manifest).encode()),
    ]
    message = commit_message or f"{WAREHOUSE_FILE} {sha256[:12]} ({size} bytes)"
    info = api.create_commit(
        repo_id=dataset,
        repo_type="dataset",
        revision=revision,
        operations=operations,
        commit_message=message,
        token=token,
    )
    verdict["commit"] = _commit_label(info)
    return verdict


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="publish_warehouse.py",
        description="Publish the Dime warehouse DuckDB file to a private Hugging Face dataset.",
    )
    parser.add_argument("--warehouse", default=None,
                        help="Warehouse file to publish. Defaults to DIME_WAREHOUSE or backend/data/warehouse.duckdb.")
    parser.add_argument("--dataset", default=os.environ.get("DIME_WAREHOUSE_DATASET", DEFAULT_DATASET),
                        help="Hugging Face dataset repo id.")
    parser.add_argument("--revision", default=os.environ.get("DIME_WAREHOUSE_REVISION", DEFAULT_REVISION),
                        help="Dataset revision to update.")
    parser.add_argument("--message", default=None, dest="commit_message",
                        help="Commit message for the dataset update.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the publish plan and manifest without uploading.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    warehouse = Path(args.warehouse).expanduser().resolve() if args.warehouse else default_warehouse_path()
    token = os.environ.get("HF_TOKEN")
    try:
        verdict = publish(
            warehouse,
            dataset=args.dataset,
            revision=args.revision,
            token=token,
            dry_run=args.dry_run,
            commit_message=args.commit_message,
        )
    except Exception as exc:
        print(f"publish_warehouse: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
