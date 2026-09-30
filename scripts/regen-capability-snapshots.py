#!/usr/bin/env python3
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from v2.argument_schemas import canonical_hash, compile_capability_catalog
from v2.runtime.assembly import capability_catalog


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def main():
    root = pathlib.Path(__file__).resolve().parents[1] / "backend" / "v2" / "capability_snapshots"
    live = capability_catalog()
    compiled = compile_capability_catalog(live)
    dump(root / "catalog.source.json", live)
    dump(root / "catalog.compiled.json", compiled)
    for row in compiled["capabilities"]:
        dump(root / (row["capability_id"] + ".json"), row)
    files = {}
    for path in sorted(root.glob("*.json")):
        if path.name in {"manifest.json"}:
            continue
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    dump(root / "manifest.json", {
        "catalog_canonical_sha256": canonical_hash(live),
        "compiled_canonical_sha256": canonical_hash(compiled),
        "count": len(compiled["capabilities"]),
        "files": files,
    })


if __name__ == "__main__":
    main()
