"""Mirror check for the impact family: independent replica vs the real
get_impact_estimate tool. Asserts exact 2dp equality on the estimate plus
the lift and prior components, across a stratified player sample.
Run from backend/: .venv/bin/python -m bench.mirror_impact_check
"""

import random
import sys

sys.path.insert(0, ".")

from app import store

from .ground import SEASON, _impact_estimate


def _sample(seed: int, n: int) -> list[tuple]:
    con = store.connect(read_only=True)
    try:
        rows = con.execute(
            "SELECT PLAYER_ID, PLAYER_NAME, POSS FROM silver_advanced "
            "WHERE _season = ? AND GP >= 5", [SEASON]).fetchall()
    finally:
        con.close()
    buckets: dict[str, list] = {"low": [], "mid": [], "high": []}
    for r in rows:
        poss = r[2] or 0
        key = "low" if poss < 1000 else ("mid" if poss < 3000 else "high")
        buckets[key].append(r)
    rng = random.Random(seed)
    out = []
    for key in ("low", "mid", "high"):
        pool = buckets[key]
        out += rng.sample(pool, min(n // 3, len(pool)))
    return out


def main() -> None:
    from app.tools.player import get_impact_estimate

    sample = _sample(seed=1234, n=21)
    mismatches = 0
    for pid, name, poss in sample:
        nm, tm, est, lift, prior = _impact_estimate(int(pid))
        res = get_impact_estimate.invoke(
            {"player": int(pid), "season": SEASON})
        comp = res.get("components") or {}
        checks = {
            "ok": res.get("ok") is True,
            "is_estimate": res.get("is_estimate") is True,
            "method": res.get("method") == "box_prior_shrinkage",
            "estimate": res.get("estimate_per_100") == est,
            "lift": comp.get("measured_lift_per_100") == lift,
            "prior": comp.get("box_prior_per_100") == prior,
        }
        bad = [k for k, v in checks.items() if not v]
        status = "OK " if not bad else "MISS"
        if bad:
            mismatches += 1
        print(f"{status} {nm} ({tm}) poss={poss:.0f} "
              f"est={est} tool={res.get('estimate_per_100')} "
              f"{'bad=' + ','.join(bad) if bad else ''}")
    print(f"\n{len(sample) - mismatches}/{len(sample)} exact matches")
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
