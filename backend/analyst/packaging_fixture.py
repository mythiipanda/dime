"""Static image boundary and local SDK assets; never builds a warehouse image."""
import json
from pathlib import Path
import shutil
import subprocess

module = Path(__file__).resolve().parent
image = (module.parent / "Dockerfile").read_text()
packaging, runtime = image.split("FROM python:3.11-slim-bookworm AS runtime", 1)
assert "FROM node:22.19.0-bookworm-slim AS analyst-deps" in packaging
assert "npm ci --omit=dev --ignore-scripts" in packaging
assert "analyst/package-lock.json" in packaging
assert "COPY analyst/*.mjs analyst/*.py ./" in packaging
assert "warehouse" not in packaging
assert "COPY --from=analyst-deps /usr/local/bin/node /usr/local/bin/node" in runtime
assert "COPY --from=analyst-deps /analyst /srv/analyst" in runtime
lock = json.loads((module / "package-lock.json").read_text())
assert lock["packages"]["node_modules/@earendil-works/pi-coding-agent"]["version"] == "1.4.0"
subprocess.run([shutil.which("node"), "--input-type=module", "-e",
                "await import(" + json.dumps((module / "runtime.mjs").as_uri()) + ")"], check=True)
print("Static Node image/assets/lock boundary and local pinned SDK import passed; no image built")
