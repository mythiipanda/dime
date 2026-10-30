"""Launch each meaningful product fixture in a clean environment before imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

module = Path(__file__).resolve().parent
root = Path(sys.argv[1]).resolve()
target = sys.argv[2]
root.mkdir(parents=True, exist_ok=target != "prepare")
for name in ("home", "temp", "cwd"):
    (root / name).mkdir(exist_ok=True)
env = {"SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
       "PATH": str(Path(shutil.which("node")).parent),
       "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
       "TEMP": str(root / "temp"), "TMP": str(root / "temp"),
       "PI_OFFLINE": "1", "DIME_PI_TEST_ROOT": str(root / "cwd"),
       "DIME_WAREHOUSE": str(root / "cwd" / "owned.duckdb"),
       "DIME_STATE_DB": str(root / "cwd" / "state.duckdb"),
       "PYTHONDONTWRITEBYTECODE": "1"}
if target == "prepare":
    subprocess.run([sys.executable, "-B", str(module / "python_fixture.py")],
                   cwd=root / "cwd", env=env, check=True)
    raise SystemExit(0)
if target == "frontend":
    loader = Path(sys.argv[3]).resolve().as_uri()
    raise SystemExit(subprocess.run([shutil.which("node"), "--import", loader,
                                    str(module / "frontend_fixture.mjs"), str(root / "cwd")],
                                   cwd=root / "cwd", env=env).returncode)
raise SystemExit(subprocess.run([sys.executable, "-B", str(module / "product_session_test.py"),
                                "ProductSessionTest." + target], cwd=root / "cwd", env=env).returncode)
