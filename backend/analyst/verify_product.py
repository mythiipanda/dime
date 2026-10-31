"""Launch each meaningful product fixture in a clean environment before imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

def worker_environment():
    names=("SystemRoot","WINDIR","PATH","LANG","SSL_CERT_FILE","SSL_CERT_DIR")
    return {**{name:os.environ[name] for name in names if name in os.environ},"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","POLARS_MAX_THREADS":"1"}

module = Path(__file__).resolve().parent
root = Path(sys.argv[1]).resolve()
target = sys.argv[2]
root.mkdir(parents=True, exist_ok=target != "prepare")
for name in ("home", "temp", "cwd"):
    (root / name).mkdir(exist_ok=True)
env = {**worker_environment(), "SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
       "PATH": str(Path(shutil.which("node")).parent),
       "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
       "TEMP": str(root / "temp"), "TMP": str(root / "temp"),
       "PI_OFFLINE": "1", "DIME_PI_TEST_ROOT": str(root / "cwd"),
       "DIME_WAREHOUSE": str(root / "cwd" / "owned.duckdb"),
       "DIME_STATE_DB": str(root / "cwd" / "state.duckdb"),
       "PYTHONDONTWRITEBYTECODE": "1", "DIME_RUNTIME_V2": "on",
       "REFLECTION_API_KEY": "synthetic-not-a-secret", "DIME_ENABLE_REFLECTION": "true",
       "DIME_PROJECT_STORE": str(root / "cwd/projects.sqlite"),
       "DIME_WORKSPACE_STORE": str(root / "cwd/workspaces.sqlite"),
       "DIME_CONVERSATION_STORE": str(root / "cwd/conversations.sqlite"),
       "DIME_PI_SOURCES_DIR": str(root / "cwd/sources"),
       "DIME_PI_PRIVATE_DIR": str(root / "cwd/private")}
if os.environ.get("DIME_PI_TEST_DEPENDENCIES"):
    env["PYTHONPATH"] = os.pathsep.join((os.environ["DIME_PI_TEST_DEPENDENCIES"], str(module.parent)))
env.setdefault("PYTHONPATH", str(module.parent))
if target == "pytest":
    raise SystemExit(subprocess.run([sys.executable, "-B", "-m", "pytest", *sys.argv[3:]],
                                   cwd=module.parents[1], env=env).returncode)
if target == "fixture":
    raise SystemExit(subprocess.run([sys.executable,"-B",sys.argv[3]],cwd=root/"cwd",env=env).returncode)
if target == "entrypoint":
    raise SystemExit(subprocess.run([sys.executable,"-B",str(module/"entrypoint_fixture.py")],cwd=root/"cwd",env=env).returncode)
if target == "persistence":
    for command in ([sys.executable,"-B",str(module/"persistence_fixture.py"),"prepare"],[shutil.which("node"),str(module/"persistence.test.mjs")],[sys.executable,"-B",str(module/"persistence_fixture.py"),"verify"]):
        subprocess.run(command,cwd=root/"cwd",env=env,check=True)
    raise SystemExit(0)
if target == "policy":
    raise SystemExit(subprocess.run([shutil.which("node"),"--test",str(module/"policy.test.mjs")],cwd=root/"cwd",env=env).returncode)
if target == "packaging":
    raise SystemExit(subprocess.run([sys.executable, "-B", str(module / "packaging_fixture.py")],
                                   cwd=root / "cwd", env=env).returncode)
if target in {"inprocess", "host"}:
    if target == "host": env["DIME_HOST_TEST_STAGE"] = sys.argv[3] if len(sys.argv) > 3 else "normal"
    env["DIME_PI_PYTHON"] = sys.executable
    raise SystemExit(subprocess.run([shutil.which("node"), "--test", *(["--import", (module.parents[1] / "frontend/node_modules/tsx/dist/loader.mjs").as_uri()] if target == "host" and env.get("DIME_HOST_TEST_STAGE")=="frontend" else []), str(module / ("host.test.mjs" if target == "host" else "analyst.test.mjs"))],
                                   cwd=root / "cwd", env=env).returncode)
if target == "contracts":
    env["DIME_PI_PYTHON"] = sys.executable
    raise SystemExit(subprocess.run([shutil.which("node"),str(module/"route-contract.test.mjs"),sys.argv[3]],cwd=root/"cwd",env=env).returncode)
if target == "prepare":
    subprocess.run([sys.executable, "-B", str(module / "python_fixture.py")],
                   cwd=root / "cwd", env=env, check=True)
    raise SystemExit(0)
if target.startswith("consumer_"):
    names = {"consumer_api": "api", "consumer_evidence": "evidence", "consumer_stream": "dime-stream"}
    loader = Path(sys.argv[3]).resolve().as_uri()
    frontend = module.parents[1] / "frontend"
    raise SystemExit(subprocess.run([shutil.which("node"), "--import", loader,
                                    "--test", str(frontend / "lib" / (names[target] + ".test.ts"))],
                                   cwd=frontend, env=env).returncode)
if target == "frontend":
    env["TSX_TSCONFIG_PATH"] = str(module.parents[1] / "frontend/tsconfig.json")
    loader = Path(sys.argv[3]).resolve().as_uri()
    raise SystemExit(subprocess.run([shutil.which("node"), "--import", loader,
                                    str(module / "frontend_fixture.mjs"), str(root / "cwd")],
                                   cwd=root / "cwd", env=env).returncode)
raise SystemExit("Unknown verification target")
