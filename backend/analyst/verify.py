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
for name in ("home", "temp", "cwd"):
    (root / name).mkdir(exist_ok=True)
env = {"SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
       "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
       "TEMP": str(root / "temp"), "TMP": str(root / "temp"),
       "PI_OFFLINE": "1", "DIME_PI_TEST_ROOT": str(root / "cwd"),
       "DIME_PI_PYTHON": sys.executable,
       "DIME_WAREHOUSE": str(root / "cwd" / "owned.duckdb"),
       "PYTHONDONTWRITEBYTECODE": "1"}
subprocess.run([sys.executable, "-B", str(module / "python_fixture.py")],
               cwd=root / "cwd", env=env, check=True)
for source in ("runtime.mjs", "runtime.test.mjs", "python-tools.mjs"):
    subprocess.run([node, "--check", str(module / source)], cwd=root / "cwd", env=env, check=True)
raise SystemExit(subprocess.run([node, "--test", str(module / "runtime.test.mjs")], cwd=root / "cwd", env=env).returncode)
