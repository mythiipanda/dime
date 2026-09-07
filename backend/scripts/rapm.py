"""RAPM-lite. Ridge regression on possession stints, garbage time excluded.

Design: rows are possessions, columns are players (+1 offense, -1 defense).
Target is points minus league average per possession. Report per 100.

Usage: python -m scripts.rapm --season 2025-26 --min-poss 500
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import polars as pl
from scipy.sparse import csr_matrix
from sklearn.linear_model import RidgeCV

from app import store

OFF = [f"off_player_{i}" for i in range(1, 6)]
DEF = [f"def_player_{i}" for i in range(1, 6)]


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--season", default="2025-26")
    args.add_argument("--min-poss", type=int, default=500)
    ns = args.parse_args()

    con = store.connect()
    try:
        df = pl.from_arrow(con.execute(
            f"""SELECT {', '.join(OFF + DEF)}, points
            FROM silver_hist_possessions
            WHERE _season = ? AND garbage = 0""",
            [ns.season],
        ).to_arrow_table())
    finally:
        con.close()
    print(f"possessions: {df.height}", flush=True)

    players = sorted({str(v) for c in OFF + DEF for v in df[c].to_list() if v})
    idx = {p: i for i, p in enumerate(players)}
    rows, cols, data = [], [], []
    pts = []
    for n, r in enumerate(df.to_dicts()):
        try:
            pts.append(float(r.get("points") or 0))
        except (TypeError, ValueError):
            continue
        for c in OFF:
            if r.get(c):
                rows.append(n)
                cols.append(idx[str(r[c])])
                data.append(1.0)
        for c in DEF:
            if r.get(c):
                rows.append(n)
                cols.append(idx[str(r[c])])
                data.append(-1.0)
    X = csr_matrix((data, (rows, cols)), shape=(len(pts), len(players)))
    y = np.array(pts) - np.mean(pts)
    print("matrix built", flush=True)

    model = RidgeCV(alphas=[500, 1000, 2000, 4000])
    model.fit(X, y)
    print(f"alpha: {model.alpha_}", flush=True)

    counts = np.bincount(np.array(cols), minlength=len(players))
    from nba_api.stats.static import players as _pl

    names = {str(p["id"]): p["full_name"] for p in _pl.get_players()}
    out = []
    for p, i in idx.items():
        if counts[i] >= ns.min_poss:
            out.append({"player_id": p, "name": names.get(p, p),
                        "rapm": round(float(model.coef_[i]) * 100, 2),
                        "possessions": int(counts[i])})
    out.sort(key=lambda r: r["rapm"], reverse=True)
    print("top 10:", [(r["name"], r["rapm"]) for r in out[:10]])
    print("bottom 5:", [(r["name"], r["rapm"]) for r in out[-5:]])

    from app.sources.base import FetchMeta, FetchResult

    frame = pl.DataFrame(out)
    res = FetchResult(frame=frame, meta=FetchMeta(source="rapm-lite", season=ns.season))
    store.save_frame("silver_rapm", res, entity=f"season:{ns.season}")
    print(f"saved {len(out)} players")


if __name__ == "__main__":
    main()
