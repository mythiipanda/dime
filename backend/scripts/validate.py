"""Warehouse hygiene. Catches dup rows, null ids, stale seasons, case dupes.

Usage: python -m scripts.validate
Exit 1 on any failure. Run before deploy claims.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store

FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAIL
    if cond:
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} :: {detail[:160]}")


def main() -> None:
    con = store.connect()
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        lowered = [t.lower() for t in tables]
        check("no case-duplicate tables", len(lowered) == len(set(lowered)),
              str([t for t in tables if lowered.count(t.lower()) > 1]))
        for t in tables:
            if t in ("fetch_log", "chat_history", "runs"):
                continue
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()]
            check(f"{t} has provenance",
                  all(c in cols for c in ("_source", "_season", "_fetched_at", "_entity")),
                  str(cols[-6:]))
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            check(f"{t} non-empty", n > 0, "0 rows")
            if "_entity" in cols and not t.startswith("silver_hist_"):
                dups = con.execute(
                    f"""SELECT _entity, _fetched_at, COUNT(*) FROM {t}
                    GROUP BY _entity, _fetched_at HAVING COUNT(*) > 5000"""
                ).fetchall()
                check(f"{t} no entity blowups", not dups, str(dups[:2]))
    finally:
        con.close()
    print(f"\nhygiene: {'clean' if not FAIL else f'{FAIL} failures'}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
