import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

TABLE = "silver_on_off_derived"


def slug(stat: str) -> str:
    s = stat.replace("%", " pct")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    if s.endswith("_defense"):
        s = s[: -len("_defense")] + "_def"
    return s


def build_rows(rows):
    players = {}
    for stat, on, off, diff, _season, entity in rows:
        player_id = int(entity.split(":", 1)[1])
        key = (_season, player_id)
        rec = players.setdefault(key, {"_season": _season, "player_id": player_id})
        col = slug(stat)
        for suffix, val in (("on", on), ("off", off), ("diff", diff)):
            try:
                rec[f"{col}_{suffix}"] = float(val) if val is not None else None
            except (TypeError, ValueError):
                rec[f"{col}_{suffix}"] = None
    return list(players.values())


def fetch(con):
    return con.execute(
        'SELECT Stat, "On", "Off", "On-Off", _season, _entity '
        "FROM silver_on_off"
    ).fetchall()


def attach_teams(con, records):
    seasons = sorted({r["_season"] for r in records})
    team_map = {}
    for season in seasons:
        try:
            for pid, team in con.execute(
                "SELECT DISTINCT PLAYER_ID, TEAM FROM silver_player_season "
                "WHERE _season = ?", [season]).fetchall():
                team_map[(season, int(pid))] = team
        except Exception:
            pass
        try:
            for pid, team in con.execute(
                "SELECT DISTINCT PLAYER_ID, TEAM_ABBREVIATION "
                "FROM silver_boxscores_ext WHERE _season = ?", [season]).fetchall():
                team_map.setdefault((season, int(pid)), team)
        except Exception:
            pass
    for r in records:
        r["team"] = team_map.get((r["_season"], r["player_id"]))
    cols = ["_season", "player_id", "team"] + sorted(
        c for c in records[0] if c not in ("_season", "player_id", "team"))
    return [{c: r.get(c) for c in cols} for r in records]


def build(con):
    records = build_rows(fetch(con))
    if not records:
        return [], []
    records = attach_teams(con, records)
    return list(records[0].keys()), records


def main() -> None:
    import polars as pl
    con = store.connect(read_only=False)
    try:
        cols, records = build(con)
        if not records:
            raise SystemExit("silver_on_off is empty; nothing to derive")
        frame = pl.DataFrame(records, infer_schema_length=None)
        con.execute(f"CREATE OR REPLACE TABLE {TABLE} AS SELECT * FROM frame")
        rows = con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
        seasons = con.execute(
            f"SELECT min(_season), max(_season) FROM {TABLE}").fetchone()
    finally:
        con.close()
    print(f"{TABLE}: {rows} rows x {len(cols)} cols, seasons "
          f"{seasons[0]}..{seasons[1]}")


if __name__ == "__main__":
    main()
