import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CCCC = Path(r"C:\Users\15980\Downloads\dime\t3-coordination\tools\cccc-v1.8.0\bin\cccc.exe")
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
CCCC_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")
SCAN_ROOTS = ("backend/", "frontend/", "acceptance/", "scripts/")
EXCLUDED_DIRS = ("node_modules", ".next", "dist", "__pycache__", ".git", "out", "coverage")
MAX_COGNITIVE = 40
MAX_CYCLOMATIC = 40
MAX_LOC = 1000


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--exclude-paths", nargs="*", default=[])
    parser.add_argument("--changed", "--Changed", dest="changed", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    return parser.parse_args(argv)


def normalize_excludes(raw: list[str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        for part in item.split(","):
            cleaned = part.strip().replace("\\", "/").lstrip("./").rstrip("/")
            if cleaned:
                out.append(cleaned)
    return out


def is_excluded(rel_path: str, excludes: list[str]) -> bool:
    norm = rel_path.replace("\\", "/").lstrip("./")
    parts = norm.split("/")
    if any(seg in EXCLUDED_DIRS for seg in parts[:-1]):
        return True
    for pat in excludes:
        if norm == pat or norm.startswith(f"{pat}/"):
            return True
    return False


def is_test_path(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    name = Path(norm).name
    if "/tests/" in norm or norm.startswith("tests/") or "/evals/" in norm:
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(tag in name for tag in (".test.", ".spec."))


def run_step(label: str, cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> int:
    print(f"=== {label} ===")
    merged_env = os.environ.copy()
    py_dir = str(Path(sys.executable).resolve().parent)
    merged_env["PATH"] = py_dir + os.pathsep + merged_env.get("PATH", "")
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, cwd=str(cwd), env=merged_env)
    if proc.returncode != 0:
        print(f"FAIL: {label} exited with {proc.returncode}")
        return proc.returncode
    print(f"PASS: {label}")
    return 0


def git_paths(args: list[str]) -> list[str]:
    proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, check=True)
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def collect_code_files(changed_only: bool, excludes: list[str], suffixes: tuple[str, ...] = CODE_SUFFIXES) -> list[str]:
    if changed_only:
        paths = git_paths(["diff", "--name-only", "--diff-filter=ACMRT", "HEAD"])
        paths.extend(git_paths(["ls-files", "--others", "--exclude-standard"]))
        candidates = list(dict.fromkeys(paths))
    else:
        candidates = git_paths(["ls-files", "--cached", "--others", "--exclude-standard"])
    selected: list[str] = []
    for rel in candidates:
        if not rel.endswith(suffixes) or not rel.startswith(SCAN_ROOTS):
            continue
        if is_excluded(rel, excludes) or not (ROOT / rel).is_file():
            continue
        selected.append(rel)
    return sorted(selected)


def find_cccc() -> str | None:
    env_bin = os.environ.get("CCCC_BIN")
    if env_bin and Path(env_bin).is_file():
        return env_bin
    if DEFAULT_CCCC.is_file():
        return str(DEFAULT_CCCC)
    return shutil.which("cccc")


def walk_cccc_functions(path: str, funcs: list[dict], violations: list[str]) -> None:
    for fn in funcs:
        cog = fn.get("cognitive", 0)
        cyc = fn.get("cyclomatic", 0)
        if cog > MAX_COGNITIVE or cyc > MAX_CYCLOMATIC:
            violations.append(f"{path}:{fn.get('line', 0)} {fn.get('name', '?')} cog={cog} cyc={cyc}")
        children = fn.get("children") or []
        if children:
            walk_cccc_functions(path, children, violations)


def check_cccc(changed_only: bool, excludes: list[str]) -> int:
    cccc_bin = find_cccc()
    if not cccc_bin:
        print("FAIL: cccc binary not found (set CCCC_BIN or install cccc)")
        return 2
    files = collect_code_files(changed_only, excludes, suffixes=CCCC_SUFFIXES)
    if not files:
        print("PASS: cccc complexity (0 matching files)")
        return 0
    violations: list[str] = []
    for start in range(0, len(files), 80):
        batch = files[start:start + 80]
        proc = subprocess.run([cccc_bin, *batch], cwd=str(ROOT), capture_output=True, text=True)
        if not proc.stdout.strip():
            if proc.returncode == 0:
                continue
            print(f"FAIL: cccc produced no output (rc={proc.returncode}): {proc.stderr}")
            return 2
        payload = json.loads(proc.stdout)
        for entry in payload.get("files", []):
            rel = entry.get("path", "").replace("\\", "/")
            if entry.get("parse_error"):
                violations.append(f"{rel}: parse_error")
            walk_cccc_functions(rel, entry.get("functions", []), violations)
    if violations:
        print("FAIL: cccc violations:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"PASS: cccc complexity ({len(files)} files checked, max <= {MAX_COGNITIVE})")
    return 0


def check_loc(excludes: list[str]) -> int:
    tracked = git_paths(["ls-files"])
    violations: list[str] = []
    checked = 0
    for rel in tracked:
        if not rel.endswith(CODE_SUFFIXES) or is_test_path(rel) or is_excluded(rel, excludes):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        checked += 1
        loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        if loc > MAX_LOC:
            violations.append(f"{rel}: {loc} LOC (> {MAX_LOC})")
    if violations:
        print("FAIL: file LOC ceiling exceeded:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"PASS: non-test file LOC ceiling ({checked} files checked, all <= {MAX_LOC})")
    return 0


def find_npm() -> str:
    return shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm") or "npm"


def run_analyst_suite(npm_bin: str) -> int:
    analyst_dir = ROOT / "backend" / "analyst"
    if not (analyst_dir / "node_modules").is_dir():
        rc = run_step("analyst npm ci --ignore-scripts", [npm_bin, "ci", "--ignore-scripts"], cwd=analyst_dir)
        if rc != 0:
            return rc
    return run_step("analyst npm test", [npm_bin, "test"], cwd=analyst_dir)


def run_frontend_suite(npm_bin: str) -> int:
    frontend_dir = ROOT / "frontend"
    if not (frontend_dir / "node_modules").is_dir():
        rc = run_step("frontend npm ci", [npm_bin, "ci"], cwd=frontend_dir)
        if rc != 0:
            return rc
    rc = run_step("frontend typecheck", [npm_bin, "run", "typecheck"], cwd=frontend_dir)
    if rc != 0:
        return rc
    return run_step("frontend npm test", [npm_bin, "test"], cwd=frontend_dir)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    excludes = normalize_excludes(args.exclude_paths)
    npm_bin = find_npm()
    steps = [
        lambda: check_cccc(args.changed, excludes),
        lambda: check_loc(excludes),
        lambda: run_step("no_comments check", [sys.executable, "backend/scripts/no_comments.py"]),
        lambda: run_step("no_comments self-test", [sys.executable, "backend/scripts/no_comments.py", "--self-test"]),
        lambda: run_step("pytest backend/tests", [sys.executable, "-m", "pytest", "backend/tests", "-q"]),
        lambda: run_analyst_suite(npm_bin),
    ]
    if not args.skip_frontend:
        steps.append(lambda: run_frontend_suite(npm_bin))
    for step in steps:
        rc = step()
        if rc != 0:
            return rc
    print("PASS: all gate checks succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
