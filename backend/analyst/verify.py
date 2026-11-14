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
root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="dime-pi-proof-"))
root.mkdir(parents=True, exist_ok=True)


def environment(name):
    home = root / name
    for part in ("home", "temp", "cwd"):
        (home / part).mkdir(parents=True, exist_ok=True)
    return {"SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
            "PATH": os.environ["PATH"],
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


env = environment("runtime")
for source in ("dist/runtime.js", "runtime.test.mjs", "dist/python-tools.js"):
    subprocess.run([node, "--check", str(module / source)],
                   cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)

for name, suite in (("runtime", "runtime.test.mjs"), ("policy", "policy.test.mjs"),
                    ("analyst", "analyst.test.mjs"), ("host", "host.test.mjs"),
                    ("submit-answer", "submit-answer.test.mjs")):
    env = environment(name)
    owned_warehouse(env)
    node_suite(env, suite, "--test")

env = environment("persistence")
subprocess.run([sys.executable, "-B", str(module / "persistence_fixture.py"), "prepare"],
               cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)
node_suite(env, "persistence.test.mjs")
subprocess.run([sys.executable, "-B", str(module / "persistence_fixture.py"), "verify"],
               cwd=env["DIME_PI_TEST_ROOT"], env=env, check=True)
