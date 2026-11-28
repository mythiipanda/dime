import argparse
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
HOST_JS = ROOT / "backend" / "analyst" / "dist" / "host.js"
ENV_FILE = ROOT / "backend" / ".env"
WAREHOUSE = ROOT / "backend" / "data" / "warehouse-runtime.duckdb"
RUNNER = Path("scripts/run_dab.py")
HEADLINES = (
    "total_tasks",
    "hallucination_gated_all_pass_rate",
    "raw_all_pass_rate",
    "weighted_criterion_pass_rate",
    "deterministic_anchor_accuracy",
    "artifact_completeness_rate",
)
SECRETS: set[str] = set()


def redact(text: str) -> str:
    for value in SECRETS:
        text = text.replace(value, "***")
    return text


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-command DAB run with pinned model and judge.")
    parser.add_argument("--model", default="reflection:Beam-1.0-501B-A23B")
    parser.add_argument("--judge-model", default="gemini-3-flash-preview")
    parser.add_argument("--judge-base-url", default="https://generativelanguage.googleapis.com/v1beta/openai/")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--data-dir", default=None, help="Override the benchmark task data directory (e.g. the artifact-lane scratch dir)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tasks", default=None, help="Comma-separated dev task IDs for a spot check")
    parser.add_argument("--workers", type=int, default=1, help="Run DAB adapter tasks concurrently")
    parser.add_argument("--no-llm-judge", action="store_true", help="Score deterministic anchors/artifacts only")
    parser.add_argument("--save-history", action="store_true", help="Save the judged run into dime-internal DAB history")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout-s", type=float, default=420.0)
    parser.add_argument("--out-name", default=None)
    parser.add_argument("--host-log", default=None)
    parser.add_argument("--keep-host", action="store_true")
    return parser.parse_args(argv)


def model_slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()


def default_out_name(model: str) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{model_slug(model)}"


def provider_of(model: str) -> str:
    return model.split(":", 1)[0] if ":" in model else ""


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        name = key.strip()
        if name:
            values[name] = value.strip()
    return values


def collect_secrets(parsed: dict[str, str]) -> None:
    for name, value in {**os.environ, **parsed}.items():
        if re.search(r"KEY|TOKEN|SECRET|PASSWORD", name, re.I) and len(value) >= 4:
            SECRETS.add(value)


def listener_pid(port: int) -> str | None:
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[1].endswith(f":{port}"):
                    return parts[4]
    except OSError:
        pass
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    except OSError:
        return "unknown"
    return None


def free_port(start: int, span: int = 50) -> int | None:
    for candidate in range(start, start + span):
        if listener_pid(candidate) is None:
            return candidate
    return None


def port_owner_pid(port: int) -> int | None:
    try:
        proc = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        match = re.search(r"pid=(\d+)", proc.stdout)
        if match:
            return int(match.group(1))
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[1].endswith(f":{port}"):
                    pid = parts[4]
                    if pid.isdigit():
                        return int(pid)
    except OSError:
        pass
    return None


def proc_cwd(pid: int) -> Path | None:
    try:
        return Path(os.readlink(f"/proc/{pid}/cwd")).resolve()
    except OSError:
        return None


def pid_is_descendant(pid: int, ancestor: int) -> bool:
    for _ in range(32):
        if pid == ancestor:
            return True
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="ignore")
            pid = int(stat.rpartition(")")[2].split()[1])
        except (OSError, IndexError, ValueError):
            return False
    return False


def host_matches_worktree(pid: int) -> bool:
    cwd = proc_cwd(pid)
    return cwd is not None and cwd == ROOT


def log_path_for(args: argparse.Namespace) -> Path:
    if args.host_log:
        return Path(args.host_log)
    return Path(tempfile.gettempdir()) / f"dab-host-{os.getpid()}-{args.port}.log"


def generate_manifest(env: dict[str, str], path: Path) -> bool:
    proc = subprocess.run(
        ["node", str(HOST_JS), "manifest", str(path)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print("manifest generation failed:", file=sys.stderr)
        print(redact(proc.stderr.strip()), file=sys.stderr)
        return False
    return True


STATIC_PROVIDER_URLS = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "amd": "https://developer.amd.com.cn/radeon/api/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def preflight_lane(model: str, parsed: dict[str, str]) -> None:
    provider = provider_of(model)
    if not provider:
        return
    upper = provider.upper()
    key = parsed.get(f"{upper}_RELAY_API_KEY") or parsed.get(f"{upper}_API_KEY")
    base = parsed.get(f"{upper}_RELAY_BASE_URL") or STATIC_PROVIDER_URLS.get(provider, "")
    if not key or not base:
        return
    _, _, model_id = model.partition(":")
    body = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
        "max_tokens": 8,
    }).encode()
    samples = []
    for _ in range(2):
        start = time.time()
        try:
            req = httpx.Request(
                "POST", f"{base.rstrip('/')}/chat/completions",
                content=body,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            with httpx.Client(timeout=30.0) as client:
                resp = client.send(req)
                resp.read()
            if resp.status_code < 500:
                samples.append(time.time() - start)
        except Exception:
            pass
        time.sleep(1)
    if not samples:
        print(f"preflight WARNING: lane {provider} unreachable — probe completions all failed; "
              f"measurement legs in this state risk lane-state contamination", flush=True)
        return
    median = sorted(samples)[len(samples) // 2]
    print(f"preflight: lane {provider} probe round-trip median {median:.1f}s", flush=True)
    if median > 4.0:
        print(f"preflight WARNING: lane {provider} degraded — tiny-probe median {median:.1f}s exceeds 4s; "
              f"historically healthy lanes probe at 1-3s and per-tool-call latency inflates proportionally. "
              f"Timeout-capped deaths in this state measure lane survival, not model decisions.", flush=True)


def boot_host(env: dict[str, str], log_file: Path) -> subprocess.Popen | None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as handle:
        return subprocess.Popen(
            ["node", str(HOST_JS)],
            cwd=str(ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )


def tail_log(log_file: Path) -> None:
    if not log_file.is_file():
        return
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-20:]:
        print(redact(line), file=sys.stderr)


def wait_health(port: int, host: subprocess.Popen | None, log_file: Path) -> dict | None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + 120.0
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            if host is not None and host.poll() is not None:
                print("host exited before health became ready", file=sys.stderr)
                tail_log(log_file)
                return None
            try:
                response = client.get(url)
                if response.status_code == 200:
                    payload = response.json()
                    if payload.get("ok") is True:
                        return payload.get("providers", {})
            except Exception:
                pass
            time.sleep(1.0)
    print("host health deadline exceeded (120s)", file=sys.stderr)
    tail_log(log_file)
    return None


def eval_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(RUNNER),
        "eval",
        "--adapter", "dime_http",
        "--base-url", f"http://127.0.0.1:{args.port}",
        "--split", args.split,
    ]
    if args.data_dir:
        cmd.extend(["--data-dir", args.data_dir])
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.tasks:
        cmd.extend(["--tasks", args.tasks])
    cmd.extend(["--workers", str(args.workers)])
    cmd.extend([
        "--timeout-s", str(args.timeout_s),
        "--out-dir", f"runs/{args.out_name}",
    ])
    if args.no_llm_judge:
        cmd.append("--no-llm-judge")
    else:
        cmd.extend([
            "--judge-model", args.judge_model,
            "--judge-base-url", args.judge_base_url,
        ])
    return cmd


def run_eval(cmd: list[str], env: dict[str, str]) -> int:
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout:
        print(redact(line.rstrip("\n")), flush=True)
    return proc.wait()


def declared_tables() -> list[str]:
    path = ROOT / "backend" / "shared" / "tools" / "league" / "sql_schema.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "_SQL_TABLES" for t in node.targets):
            return list(ast.literal_eval(node.value))
    return []


def verify_runtime_warehouse() -> tuple[list[str], int]:
    if not WAREHOUSE.is_file():
        return [f"runtime warehouse missing: {WAREHOUSE}"], 0
    try:
        import duckdb
        con = duckdb.connect(str(WAREHOUSE), read_only=True)
        try:
            present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
    except Exception as exc:
        return [f"runtime warehouse unreadable: {exc}"], 0
    declared = set(declared_tables())
    missing = sorted(declared - present)
    if missing:
        shown = ", ".join(missing[:10])
        more = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
        return [
            f"runtime warehouse lacks {len(missing)} declared table(s): "
            f"{shown}{more}; refresh backend/data/warehouse.duckdb via "
            "scripts/fetch-data.sh and relink warehouse-runtime.duckdb"
        ], len(present)
    return [], len(present)


def warehouse_metadata() -> dict[str, object]:
    digest = hashlib.sha256()
    with WAREHOUSE.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    stat = WAREHOUSE.stat()
    return {
        "warehouse_file": WAREHOUSE.name,
        "warehouse_sha256": digest.hexdigest(),
        "warehouse_size_bytes": stat.st_size,
        "warehouse_mtime_utc": datetime.datetime.fromtimestamp(
            stat.st_mtime, datetime.timezone.utc).isoformat(),
    }


def dab_root() -> Path:
    from_env = os.environ.get("DIME_DAB_ROOT")
    if from_env:
        return Path(from_env)
    sibling = ROOT.parent / "dime-internal" / "benchmarks" / "dab-v1"
    if sibling.is_dir():
        return sibling
    return Path("C:/Users/15980/Downloads/dime/dime-internal/benchmarks/dab-v1")


def save_history(args: argparse.Namespace) -> bool:
    root = dab_root()
    saver = root / "save_run.py"
    run_dir = root / "runs" / args.out_name
    if not saver.is_file():
        print(f"DAB save_run.py not found: {saver}", file=sys.stderr)
        return False
    proc = subprocess.run(
        [sys.executable, str(saver), str(run_dir), "--name", args.out_name],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print(redact(proc.stderr.strip()), file=sys.stderr)
        return False
    print(proc.stdout.strip())
    return True


def report_results(args: argparse.Namespace) -> bool:
    path = dab_root() / "runs" / args.out_name / "results.json"
    if not path.is_file():
        print(f"results.json missing: {path}", file=sys.stderr)
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    for name in HEADLINES:
        print(f"{name}: {summary.get(name)}")
    print(f"failure_clusters: {json.dumps(summary.get('failure_clusters', {}), ensure_ascii=False)}")
    print(f"results.json: {path.resolve()}")
    return True


def terminate_host(host: subprocess.Popen | None, keep: bool) -> None:
    if host is None:
        print("reused host left running")
        return
    if keep:
        print(f"host left running pid {host.pid}")
        return
    host.terminate()
    try:
        host.wait(timeout=10)
    except subprocess.TimeoutExpired:
        host.kill()
        host.wait()
    print("host terminated")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    model = args.model
    args.out_name = args.out_name or default_out_name(model)
    provider = provider_of(model)
    print(f"pinned model: {model}")
    print(f"judge model: {args.judge_model}")
    print(f"port: {args.port}  out-name: {args.out_name}")

    parsed = load_env(ENV_FILE)
    collect_secrets(parsed)
    os.environ.update(parsed)

    env = os.environ.copy()
    env.update({
        "DIME_V2_MODEL": model,
        "DIME_WAREHOUSE": str(WAREHOUSE),
        "DIME_PI_PYTHON": sys.executable,
        "DIME_TRACE_TOOL_RESULTS": "1",
        "PORT": str(args.port),
        "DIME_V2_RUN_TIMEOUT_S": str(max(60.0, args.timeout_s - 30.0)),
    })
    if provider:
        env[f"DIME_ENABLE_{provider.upper()}"] = "true"

    preflight_lane(model, parsed)

    reuse_pid: int | None = None
    held_by = listener_pid(args.port)
    if held_by is not None:
        owner = port_owner_pid(args.port)
        if owner is not None and host_matches_worktree(owner):
            reuse_pid = owner
            print(f"port {args.port} already serves this worktree (pid {owner}); reusing it")
        else:
            detail = f"pid {owner} cwd {proc_cwd(owner)}" if owner is not None else "pid unknown"
            print(f"port {args.port} already listening, held by foreign host ({detail}); refusing to drift ports — kill the stale host or pass a free port", file=sys.stderr)
            return 1

    warehouse_errors, warehouse_tables = verify_runtime_warehouse()
    if warehouse_errors:
        for problem in warehouse_errors:
            print(f"FAILED: {problem}", file=sys.stderr)
        return 1
    print(f"runtime warehouse ok: {WAREHOUSE} ({warehouse_tables} tables)")
    run_metadata = {
        "model": model,
        "judge_model": args.judge_model,
        "split": args.split,
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **warehouse_metadata(),
    }

    manifest_dir = Path(tempfile.mkdtemp(prefix="dab-manifest-"))
    manifest_path = manifest_dir / "asset-manifest.json"
    env["DIME_EXPECTED_ASSET_MANIFEST"] = str(manifest_path)
    if not generate_manifest(env, manifest_path):
        return 1
    print(f"asset manifest: {manifest_path}")

    log_file = log_path_for(args)
    host: subprocess.Popen | None = None
    if reuse_pid is None:
        print(f"host log: {log_file}")
        host = boot_host(env, log_file)
    ok = True
    try:
        providers = wait_health(args.port, host, log_file)
        if providers is None:
            return 1
        owner = port_owner_pid(args.port)
        if reuse_pid is not None:
            if owner != reuse_pid:
                print(f"port {args.port} owner changed mid-run; refusing to evaluate", file=sys.stderr)
                return 1
        elif owner is not None and host is not None and owner != host.pid and not pid_is_descendant(owner, host.pid):
            print(
                f"port {args.port} is served by foreign pid {owner} "
                f"(cwd {proc_cwd(owner)}), not spawned host pid {host.pid}; "
                "refusing to evaluate",
                file=sys.stderr,
            )
            return 1
        if provider and providers.get(provider) is not True:
            print(f"provider {provider} is not enabled in health providers map", file=sys.stderr)
            return 1
        print(f"provider {provider}: true")
        if run_eval(eval_command(args), env) != 0:
            print("eval subprocess failed", file=sys.stderr)
            ok = False
        run_dir = dab_root() / "runs" / args.out_name
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run-metadata.json").write_text(
            json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8")
        if not report_results(args):
            ok = False
        elif args.save_history and not save_history(args):
            ok = False
    finally:
        terminate_host(host, args.keep_host)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
