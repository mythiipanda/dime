"""Launch each meaningful product fixture in a clean environment before imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from configuration import worker_environment

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
       "DIME_CONVERSATION_STORE": str(root / "cwd/conversations.sqlite"),
       "DIME_PI_SOURCES_DIR": str(root / "cwd/sources"),
       "DIME_PI_PRIVATE_DIR": str(root / "cwd/private")}
if os.environ.get("DIME_PI_TEST_DEPENDENCIES"):
    env["PYTHONPATH"] = os.pathsep.join((os.environ["DIME_PI_TEST_DEPENDENCIES"], str(module.parent)))
if target == "pytest":
    env.setdefault("PYTHONPATH", str(module.parent))
    raise SystemExit(subprocess.run([sys.executable, "-B", "-m", "pytest", *sys.argv[3:]],
                                   cwd=module.parents[1], env=env).returncode)
if target == "packaging":
    raise SystemExit(subprocess.run([sys.executable, "-B", str(module / "packaging_fixture.py")],
                                   cwd=root / "cwd", env=env).returncode)
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
raise SystemExit(subprocess.run([sys.executable, "-B", str(module / ("route_test.py" if target.startswith("route_") else "product_session_test.py")),
                                ("RouteTest." + target if target.startswith("route_") else "ProductSessionTest." + target)], cwd=root / "cwd", env=env).returncode)
