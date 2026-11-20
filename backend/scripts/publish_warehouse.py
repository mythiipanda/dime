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
CARD_FILE = "README.md"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SOURCE_LICENSES = {
    "nba_api": "NBA Stats API via nba_api (stats.nba.com terms of use)",
    "nba_api_boxscore_ext": "NBA Stats API via nba_api (stats.nba.com terms of use)",
    "nba_official": "NBA official league data (nba.com terms of use)",
    "sportsdataverse": "sportsdataverse-data releases, sourced from NBA Stats (MIT)",
    "huggingface": "community dataset on Hugging Face (see its dataset page)",
    "teamrankings": "TeamRankings public projections (teamrankings.com terms of use)",
    "spotrac": "Spotrac contract data (spotrac.com terms of use)",
    "basketball-reference": "Basketball Reference (sports-reference.com terms of use)",
    "bref_contracts": "Basketball Reference contract data (sports-reference.com terms of use)",
    "espn": "ESPN public data (espn.com terms of use)",
    "fivethirtyeight": "FiveThirtyEight RAPTOR archive (CC BY 4.0)",
    "orojas119/nba-salary-cap": "community dataset (orojas119/nba-salary-cap)",
    "pbpstats": "pbpstats public NBA possession data",
    "rapm-lite": "derived metric computed in-repo",
    "rapm-prior": "derived metric computed in-repo",
}


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


def _table_inventory(warehouse_path):
    import duckdb
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        names = sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
        inventory = []
        for name in names:
            count = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            columns = {row[0] for row in con.execute(f'DESCRIBE "{name}"').fetchall()}
            seasons = None
            season_col = "_season" if "_season" in columns else ("season" if "season" in columns else None)
            if season_col:
                lo, hi = con.execute(
                    f'SELECT min("{season_col}"), max("{season_col}") FROM "{name}"'
                ).fetchone()
                if lo is not None:
                    seasons = str(lo) if lo == hi else f"{lo} – {hi}"
            sources = ""
            if "_source" in columns:
                sources = ", ".join(sorted(
                    row[0] for row in
                    con.execute(f'SELECT DISTINCT "_source" FROM "{name}"').fetchall()
                    if row[0]
                ))
            inventory.append({
                "table": name,
                "rows": count,
                "seasons": seasons or "—",
                "sources": sources,
            })
        return inventory
    finally:
        con.close()


def _license_for_source(source):
    if source in SOURCE_LICENSES:
        return SOURCE_LICENSES[source]
    head = source.split(":", 1)[0]
    if head in SOURCE_LICENSES:
        return SOURCE_LICENSES[head]
    return "see source terms"


def build_dataset_card(warehouse_path, manifest):
    try:
        tables = _table_inventory(warehouse_path)
    except Exception as exc:
        tables = []
        inventory_error = str(exc)
    else:
        inventory_error = None
    licenses = {}
    for row in tables:
        for source in row["sources"].split(", ") if row["sources"] else []:
            licenses.setdefault(source, _license_for_source(source))
    lines = [
        "---",
        "license: other",
        "tags:",
        "  - nba",
        "  - basketball",
        "  - sports-analytics",
        "  - duckdb",
        "---",
        "",
        "# Dime Warehouse",
        "",
        "DuckDB warehouse backing [Dime](https://github.com/mythiipanda/dime), an NBA analytics agent. "
        "Bronze and silver tables hold box scores, play-by-play, tracking, contracts, and historical "
        "stats, normalized for deterministic tool queries.",
        "",
        f"- Warehouse file: `{WAREHOUSE_FILE}` ({manifest['size']:,} bytes)",
        f"- sha256: `{manifest['sha256']}`",
        f"- Last updated: {manifest['published_at']}",
        "",
        "## Tables",
        "",
    ]
    if inventory_error is not None:
        lines.append(f"Table inventory unavailable at publish time: {inventory_error}")
        lines.append("")
    else:
        lines += [
            "| Table | Rows | Seasons | Sources |",
            "| --- | --- | --- | --- |",
        ]
        for row in tables:
            lines.append(f"| `{row['table']}` | {row['rows']:,} | {row['seasons']} | {row['sources']} |")
        lines.append("")
    lines.append("## Sources")
    lines.append("")
    if licenses:
        for source in sorted(licenses):
            lines.append(f"- `{source}` — {licenses[source]}")
    else:
        lines.append("See each table's `_source` provenance column.")
    lines += [
        "",
        "Every silver table carries provenance columns: `_source` (origin dataset), `_season` "
        "(NBA season label), `_entity` (ingestion unit), and `_fetched_at` (UTC timestamp). "
        "The `fetch_log` table records one row per ingestion unit.",
        "",
        "## Pull",
        "",
        "```bash",
        "./scripts/fetch-data.sh",
        "```",
        "",
        f"Downloads `{WAREHOUSE_FILE}` from this dataset into `backend/data/`.",
        "",
        "## Publish",
        "",
        "```bash",
        f"python backend/scripts/publish_warehouse.py --warehouse backend/data/{WAREHOUSE_FILE}",
        "```",
        "",
        f"Uploads `{WAREHOUSE_FILE}`, `{CHECKSUM_FILE}`, `{MANIFEST_FILE}`, and this card to the "
        "dataset. Requires `HF_TOKEN` with write access.",
        "",
    ]
    return "\n".join(lines)


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
        "card_file": CARD_FILE,
        "sha256": sha256,
        "size": size,
        "dry_run": bool(dry_run),
        "skipped": False,
        "commit": None,
    }
    card = build_dataset_card(warehouse_path, manifest)
    if dry_run:
        verdict["manifest"] = manifest
        verdict["card"] = card
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
        CommitOperationAdd(path_in_repo=CARD_FILE, path_or_fileobj=card.encode()),
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
=======
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
CARD_FILE = "README.md"
DICTIONARY_FILE = "data_dictionary.json"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SOURCE_LICENSES = {
    "nba_api": "NBA Stats API via nba_api (stats.nba.com terms of use)",
    "nba_api_boxscore_ext": "NBA Stats API via nba_api (stats.nba.com terms of use)",
    "nba_official": "NBA official league data (nba.com terms of use)",
    "sportsdataverse": "sportsdataverse-data releases, sourced from NBA Stats (MIT)",
    "huggingface": "community dataset on Hugging Face (see its dataset page)",
    "teamrankings": "TeamRankings public projections (teamrankings.com terms of use)",
    "spotrac": "Spotrac contract data (spotrac.com terms of use)",
    "basketball-reference": "Basketball Reference (sports-reference.com terms of use)",
    "bref_contracts": "Basketball Reference contract data (sports-reference.com terms of use)",
    "espn": "ESPN public data (espn.com terms of use)",
    "fivethirtyeight": "FiveThirtyEight RAPTOR archive (CC BY 4.0)",
    "orojas119/nba-salary-cap": "community dataset (orojas119/nba-salary-cap)",
    "pbpstats": "pbpstats public NBA possession data",
    "rapm-lite": "derived metric computed in-repo",
    "rapm-prior": "derived metric computed in-repo",
}


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


def _table_inventory(warehouse_path):
    import duckdb
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        names = sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
        inventory = []
        for name in names:
            count = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            columns = {row[0] for row in con.execute(f'DESCRIBE "{name}"').fetchall()}
            seasons = None
            season_col = "_season" if "_season" in columns else ("season" if "season" in columns else None)
            if season_col:
                lo, hi = con.execute(
                    f'SELECT min("{season_col}"), max("{season_col}") FROM "{name}"'
                ).fetchone()
                if lo is not None:
                    seasons = str(lo) if lo == hi else f"{lo} – {hi}"
            sources = ""
            if "_source" in columns:
                sources = ", ".join(sorted(
                    row[0] for row in
                    con.execute(f'SELECT DISTINCT "_source" FROM "{name}"').fetchall()
                    if row[0]
                ))
            inventory.append({
                "table": name,
                "rows": count,
                "seasons": seasons or "—",
                "sources": sources,
            })
        return inventory
    finally:
        con.close()


def _license_for_source(source):
    if source in SOURCE_LICENSES:
        return SOURCE_LICENSES[source]
    head = source.split(":", 1)[0]
    if head in SOURCE_LICENSES:
        return SOURCE_LICENSES[head]
    return "see source terms"


def build_dataset_card(warehouse_path, manifest):
    try:
        tables = _table_inventory(warehouse_path)
    except Exception as exc:
        tables = []
        inventory_error = str(exc)
    else:
        inventory_error = None
    licenses = {}
    for row in tables:
        for source in row["sources"].split(", ") if row["sources"] else []:
            licenses.setdefault(source, _license_for_source(source))
    lines = [
        "---",
        "license: other",
        "tags:",
        "  - nba",
        "  - basketball",
        "  - sports-analytics",
        "  - duckdb",
        "---",
        "",
        "# Dime Warehouse",
        "",
        "DuckDB warehouse backing [Dime](https://github.com/mythiipanda/dime), an NBA analytics agent. "
        "Bronze and silver tables hold box scores, play-by-play, tracking, contracts, and historical "
        "stats, normalized for deterministic tool queries.",
        "",
        f"- Warehouse file: `{WAREHOUSE_FILE}` ({manifest['size']:,} bytes)",
        f"- sha256: `{manifest['sha256']}`",
        f"- Last updated: {manifest['published_at']}",
        "",
        "## Tables",
        "",
    ]
    if inventory_error is not None:
        lines.append(f"Table inventory unavailable at publish time: {inventory_error}")
        lines.append("")
    else:
        lines += [
            "| Table | Rows | Seasons | Sources |",
            "| --- | --- | --- | --- |",
        ]
        for row in tables:
            lines.append(f"| `{row['table']}` | {row['rows']:,} | {row['seasons']} | {row['sources']} |")
        lines.append("")
    lines.append("## Sources")
    lines.append("")
    if licenses:
        for source in sorted(licenses):
            lines.append(f"- `{source}` — {licenses[source]}")
    else:
        lines.append("See each table's `_source` provenance column.")
    lines += [
        "",
        "Every silver table carries provenance columns: `_source` (origin dataset), `_season` "
        "(NBA season label), `_entity` (ingestion unit), and `_fetched_at` (UTC timestamp). "
        "The `fetch_log` table records one row per ingestion unit.",
        "",
        "## Pull",
        "",
        "```bash",
        "./scripts/fetch-data.sh",
        "```",
        "",
        f"Downloads `{WAREHOUSE_FILE}` from this dataset into `backend/data/`.",
        "",
        "## Publish",
        "",
        "```bash",
        f"python backend/scripts/publish_warehouse.py --warehouse backend/data/{WAREHOUSE_FILE}",
        "```",
        "",
        f"Uploads `{WAREHOUSE_FILE}`, `{CHECKSUM_FILE}`, `{MANIFEST_FILE}`, and this card to the "
        "dataset. Requires `HF_TOKEN` with write access.",
        "",
    ]
    return "\n".join(lines)


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
        "card_file": CARD_FILE,
        "sha256": sha256,
        "size": size,
        "dry_run": bool(dry_run),
        "skipped": False,
        "commit": None,
    }
    card = build_dataset_card(warehouse_path, manifest)
    if dry_run:
        verdict["manifest"] = manifest
        verdict["card"] = card
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
        CommitOperationAdd(path_in_repo=CARD_FILE, path_or_fileobj=card.encode()),
    ]
    dictionary_path = warehouse_path.parent / DICTIONARY_FILE
    if dictionary_path.is_file():
        verdict["dictionary_file"] = DICTIONARY_FILE
        operations.append(CommitOperationAdd(
            path_in_repo=DICTIONARY_FILE,
            path_or_fileobj=str(dictionary_path)))
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
>>>>>>> origin/dev
