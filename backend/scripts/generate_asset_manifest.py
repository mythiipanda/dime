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
