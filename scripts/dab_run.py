import argparse
import datetime
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
    parser.add_argument("--limit", type=int, default=None)
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
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-20:]:
        print(redact(line), file=sys.stderr)


def wait_health(port: int, host: subprocess.Popen, log_file: Path) -> dict | None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + 120.0
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            if host.poll() is not None:
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
    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    cmd.extend([
        "--timeout-s", str(args.timeout_s),
        "--judge-model", args.judge_model,
        "--judge-base-url", args.judge_base_url,
        "--out-dir", f"runs/{args.out_name}",
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


def dab_root() -> Path:
    from_env = os.environ.get("DIME_DAB_ROOT")
    if from_env:
        return Path(from_env)
    sibling = ROOT.parent / "dime-internal" / "benchmarks" / "dab-v1"
    if sibling.is_dir():
        return sibling
    return Path("C:/Users/15980/Downloads/dime/dime-internal/benchmarks/dab-v1")


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


def terminate_host(host: subprocess.Popen, keep: bool) -> None:
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
        "PORT": str(args.port),
    })
    if provider:
        env[f"DIME_ENABLE_{provider.upper()}"] = "true"

    held_by = listener_pid(args.port)
    if held_by is not None:
        print(f"port {args.port} already listening, held by pid {held_by}", file=sys.stderr)
        return 1

    manifest_dir = Path(tempfile.mkdtemp(prefix="dab-manifest-"))
    manifest_path = manifest_dir / "asset-manifest.json"
    env["DIME_EXPECTED_ASSET_MANIFEST"] = str(manifest_path)
    if not generate_manifest(env, manifest_path):
        return 1
    print(f"asset manifest: {manifest_path}")

    log_file = log_path_for(args)
    print(f"host log: {log_file}")
    host = boot_host(env, log_file)
    ok = True
    try:
        providers = wait_health(args.port, host, log_file)
        if providers is None:
            return 1
        if provider and providers.get(provider) is not True:
            print(f"provider {provider} is not enabled in health providers map", file=sys.stderr)
            return 1
        print(f"provider {provider}: true")
        if run_eval(eval_command(args), env) != 0:
            print("eval subprocess failed", file=sys.stderr)
            ok = False
        if not report_results(args):
            ok = False
    finally:
        terminate_host(host, args.keep_host)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
