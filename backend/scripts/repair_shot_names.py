import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from scripts.seed_history import full_name_map


def repair(con) -> int:
    names = full_name_map()
    if not names:
        print("abort: no player name map available")
        raise SystemExit(1)
    con.execute("CREATE OR REPLACE TEMP TABLE shot_name_map "
                "(person_id BIGINT, full_name VARCHAR)")
    con.executemany("INSERT INTO shot_name_map VALUES (?, ?)",
                    [(pid, name) for pid, name in names.items()])
    stale = con.execute(
        "select count(*) from silver_hist_shots s join shot_name_map m "
        "on s.person_id = m.person_id where s.player_name <> m.full_name"
    ).fetchone()[0]
    con.execute(
        "update silver_hist_shots s set player_name = m.full_name "
        "from shot_name_map m where s.person_id = m.person_id")
    return int(stale)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-db', type=Path)
    args = parser.parse_args()
    target = args.scratch_db or Path(
        os.environ.get('DIME_WAREHOUSE') or store.DB_PATH)
    if target.resolve() == store.CANONICAL_DB_PATH:
        parser.error('use --scratch-db or noncanonical DIME_WAREHOUSE')
    if not target.is_file():
        parser.error('scratch warehouse must be an existing copy')
    store.DB_PATH = target.resolve()
    store.LOCK_PATH = store.DB_PATH.parent / '.write.lock'
    with store.connect() as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if 'silver_hist_shots' not in tables:
            print("abort: silver_hist_shots missing from scratch warehouse")
            raise SystemExit(1)
        n = repair(con)
    print(f"silver_hist_shots: {n} player_name rows repaired to full names")


if __name__ == "__main__":
    main()
