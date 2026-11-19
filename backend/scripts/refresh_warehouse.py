import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
LOCAL_WAREHOUSE = REPO_ROOT / "backend" / "data" / "warehouse.duckdb"
DEFAULT_DATASET = "mythiix/dime-warehouse"
DEFAULT_SEASON = "2025-26"

sys.path.insert(0, str(SCRIPTS_DIR.parent))

SEEDERS = [
    ("current_season", "seed_current_season.py", ["--season"], True),
    ("bulk_history", "seed_bulk_history.py", [], True),
    ("recent_market", "seed_recent_market.py", [], True),
    ("transactions", "seed_transactions.py", [], True),
    ("injuries_news", "seed_injury_news.py", ["--season"], True),
    ("injury_entries", "normalize_injuries.py", [], True),
    ("tracking", "seed_tracking.py", [], True),
    ("playoffs", "seed_historical_playoffs.py", ["--season"], False),
    ("team_ratings", "seed_team_ratings.py", [], True),
    ("impact", "seed_bref_impact.py", [], True),
    ("salaries", "seed_salaries.py", [], False),
    ("stints", "seed_stints.py", [], True),
    ("scoreboard", "seed_scoreboard_2025_26.py", [], False),
    ("shots", "seed_shots_2025_26.py", [], False),
    ("repair_shot_names", "repair_shot_names.py", [], False),
    ("four_factors_team", "build_team_four_factors.py", [], False),
]


def pull_warehouse(dataset: str, work_dir: Path, token: str | None) -> Path:
    target = work_dir / "warehouse.duckdb"
    try:
        from huggingface_hub import hf_hub_download
        got = hf_hub_download(repo_id=dataset, filename="warehouse.duckdb",
                              repo_type="dataset", token=token)
        shutil.copy2(got, target)
        print(f"pulled {dataset} warehouse -> {target}")
        return target
    except Exception as exc:
        print(f"hub pull failed ({exc!r}); falling back to local warehouse")
        if not LOCAL_WAREHOUSE.is_file():
            raise RuntimeError(
                f"no pull source: {exc!r} and {LOCAL_WAREHOUSE} missing")
        shutil.copy2(LOCAL_WAREHOUSE, target)
        print(f"copied local warehouse -> {target}")
        return target


def pull_manifest(dataset: str, token: str | None) -> dict:
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(repo_id=dataset, filename="manifest.json",
                               repo_type="dataset", token=token)
        return json.loads(Path(path).read_text())
    except Exception as exc:
        print(f"manifest pull failed ({exc!r}); continuing without baseline")
        return {}


def snapshot_counts(warehouse: Path) -> dict[str, int]:
    import duckdb
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        return {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                for t in tables}
    finally:
        con.close()


def check_counts(before: dict[str, int], after: dict[str, int],
                 allow_shrink: bool) -> tuple[bool, list[str]]:
    problems = []
    missing = sorted(set(before) - set(after))
    for t in missing:
        problems.append(f"table dropped: {t}")
    for t in sorted(set(before) & set(after)):
        if after[t] < before[t] and not allow_shrink:
            problems.append(
                f"{t}: rows shrank {before[t]} -> {after[t]}")
    grew = sorted(t for t in set(before) & set(after) if after[t] > before[t])
    added = sorted(set(after) - set(before))
    print(f"check: {len(grew)} tables grew, {len(added)} added, "
          f"{len(missing)} dropped")
    for t in grew:
        print(f"  grew {t}: {before[t]} -> {after[t]}")
    for t in added:
        print(f"  added {t}: {after[t]} rows")
    return not problems, problems


def run_seeders(warehouse: Path, season: str, only: set[str] | None,
                dry_run: bool, env_extra: dict | None = None) -> list[str]:
    failures = []
    env = dict(os.environ)
    env["DIME_WAREHOUSE"] = str(warehouse)
    env.setdefault("DIME_ENV", "dev")
    if env_extra:
        env.update(env_extra)
    for name, script, args, supports_dry in SEEDERS:
        if only and name not in only:
            continue
        cmd = [sys.executable, str(SCRIPTS_DIR / script)]
        if "--season" in args:
            cmd += ["--season", season]
        cmd += [a for a in args if a != "--season"]
        if dry_run and supports_dry:
            cmd.append("--dry-run")
        print(f"=== seeder {name}: {' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd, env=env, cwd=str(SCRIPTS_DIR.parent),
                              capture_output=True, text=True, timeout=3600)
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-8:])
        print(tail)
        if proc.returncode != 0:
            print(f"seeder {name} failed rc={proc.returncode}")
            failures.append(name)
    return failures


def rollback_copy(warehouse: Path, backup: Path) -> None:
    shutil.copy2(backup, warehouse)
    print(f"rollback: restored {backup} over {warehouse}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=os.environ.get(
        "DIME_WAREHOUSE_DATASET", DEFAULT_DATASET))
    parser.add_argument("--season", default=DEFAULT_SEASON)
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--seeders", default="",
                        help="comma list; default runs all")
    parser.add_argument("--from-local", action="store_true",
                        help="seed the local backend/data/warehouse.duckdb "
                             "copy instead of pulling from the dataset")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument("--allow-shrink", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    work_dir = (Path(args.work_dir).expanduser().resolve() if args.work_dir
                else Path(tempfile.mkdtemp(prefix="dime-refresh-")))
    work_dir.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN")

    if args.from_local:
        warehouse = work_dir / "warehouse.duckdb"
        if not LOCAL_WAREHOUSE.is_file():
            print(f"FAILED: local warehouse missing: {LOCAL_WAREHOUSE}")
            return 2
        shutil.copy2(LOCAL_WAREHOUSE, warehouse)
        print(f"copied local warehouse -> {warehouse}")
        manifest = {}
    else:
        warehouse = pull_warehouse(args.dataset, work_dir, token)
        manifest = pull_manifest(args.dataset, token)
    if manifest:
        print(f"previous publish: sha256={manifest.get('sha256', '')[:12]} "
              f"size={manifest.get('size')}")
    backup = work_dir / "warehouse.rollback.duckdb"
    shutil.copy2(warehouse, backup)
    before = snapshot_counts(backup)
    print(f"baseline: {len(before)} tables, "
          f"{sum(before.values()):,} rows")

    only = {s.strip() for s in args.seeders.split(",") if s.strip()} or None
    failures = [] if args.skip_seed else run_seeders(
        warehouse, args.season, only, args.dry_run)
    if failures:
        rollback_copy(warehouse, backup)
        print(f"FAILED: seeders failed: {', '.join(failures)}; "
              "restored pre-seed copy, nothing published")
        return 3

    if not args.dry_run:
        ok, problems = check_counts(before, snapshot_counts(warehouse),
                                  args.allow_shrink)
        if not ok:
            rollback_copy(warehouse, backup)
            for p in problems:
                print(f"  check failed: {p}")
            print("FAILED: row-count checks failed; restored pre-seed "
                  "copy, nothing published")
            return 4
    else:
        print("dry-run: row-count check skipped (seeders ran dry)")

    if args.skip_publish:
        print("skip-publish: done, warehouse staged at", warehouse)
        return 0

    from publish_warehouse import publish
    verdict = publish(warehouse, dataset=args.dataset, token=token,
                      dry_run=args.dry_run,
                      commit_message=f"refresh {args.season} "
                                     f"({len(before)} baseline tables)")
    print(json.dumps({k: v for k, v in verdict.items()
                      if k != "card"}, indent=2, sort_keys=True))
    if not args.dry_run and not verdict.get("skipped") \
            and not verdict.get("commit"):
        print("FAILED: publish produced no commit")
        return 5
    print("rollback copy kept at", backup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
