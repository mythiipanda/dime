import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
DEFAULT_WAREHOUSE = REPO_ROOT / "backend" / "data" / "warehouse.duckdb"


def season_key_type(values: list) -> str | None:
    labels = [v for v in values if isinstance(v, str) and len(v) == 7 and v[4] == "-"]
    if labels:
        return "season_label"
    ints = [v for v in values if isinstance(v, int) and 1900 < v < 2100]
    if ints:
        return "int_year"
    return None


def build_inventory(warehouse: Path) -> dict:
    import duckdb
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'silver\\_%' ESCAPE '\\' ORDER BY 1").fetchall()]
        inventory: dict[str, dict] = {}
        for table in tables:
            columns = [r[1] for r in con.execute(
                f"pragma table_info('{table}')").fetchall()]
            if "_season" not in columns:
                continue
            rows = con.execute(
                f'SELECT "_season", count(*) FROM "{table}" '
                'GROUP BY "_season"').fetchall()
            seasons = {str(key): count for key, count in rows
                       if key is not None}
            if seasons:
                inventory[table] = {"key_column": "_season", "seasons": seasons}
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "warehouse": os.path.basename(str(warehouse)),
            "tables": inventory,
        }
    finally:
        con.close()


def main() -> int:
    warehouse = Path(os.environ.get("DIME_WAREHOUSE", str(DEFAULT_WAREHOUSE)))
    if not warehouse.is_file():
        print(f"warehouse missing: {warehouse}")
        return 2
    out = warehouse.parent / "warehouse-inventory.json"
    inventory = build_inventory(warehouse)
    out.write_text(json.dumps(inventory, indent=2, sort_keys=True))
    total = sum(len(entry["seasons"]) for entry in inventory["tables"].values())
    print(f"wrote {out}: {len(inventory['tables'])} tables, "
          f"{total} table-season cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
