"""Multi-season RAPM priors. Ridge per season, never the current season.

Reads non-garbage stints from silver_hist_possessions for end-years
2022..2025 (labels 2021-22..2024-25) and writes one row per qualifying
player per season to the NEW table silver_rapm_prior. Never touches
silver_rapm and never computes end-year 2026 (2025-26): the current
season stays a live estimate, not its own prior.

Shrinkage, in one place. The ridge penalty shrinks every coefficient
toward zero, which is league average because targets are demeaned
points per possession. Larger alphas mean stronger shrinkage toward
zero. Alpha is picked per season by RidgeCV over ALPHAS. The
possession floor drops low-sample players after the fit instead of
shrinking them further, so published rows all clear MIN_POSS.

Usage: python -m scripts.seed_rapm_priors --self-check
    python -m scripts.seed_rapm_priors --end-years 2022 2023 2024 2025
The coordinator schedules the full warehouse run. Do not run it inline.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import polars as pl
from scipy.sparse import csr_matrix
from sklearn.linear_model import RidgeCV

OFF = [f"off_player_{i}" for i in range(1, 6)]
DEF = [f"def_player_{i}" for i in range(1, 6)]

PRIOR_SEASONS = {2022: "2021-22", 2023: "2022-23",
                 2024: "2023-24", 2025: "2024-25"}
ALPHAS = [500, 1000, 2000, 4000]
MIN_POSS = 500
MIN_ROWS = 100


def season_label(end_year: int) -> str:
    if int(end_year) == 2026:
        raise ValueError("end-year 2026 (2025-26) is the live season, never a prior")
    try:
        return PRIOR_SEASONS[int(end_year)]
    except KeyError:
        raise ValueError(f"prior end-year must be one of {sorted(PRIOR_SEASONS)}")


def build_matrix(stints: pl.DataFrame):
    players = sorted({str(v) for c in OFF + DEF
                      for v in stints[c].to_list() if v})
    idx = {p: i for i, p in enumerate(players)}
    rows, cols, data = [], [], []
    pts: list[float] = []
    for n, r in enumerate(stints.to_dicts()):
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
    counts = np.bincount(np.array(cols, dtype=int), minlength=len(players))
    return X, y, players, counts


def fit_ridge(X, y):
    model = RidgeCV(alphas=ALPHAS)
    model.fit(X, y)
    return model.coef_, model.alpha_


def compute_season_rapm(stints: pl.DataFrame, season: str,
                        min_poss: int = MIN_POSS) -> pl.DataFrame:
    if season == "2025-26":
        raise ValueError("2025-26 is the live season, never a prior")
    X, y, players, counts = build_matrix(stints)
    coef, _ = fit_ridge(X, y)
    try:
        from nba_api.stats.static import players as _pl

        names = {str(p["id"]): p["full_name"] for p in _pl.get_players()}
    except Exception:
        names = {}
    out = [{"player_id": p, "name": names.get(p, p),
            "rapm": round(float(coef[i]) * 100, 2),
            "possessions": int(counts[i])}
           for p, i in ({p: i for i, p in enumerate(players)}).items()
           if counts[i] >= min_poss]
    out.sort(key=lambda r: r["rapm"], reverse=True)
    return pl.DataFrame(out, schema=["player_id", "name", "rapm", "possessions"])


def fetch_stints(con, season: str) -> pl.DataFrame:
    return pl.from_arrow(con.execute(
        f"""SELECT {', '.join(OFF + DEF)}, points
        FROM silver_hist_possessions
        WHERE _season = ? AND garbage = 0""",
        [season],
    ).to_arrow_table())


def seed_season(season: str, min_poss: int = MIN_POSS) -> int:
    from app import store
    from app.sources.base import FetchMeta, FetchResult

    con = store.connect()
    try:
        stints = fetch_stints(con, season)
    finally:
        con.close()
    frame = compute_season_rapm(stints, season, min_poss)
    assert frame.height >= MIN_ROWS, f"prior season {season} too thin: {frame.height} rows"
    res = FetchResult(frame=frame, meta=FetchMeta(source="rapm-prior", season=season))
    return store.save_frame("silver_rapm_prior", res, entity=f"season:{season}")


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--end-years", type=int, nargs="*",
                      default=sorted(PRIOR_SEASONS))
    args.add_argument("--min-poss", type=int, default=MIN_POSS)
    args.add_argument("--self-check", action="store_true")
    ns = args.parse_args()
    if ns.self_check:
        _self_check()
        return
    for end_year in ns.end_years:
        season = season_label(end_year)
        n = seed_season(season, ns.min_poss)
        print(f"seeded prior {season}: {n} players")


def _self_check() -> None:
    star = {"points": 1.2, **{c: v for c, v in zip(
        OFF, ["1", "2", "3", "4", "5"])},
        **{c: v for c, v in zip(DEF, ["6", "7", "8", "9", "10"])}}
    weak = {"points": 0.8, **{c: v for c, v in zip(
        OFF, ["6", "7", "8", "9", "10"])},
        **{c: v for c, v in zip(DEF, ["1", "2", "3", "4", "5"])}}
    stints = pl.DataFrame([star] * 60 + [weak] * 60)
    frame = compute_season_rapm(stints, "2021-22", min_poss=10)
    by_id = {r["player_id"]: r["rapm"] for r in frame.to_dicts()}
    assert by_id["1"] > by_id["6"], "ridge must rank the high-efficiency side first"
    assert frame.height == 10
    print(f"self-check ok: {frame.height} players, star {by_id['1']} > weak {by_id['6']}")


if __name__ == "__main__":
    main()
