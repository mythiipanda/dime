import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.sources.draft_picks import future_picks

def curve_season() -> str:
    from shared.tools._core import current_season
    return current_season() or "2026-27"
CURVE_DRAFT_RANGE = (1997, 2015)

def _norm_name(s: object) -> str:
    import re as _re
    import unicodedata as _ud
    return _re.sub(r"[^a-z0-9]", "", "".join(
        c for c in _ud.normalize("NFKD", str(s or ""))
        if not _ud.combining(c)).lower())

def _value_curve(con) -> pl.DataFrame:
    picks = con.execute(
        "select OVERALL_PICK, ROUND_NUMBER, PLAYER_NAME from silver_hist_draft "
        "where SEASON between ? and ?",
        [CURVE_DRAFT_RANGE[0], CURVE_DRAFT_RANGE[1]]).fetchall()
    careers = con.execute(
        "select player_name, sum(mp) as mp, sum(war_total) as war "
        "from silver_raptor_player group by player_name").fetchall()
    career = {_norm_name(name): (float(mp or 0.0), float(war or 0.0))
              for name, mp, war in careers}
    by_slot: dict[int, list[tuple[float, float]]] = {}
    for slot, rnd, name in picks:
        if slot is None:
            continue
        mp, war = career.get(_norm_name(name), (0.0, 0.0))
        by_slot.setdefault(int(slot), []).append((mp, war))
    if not by_slot:
        raise SystemExit("no draft rows in sample range")
    def med(vals: list[float]) -> float:
        vals = sorted(vals)
        n = len(vals)
        mid = n // 2
        return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
    slot_war = {s: [war for _, war in careers_] for s, careers_ in by_slot.items()}
    first = (sum(slot_war.get(1, [1.0])) / len(slot_war.get(1, [1.0]))) or 1.0
    rows = []
    for slot in range(1, max(by_slot) + 1):
        entries = by_slot.get(slot, [(0.0, 0.0)])
        mps = [float(m) for m, _ in entries]
        wars = [float(w) for _, w in entries]
        rnd = 1 if slot <= 30 else 2
        mean_war = sum(wars) / len(wars)
        rows.append({
            "SLOT": slot,
            "ROUND": rnd,
            "N_PLAYERS": len(entries),
            "MEDIAN_CAREER_MP": med(mps),
            "MEDIAN_CAREER_WAR": med(wars),
            "MEAN_CAREER_WAR": round(mean_war, 2),
            "HIT_RATE": round(sum(1 for m in mps if m >= 3000) / len(mps), 4),
            "VALUE_INDEX": round(mean_war / first, 4) if first else 0.0,
        })
    return pl.DataFrame(rows)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-db', type=Path)
    args = parser.parse_args()
    target = args.scratch_db or Path(os.environ.get('DIME_WAREHOUSE') or store.DB_PATH)
    if target.resolve() == store.CANONICAL_DB_PATH:
        parser.error('use --scratch-db or noncanonical DIME_WAREHOUSE')
    if not target.is_file():
        parser.error('scratch warehouse must be an existing copy')
    store.DB_PATH = target.resolve()
    store.LOCK_PATH = store.DB_PATH.parent / '.write.lock'

    res = future_picks()
    if not res.ok or not res.meta.season or res.meta.season == "unknown":
        print(f"abort: future picks unobserved ({res.error or 'no season'})")
        raise SystemExit(1)
    n = store.save_frame("silver_future_picks", res, entity='',
                         replace_season=True)
    print(f"silver_future_picks: {n} rows saved (season {res.meta.season})")

    with store.connect(read_only=True) as con:
        for table in ("silver_hist_draft", "silver_raptor_player"):
            present = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if table not in present:
                print(f"abort: {table} missing from scratch warehouse")
                raise SystemExit(1)
        frame = _value_curve(con)
    curve = FetchResult(
        frame=frame,
        meta=FetchMeta(
            source=("derived:silver_hist_draft+silver_raptor_player "
                    f"{CURVE_DRAFT_RANGE[0]}-{CURVE_DRAFT_RANGE[1]}"),
            season=curve_season()))
    m = store.save_frame("silver_draft_value_curve", curve, entity='',
                         replace_season=True)
    print(f"silver_draft_value_curve: {m} rows saved (season {curve_season()})")

if __name__ == "__main__":
    main()
