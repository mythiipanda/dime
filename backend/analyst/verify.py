import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

module = Path(__file__).resolve().parent
node = shutil.which("node")
if not node:
    raise SystemExit("Node >=22.19.0 is required")
owned_root = len(sys.argv) < 2
root = Path(sys.argv[1]).resolve() if not owned_root else Path(tempfile.mkdtemp(prefix="dime-pi-proof-"))
root.mkdir(parents=True, exist_ok=True)


def system_root():
    for name in ("SystemRoot", "WINDIR"):
        value = os.environ.get(name)
        if value:
            return value
    return "C:\\Windows" if os.name == "nt" else "/"


def environment(name):
    home = root / name
    for part in ("home", "temp", "cwd"):
        (home / part).mkdir(parents=True, exist_ok=True)
    windows_root = system_root()
    return {"SystemRoot": windows_root, "WINDIR": windows_root,
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home / "home"), "USERPROFILE": str(home / "home"),
            "TEMP": str(home / "temp"), "TMP": str(home / "temp"),
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "POLARS_MAX_THREADS": "1",
            "PI_OFFLINE": "1", "DIME_PI_TEST_ROOT": str(home / "cwd"),
            "DIME_PI_PYTHON": sys.executable,
            "DIME_WAREHOUSE": str(home / "cwd" / "owned.duckdb"),
            "DIME_STATE_DB": str(home / "cwd" / "state.duckdb"),
            "DIME_CONVERSATION_STORE": str(home / "cwd" / "conversations.sqlite"),
            "DIME_PROJECT_STORE": str(home / "cwd" / "projects.sqlite"),
            "DIME_WORKSPACE_STORE": str(home / "cwd" / "workspaces.sqlite"),
            "DIME_PI_SOURCES_DIR": str(home / "cwd" / "sources"),
            "DIME_PI_PRIVATE_DIR": str(home / "cwd" / "private"),
            "PYTHONPATH": str(module.parent),
            "PYTHONDONTWRITEBYTECODE": "1"}


def owned_warehouse(env):
    subprocess.run([sys.executable, "-B", str(module / "python_fixture.py")],
                   cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)


def node_suite(env, name, *flags):
    code = subprocess.run([node, *flags, str(module / name)],
                          cwd=env["DIME_PI_TEST_ROOT"], env=env).returncode
    if code:
        raise SystemExit(code)


def run():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit("npm is required to build the analyst host before verifying")
    subprocess.run([npm, "run", "build"], cwd=module, check=True)

    env = environment("runtime")
    for source in ("dist/runtime.js", "runtime.test.mjs", "dist/python-tools.js"):
        subprocess.run([node, "--check", str(module / source)],
                       cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)

    for name, suite in (("runtime", "runtime.test.mjs"), ("policy", "policy.test.mjs"),
                        ("analyst", "analyst.test.mjs"), ("host", "host.test.mjs"),
                        ("submit-answer", "submit-answer.test.mjs"),
                        ("verify-answer", "verify-answer.test.mjs"),
                        ("uvarc-guard", "uvarc-guard.test.mjs"),
                        ("nim-guard", "nim-guard.test.mjs"),
                        ("prompt-map", "prompt-map.test.mjs"),
                        ("view-context", "view-context.test.mjs"),
                        ("construction", "construction.test.mjs")):
        env = environment(name)
        owned_warehouse(env)
        node_suite(env, suite, "--test")

    node_suite(environment("boards-routes"), "boards-route.test.mjs", "--test")
    node_suite(environment("objects-routes"), "objects-route.test.mjs", "--test")
    node_suite(environment("route-table"), "route-table.test.mjs", "--test")

    env = environment("persistence")
    subprocess.run([sys.executable, "-B", str(module / "persistence_fixture.py"), "prepare"],
                   cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)
    node_suite(env, "persistence.test.mjs")
    subprocess.run([sys.executable, "-B", str(module / "persistence_fixture.py"), "verify"],
                   cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)


try:
    run()
except BaseException:
    if owned_root:
        print(f"analyst run failed; temp root kept for diagnosis: {root}", file=sys.stderr)
    raise
if owned_root:
    shutil.rmtree(root, ignore_errors=True)
    if root.exists():
        print(f"analyst run finished; temp root not removed: {root}", file=sys.stderr)
