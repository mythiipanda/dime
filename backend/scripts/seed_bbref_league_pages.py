"""Seed league-wide 2025-26 tables from basketball-reference single pages.

Writes:
  silver_player_season  - per-game season line per player (coverage fallback)
  silver_zone_splits    - distance-bucket shooting splits (shot-zone fallback)

stats.nba.com endpoint-blocks datacenter IPs; bbref is reachable, so these
league pages are the seed source. Idempotent: replaces each table's season.
"""
import io
import re
import sys
import unicodedata

import pandas as pd
import polars as pl
import requests

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])
from app import store  # noqa: E402
from app.sources.base import FetchMeta, FetchResult  # noqa: E402

SEASON = "2025-26"
BBREF_YEAR = 2026
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
BASE = "https://www.basketball-reference.com/leagues/NBA_%d_%s.html"


def norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", ascii_only.strip(),
                  flags=re.IGNORECASE)


def name_map() -> dict:
    from nba_api.stats.static import players as sp
    m = {}
    for r in sp.get_players():
        m.setdefault(norm(r["full_name"]), r["id"])
    return m


def fetch(page: str) -> pd.DataFrame:
    r = requests.get(BASE % (BBREF_YEAR, page), headers=HEADERS, timeout=30)
    r.raise_for_status()
    df = pd.read_html(io.StringIO(r.text))[0]
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["|".join(str(x) for x in tup if "Unnamed" not in str(x))
                      for tup in df.columns]
    df = df[df[df.columns[1]] != "Player"]  # repeated header rows
    return df


def save(table: str, rows: list[dict], season: str) -> None:
    frame = pl.DataFrame(rows) if rows else pl.DataFrame()
    res = FetchResult(frame=frame, meta=FetchMeta("basketball-reference", season))
    con = store.connect()
    try:
        con.execute(f"DROP TABLE IF EXISTS {table}")
    finally:
        con.close()
    n = store.save_frame(table, res, "league")
    print(f"{table}: {n} rows written")


def main() -> None:
    nm = name_map()

    # --- per-game season lines ---
    pg = fetch("per_game")
    rows = []
    for _, r in pg.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid:
            continue
        rows.append({
            "PLAYER_ID": pid, "PLAYER": str(r["Player"]),
            "TEAM": str(r.get("Team", "")), "AGE": _f(r.get("Age")),
            "_TEAMORDER": 0 if str(r.get("Team", "")) == "TOT" else 1,
            "GP": _f(r.get("G")), "GS": _f(r.get("GS")),
            "MPG": _f(r.get("MP")), "PPG": _f(r.get("PTS")),
            "RPG": _f(r.get("TRB")), "APG": _f(r.get("AST")),
            "SPG": _f(r.get("STL")), "BPG": _f(r.get("BLK")),
            "FG_PCT": _f(r.get("FG%")), "FG3_PCT": _f(r.get("3P%")),
            "FT_PCT": _f(r.get("FT%")),
        })
    # Traded players appear once per team plus a TOT row; keep TOT when present.
    best = {}
    for row in rows:
        k = row["PLAYER_ID"]
        if k not in best or row["_TEAMORDER"] < best[k]["_TEAMORDER"]:
            best[k] = row
    rows = []
    for row in best.values():
        row.pop("_TEAMORDER", None)
        rows.append(row)
    save("silver_player_season", rows, SEASON)
    # Per-game FGA per player for the zone-split totals join below.
    fga_by_pid = {}
    for _, r in pg.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid or str(r.get("Team", "")) == "TOT" and pid in fga_by_pid:
            continue
        try:
            fga_by_pid[pid] = float(r.get("FGA") or 0) * float(r.get("G") or 0)
        except (TypeError, ValueError):
            pass

    # --- distance-bucket shooting splits ---
    sh = fetch("shooting")
    cols = list(sh.columns)
    dist_pct = [c for c in cols if "% of FGA" in str(c) or "Dist." in str(c)]
    print("shooting cols:", cols[:25])
    gp_col = next((c for c in cols if str(c) == "G"), None)
    bucket_pct = {}
    bucket_fg = {}
    for c in cols:
        m = re.search(r"(\d+-\d+P?|3P)", str(c))
        if not m:
            continue
        bucket = m.group(1)
        bucket = {"16-3P": "16ft-3P", "0-3": "0-3ft", "3-10": "3-10ft",
                  "10-16": "10-16ft"}.get(bucket, bucket)
        if "%" in str(c) and "FG" not in str(c).upper()[:6]:
            bucket_pct.setdefault(bucket, c)
        if "FG%" in str(c):
            bucket_fg.setdefault(bucket, c)
    print("buckets pct:", bucket_pct, "fg:", bucket_fg)
    zrows = []
    for _, r in sh.iterrows():
        pid = nm.get(norm(str(r.get("Player", ""))))
        if not pid:
            continue
        fga_tot = fga_by_pid.get(pid, 0.0)
        if fga_tot <= 0:
            continue
        for bucket, pc in bucket_pct.items():
            fc = bucket_fg.get(bucket)
            if fc is None:
                continue
            try:
                share = float(r.get(pc) or 0)
                fgpct = float(r.get(fc) or 0)
            except (TypeError, ValueError):
                continue
            fga = share * fga_tot
            zrows.append({
                "PLAYER_ID": pid, "ZONE": bucket, "FGA": round(fga, 1),
                "FGM": round(fga * fgpct, 1), "FGA_PCT": round(share, 3),
                "FG_PCT": round(fgpct, 3),
            })
    save("silver_zone_splits", zrows, SEASON)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
