import argparse
import io
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import polars as pl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
TABLE = "silver_hist_player_seasons"
ENTITY = "league"
SOURCE = "basketball-reference:league_pages"
FIRST = 1946
LAST = 1995
REQUEST_GAP = 3.0


def label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", ascii_only.strip(),
                  flags=re.IGNORECASE)


def league_slug(start_year: int) -> str:
    return "BAA" if start_year < 1949 else "NBA"


def name_map() -> dict:
    from nba_api.stats.static import players as sp
    m = {}
    for r in sp.get_players():
        m.setdefault(norm(r["full_name"]), r["id"])
    return m


def fetch_table(start_year: int, page: str) -> pd.DataFrame:
    year = start_year + 1
    url = ("https://www.basketball-reference.com/leagues/"
           f"{league_slug(start_year)}_{year}_{page}.html")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    text = re.sub(r"<!--|-->", "", r.text)
    df = pd.read_html(io.StringIO(text))[0]
    df = df[df[df.columns[1]] != "Player"]
    return df


def num(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return float(str(v).replace("%", ""))
    except (TypeError, ValueError):
        return None


def season_rows(start_year: int, pg: pd.DataFrame,
                adv: pd.DataFrame | None, nm: dict) -> list[dict]:
    end_year = start_year + 1
    adv_ts: dict = {}
    adv_usg: dict = {}
    if adv is not None:
        for _, r in adv.iterrows():
            key = (str(r.get("Player", "")).strip(),
                   str(r.get("Team", "")).strip())
            adv_ts[key] = num(r.get("TS%"))
            adv_usg[key] = num(r.get("USG%"))
    staged: list[dict] = []
    for _, r in pg.iterrows():
        player = str(r.get("Player", "")).strip()
        if not player or player == "nan":
            continue
        pid = nm.get(norm(player))
        team = str(r.get("Team", "")).strip()
        ts_pct = adv_ts.get((player, team))
        usg_pct = adv_usg.get((player, team))
        if ts_pct is None and team == "TOT":
            for (p, t), v in adv_ts.items():
                if p == player and t != "TOT":
                    ts_pct = v
                    break
        if usg_pct is None and team == "TOT":
            for (p, t), v in adv_usg.items():
                if p == player and t != "TOT":
                    usg_pct = v
                    break
        fgm, fga = num(r.get("FG")), num(r.get("FGA"))
        fg3m = num(r.get("3P")) or 0.0
        efg = num(r.get("eFG%"))
        if efg is None and fga:
            efg = round((fgm + 0.5 * fg3m) / fga, 3) if fgm is not None else None
        row = {
            "player_id": pid,
            "player_name": player,
            "team_abbreviation": team if team != "nan" else None,
            "season": end_year,
            "age": num(r.get("Age")),
            "gp": num(r.get("G")),
            "min": num(r.get("MP")),
            "pts": num(r.get("PTS")),
            "reb": num(r.get("TRB")),
            "ast": num(r.get("AST")),
            "stl": num(r.get("STL")),
            "blk": num(r.get("BLK")),
            "tov": num(r.get("TOV")),
            "fgm": fgm,
            "fga": fga,
            "fg_pct": num(r.get("FG%")),
            "fg3m": num(r.get("3P")),
            "fg3a": num(r.get("3PA")),
            "fg3_pct": num(r.get("3P%")),
            "ftm": num(r.get("FT")),
            "fta": num(r.get("FTA")),
            "ft_pct": num(r.get("FT%")),
            "ts_pct": ts_pct,
            "efg_pct": efg,
            "usg_pct": usg_pct,
            "off_rating": None,
            "def_rating": None,
            "net_rating": None,
            "pie": None,
            "pace": None,
            "_tot": 0 if team == "TOT" else 1,
        }
        staged.append(row)
    best: dict = {}
    for row in staged:
        k = row["player_name"]
        if k not in best or row["_tot"] < best[k]["_tot"]:
            best[k] = row
    rows = list(best.values())
    for row in rows:
        row.pop("_tot", None)
    return rows


def loaded_seasons() -> set[str]:
    try:
        con = store.connect(read_only=True)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if TABLE not in tables:
            return set()
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {TABLE}").fetchall()
        con.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def seed_season(start_year: int, nm: dict, fetcher=None) -> int:
    fetcher = fetcher or fetch_table
    pg = fetcher(start_year, "per_game")
    try:
        time.sleep(REQUEST_GAP)
        adv = fetcher(start_year, "advanced")
    except Exception:
        adv = None
    rows = season_rows(start_year, pg, adv, nm)
    if not rows:
        raise RuntimeError(f"{label(start_year)}: no usable rows")
    float_cols = [c for c in rows[0] if c not in
                ("player_name", "team_abbreviation", "player_id", "season", "gp")]
    frame = pl.DataFrame(rows, strict=False).with_columns(
        [pl.col(c).cast(pl.Float64, strict=False) for c in float_cols] +
        [pl.col("player_id").cast(pl.Int64, strict=False),
         pl.col("season").cast(pl.Int32, strict=False),
         pl.col("gp").cast(pl.Int64, strict=False)])
    res = FetchResult(frame=frame,
                      meta=FetchMeta(SOURCE, label(start_year)))
    return store.save_frame(TABLE, res, ENTITY, replace_season=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Backfill basketball-reference league per-game + advanced "
                    "pages into silver_hist_player_seasons for 1946-47..1995-96 "
                    "(BAA 1946-48, NBA from 1949-50).")
    ap.add_argument("--seasons", default="",
                    help="comma list of start years, e.g. 1946,1961,1995")
    ns = ap.parse_args(argv)
    if not os.environ.get("DIME_WAREHOUSE"):
        print("refusing: DIME_WAREHOUSE is not set")
        return 1
    years = ([int(x) for x in ns.seasons.split(",") if x.strip()]
             if ns.seasons else list(range(FIRST, LAST + 1)))
    done = loaded_seasons()
    nm = name_map()
    total, matched = 0, 0
    for y in years:
        if label(y) in done:
            print(f"{label(y)}: already loaded, skip")
            continue
        n = seed_season(y, nm)
        total += n
        time.sleep(REQUEST_GAP)
        print(f"{label(y)} ({league_slug(y)}): {n} player-seasons")
    print(f"loaded {total} rows into {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
