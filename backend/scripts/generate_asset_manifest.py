"""Generate the expected startup asset manifest (promotion-time binding).

Run inside the built backend image after every baked asset exists
(warehouse, code, prompts, snapshots). Writes the JSON file that
DIME_EXPECTED_ASSET_MANIFEST must point at so the lifespan preflight in
v2/api/routes.py can verify the running process matches what was promoted.

Usage: python scripts/generate_asset_manifest.py /srv/manifest/expected_asset_manifest.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v2.api.routes import runtime_asset_manifest


def main() -> None:
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = runtime_asset_manifest().as_dict()
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote expected asset manifest: {out} "
          f"(revision={manifest['revision']})")


if __name__ == "__main__":
    main()
