"""Garbage-time flags per the public Cleaning the Glass definition.

Q4 plus margin thresholds plus two or fewer starters on floor combined.
Sticky: once garbage, later events stay garbage unless margin recovers,
then the clock resets. Writes silver_hist_possessions.garbage (0/1).

Usage: python -m scripts.garbage --seasons 2022,2023,2024,2025,2026
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store


def starters(df: pl.DataFrame) -> set:
    early = df.sort(["period", "possession_number"]).head(3)
    out: set = set()
    for r in early.to_dicts():
        for k in ("off_player_1", "off_player_2", "off_player_3",
                  "off_player_4", "off_player_5",
                  "def_player_1", "def_player_2", "def_player_3",
                  "def_player_4", "def_player_5"):
            if r.get(k):
                out.add(str(r[k]))
    return out


def flag_game(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort(["period", "possession_number"])
    rows = df.to_dicts()
    teams = {str(r["offense_team_id"]) for r in rows}
    score = {t: 0 for t in teams}
    order = sorted(teams)
    start5 = starters(df)
    garbage = False
    flags = []
    for r in rows:
        t = str(r["offense_team_id"])
        try:
            score[t] += int(r.get("points") or 0)
        except (TypeError, ValueError):
            pass
        margin = abs(score.get(order[0], 0) - score.get(order[-1], 0)) if len(order) > 1 else 0
        onfloor = {
            str(r.get(k, "")) for k in (
                "off_player_1", "off_player_2", "off_player_3",
                "off_player_4", "off_player_5",
                "def_player_1", "def_player_2", "def_player_3",
                "def_player_4", "def_player_5")
        }
        nstart = len(onfloor & start5)
        secs = r.get("start_seconds_remaining") or 0
        try:
            secs = int(secs)
        except (TypeError, ValueError):
            secs = 0
        hit = (
            r.get("period") == 4
            and nstart <= 2
            and (
                (540 <= secs <= 720 and margin >= 25)
                or (360 <= secs < 540 and margin >= 20)
                or (secs < 360 and margin >= 10)
            )
        )
        if garbage and not (
            r.get("period") == 4 and margin >= 10 and nstart <= 2
        ):
            garbage = False
        if hit:
            garbage = True
        flags.append(1 if garbage else 0)
    return df.with_columns(pl.Series("garbage", flags))


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    ns = args.parse_args()
    con = store.connect()
    try:
        cols = [r[1] for r in con.execute(
            "PRAGMA table_info(silver_hist_possessions)").fetchall()]
        if "garbage" not in cols:
            con.execute("ALTER TABLE silver_hist_possessions ADD COLUMN garbage INTEGER DEFAULT 0")
        total = flagged = 0
        for y in [int(s) for s in ns.seasons.split(",")]:
            label = f"{y - 1}-{str(y)[2:]}"
            games = con.execute(
                "SELECT DISTINCT game_id FROM silver_hist_possessions WHERE _season = ?",
                [label],
            ).fetchall()
            for (gid,) in games:
                df = pl.from_arrow(con.execute(
                    "SELECT * FROM silver_hist_possessions WHERE game_id = ?",
                    [str(gid)],
                ).to_arrow_table())
                if df.height == 0:
                    continue
                out = flag_game(df)
                total += out.height
                bad = out.filter(pl.col("garbage") == 1).select(
                    ["period", "possession_number", "offense_team_id"])
                if bad.height:
                    flagged += bad.height
                    con.executemany(
                        """UPDATE silver_hist_possessions SET garbage = 1
                        WHERE game_id = ? AND period = ?
                        AND possession_number = ? AND offense_team_id = ?""",
                        [(str(gid), r["period"], r["possession_number"],
                          r["offense_team_id"]) for r in bad.to_dicts()],
                    )
        print(f"possessions: {total}, flagged: {flagged}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
