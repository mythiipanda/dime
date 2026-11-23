import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import polars as pl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

TABLE = "silver_hist_team_seasons"
ENTITY = "league"
SOURCE = "basketball-reference:league-page+stats.nba.com:standings"
FIRST = 1946
LAST = 1995
REQUEST_GAP = 3.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
}
PER_GAME_COLS = {"FG": "fgm", "FGA": "fga", "FG%": "fg_pct",
                 "3P": "fg3m", "3PA": "fg3a", "3P%": "fg3_pct",
                 "FT": "ftm", "FTA": "fta", "FT%": "ft_pct",
                 "ORB": "oreb", "DRB": "dreb", "TRB": "reb",
                 "AST": "ast", "STL": "stl", "BLK": "blk",
                 "TOV": "tov", "PF": "pf", "PTS": "pts"}
ALIASES = {"Fort Wayne Pistons": "Ft. Wayne Zollner Pistons",
          "Tri-Cities Blackhawks": "Tri-Cities Blackhawks"}


def canon(name: str) -> str:
    return ALIASES.get(name, name)


RANK_COLS = ["w", "w_pct", "pts", "fgm", "fga", "fg_pct", "ftm", "fta",
             "ft_pct", "fg3m", "fg3a", "fg3_pct", "oreb", "dreb", "reb",
             "ast", "stl", "blk", "tov", "pf"]


def league_slug(year_start: int) -> str:
    return "BAA" if year_start < 1949 else "NBA"


def label(year_start: int) -> str:
    return f"{year_start}-{(year_start + 1) % 100:02d}"


def fetch_standings(year_start: int) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguestandingsv3
    df = leaguestandingsv3.LeagueStandingsV3(
        league_id="00", season=label(year_start),
        season_type="Regular Season", timeout=60).get_data_frames()[0]
    df = df.copy()
    df["full"] = (df["TeamCity"].astype(str).str.strip() + " " +
                  df["TeamName"].astype(str).str.strip())
    return df


def fetch_bbref_tables(year_start: int) -> list[pd.DataFrame]:
    url = ("https://www.basketball-reference.com/leagues/"
           f"{league_slug(year_start)}_{year_start + 1}.html")
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    text = re.sub(r"<!--|-->", "", r.text)
    return pd.read_html(io.StringIO(text))


def per_game_tables(tables: list[pd.DataFrame]) -> dict[str, pd.DataFrame]:
    wide = [t for t in tables if "Team" in t.columns
            and "PTS" in t.columns and "G" in t.columns
            and t.shape[1] >= 20]
    wide = [t[(t["Team"].astype(str) != "Team")
              & (t["Team"].astype(str) != "League Average")] for t in wide]
    per_game = [t for t in wide
                if pd.to_numeric(t["PTS"], errors="coerce").median() < 1000]
    out = {}
    if len(per_game) >= 1:
        out["base"] = per_game[0]
    if len(per_game) >= 2:
        out["opponent"] = per_game[1]
    return out


def season_rows(year_start: int, standings: pd.DataFrame,
                tables: dict[str, pd.DataFrame]) -> pl.DataFrame:
    name_to_id = dict(zip(standings["full"], standings["TeamID"]))
    wins = dict(zip(standings["full"], standings["WINS"]))
    losses = dict(zip(standings["full"], standings["LOSSES"]))
    base = tables.get("base")
    opp = tables.get("opponent")
    rows = []
    if base is not None:
        for _, t in base.iterrows():
            team = str(t["Team"]).replace("*", "").strip()
            canon_team = canon(team)
            stat = {"team_name": team,
                    "team_id": name_to_id.get(canon_team,
                                              name_to_id.get(team))}
            for src, dst in PER_GAME_COLS.items():
                if src in t.index:
                    v = pd.to_numeric(t[src], errors="coerce")
                    stat[dst] = None if pd.isna(v) else float(v)
            opp_row = (opp[opp["Team"].astype(str).str.replace("*", "")
                          .str.strip().map(canon) == canon_team]
                       if opp is not None else None)
            if opp_row is not None and len(opp_row):
                o = opp_row.iloc[0]
                if "PTS" in o.index:
                    ov = pd.to_numeric(o["PTS"], errors="coerce")
                    if not pd.isna(ov) and stat.get("pts") is not None:
                        stat["plus_minus"] = stat["pts"] - float(ov)
            stat["gp"] = int(pd.to_numeric(t["G"], errors="coerce")) \
                if not pd.isna(pd.to_numeric(t["G"], errors="coerce")) else None
            wk = canon_team if canon_team in wins else team
            stat["w"] = int(wins[wk]) if wk in wins else None
            stat["l"] = int(losses[wk]) if wk in losses else None
            if stat.get("w") is not None and stat.get("l") is not None:
                stat["w_pct"] = round(stat["w"] / (stat["w"] + stat["l"]), 3)
            if stat.get("fgm") and stat.get("fga"):
                fg3m = stat.get("fg3m") or 0.0
                stat["efg_pct"] = (stat["fgm"] + 0.5 * fg3m) / stat["fga"]
            if stat.get("pts") and stat.get("fga"):
                fta = stat.get("fta") or 0.0
                stat["ts_pct"] = stat["pts"] / (2 * (stat["fga"] + 0.44 * fta))
            stat.update({"season": year_start + 1,
                         "season_type": "regular-season",
                         "measure_type": "base", "per_mode": "pergame"})
            rows.append(stat)
        if opp is not None:
            for _, t in opp.iterrows():
                team = str(t["Team"]).replace("*", "").strip()
                canon_team = canon(team)
                stat = {"team_name": team,
                        "team_id": name_to_id.get(canon_team,
                                                  name_to_id.get(team))}
                for src, dst in PER_GAME_COLS.items():
                    if src in t.index:
                        v = pd.to_numeric(t[src], errors="coerce")
                        stat[dst] = None if pd.isna(v) else float(v)
                stat["gp"] = int(pd.to_numeric(t["G"], errors="coerce")) \
                    if not pd.isna(pd.to_numeric(t["G"],
                                                 errors="coerce")) else None
                stat.update({"season": year_start + 1,
                             "season_type": "regular-season",
                             "measure_type": "opponent",
                             "per_mode": "pergame"})
                rows.append(stat)
    df = pl.DataFrame(rows) if rows else pl.DataFrame()
    if df.height:
        for col in RANK_COLS:
            if col in df.columns:
                try:
                    df = df.with_columns(
                        pl.col(col).rank(method="min", descending=True)
                        .alias(f"{col}_rank"))
                except Exception:
                    pass
    return df


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


def seed_season(year_start: int, dry_run: bool = False) -> int:
    standings = fetch_standings(year_start)
    time.sleep(REQUEST_GAP)
    tables = per_game_tables(fetch_bbref_tables(year_start))
    frame = season_rows(year_start, standings, tables)
    if frame.height == 0:
        print(f"{label(year_start)}: no rows")
        return 0
    for col in ("w", "l", "w_pct", "min", "plus_minus", "pts"):
        if col in frame.columns:
            frame = frame.with_columns(
                pl.col(col).cast(pl.Float64, strict=False))
    if "team_id" in frame.columns:
        frame = frame.with_columns(
            pl.col("team_id").cast(pl.Int64, strict=False))
    frame = frame.with_columns(pl.col("season").cast(pl.Int32))
    if dry_run:
        print(f"{label(year_start)}: dry-run {frame.height} rows")
        return frame.height
    res = FetchResult(frame=frame,
                      meta=FetchMeta(SOURCE, label(year_start)))
    n = store.save_frame(TABLE, res, ENTITY, replace_season=True)
    print(f"{label(year_start)}: {n} rows")
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Backfill silver_hist_team_seasons for 1946-47..1995-96 "
                    "(bbref league per-game tables + stats.nba.com standings).")
    ap.add_argument("--years", default="",
                    help="comma list of start years, e.g. 1946,1961,1984")
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    if not os.environ.get("DIME_WAREHOUSE"):
        print("refusing: DIME_WAREHOUSE is not set")
        return 1
    years = ([int(x) for x in ns.years.split(",") if x.strip()]
             if ns.years else list(range(FIRST, LAST + 1)))
    done = loaded_seasons()
    total = 0
    for y in years:
        if label(y) in done:
            print(f"{label(y)}: already loaded, skip")
            continue
        try:
            total += seed_season(y, dry_run=ns.dry_run)
        except Exception as exc:
            print(f"{label(y)}: FAILED {exc}")
        time.sleep(REQUEST_GAP)
    print(f"loaded {total} rows into {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
