import argparse
import hashlib
import json
import sys
from pathlib import Path

DICTIONARY_FILE = "data_dictionary.json"

_JOIN_KEY_NAMES = (
    "PERSON_ID", "PLAYER_ID", "Player_ID", "player_id",
    "TEAM_ID", "team_id", "TEAM_ABBREVIATION", "team_abbreviation",
    "GAME_ID", "Game_ID", "game_id",
    "GROUP_ID", "group_id",
    "_season", "season",
)

_TABLE_PURPOSES = {
    "silver_advanced": "per-player advanced season stats (TS_PCT, ratings); MIN is per-game minutes",
    "silver_bbref_gamelogs_2024_25": "Basketball Reference player gamelogs for the 2024-25 season",
    "silver_boxscores": "per-player per-game traditional box scores through 2024-25",
    "silver_boxscores_ext": "extended box-score fields beyond the traditional line",
    "silver_cap_history": "league salary cap, tax, apron, and max-salary rules by season (1984-85 on)",
    "silver_injury_report": "official NBA game-day injury report snapshots by season (2018-19 on): player, status, reason, report datetime",
    "silver_synergy": "public play-type stats per player-season (PnR ballhandler, isolation, spotup, etc.) regular-season totals, offensive and defensive (2015-16 on)",
    "silver_player_bio": "player bio per season (birth country/city, height, weight, position, college, draft pick) ESPN core (1993-94 on)",
    "silver_gleague_season": "G League player season stats (nba_api league_id=20) 2007-08 on",
    "silver_hist_salaries": "per-player salary by season for 1984-85 through 2017-18 (hoopshype mirror)",
    "silver_games_missed": "games a rostered player did not appear in vs team games, 1996-97 on; NOT injury data — trades, DNP-CDs, G League stints and suspensions look identical; full-season absences are not recorded",
    "silver_cap_players": "player contract and cap figures",
    "silver_clutch": "clutch-time player stats",
    "silver_combine": "draft combine measurements and results",
    "silver_four_factors": "player four-factors season stats",
    "silver_hist_draft": "all NBA/BAA drafts 1947 on (nba_api DraftHistory); SEASON=pick-entering season end year, DRAFT_YEAR=draft class year",
    "silver_hist_gamelogs": "team gamelogs, regular season and playoffs (season_type column)",
    "silver_hist_hustle": "historical hustle stats",
    "silver_hist_lineups": "five-man lineup stats; variant rows by season_type, measure_type, per_mode",
    "silver_hist_pbp": "historical play-by-play events",
    "silver_hist_player_seasons": "historical player season stats 1946-47 on (BAA/NBA via basketball-reference + stats.nba.com); stl/blk/tov absent pre-1973-74, 3P absent pre-1979-80; ts/usg where published, off/def/net/pie/pace NULL for pre-1996 seasons",
    "silver_hist_team_seasons": "team season stats 1946-47 on; pre-1996 base/opponent per-game rows from basketball-reference + W/L from stats.nba.com standings (stl/blk absent pre-1973-74, tov pre-1977-78, 3P pre-1979-80, ratings/adv NULL)",
    "silver_hist_possessions": "lineup-level possession outcomes",
    "silver_hist_shots": "per-shot coordinates and results back to 2009-10",
    "silver_hist_standings": "historical standings snapshots",
    "silver_hustle_player": "current-season player hustle stats",
    "silver_hustle_team": "current-season team hustle stats",
    "silver_injuries": "current injury report entries",
    "silver_leaders_ast": "official season assist leaders",
    "silver_leaders_blk": "official season block leaders",
    "silver_leaders_dreb": "official season defensive-rebound leaders",
    "silver_leaders_fg_pct": "official season field-goal-percentage leaders",
    "silver_leaders_pts": "official season scoring leaders",
    "silver_leaders_reb": "official season rebound leaders",
    "silver_leaders_stl": "official season steal leaders",
    "silver_lineups": "current dashboard lineup units; coverage ends 2024-25",
    "silver_on_off": "player on/off court splits",
    "silver_player_gamelogs": "per-player per-game lines; incomplete, never sum for season totals",
    "silver_player_season": "per-player season totals keyed by upstream PLAYER_ID",
    "silver_playoff_gamelogs": "player playoff gamelogs; thinly seeded",
    "silver_playoff_inactive": "playoff inactive-player lists",
    "silver_playoffs": "team playoff games; currently 2025-26 only",
    "silver_rapm": "regularized adjusted plus-minus estimates",
    "silver_rapm_prior": "prior-season RAPM used as a prior",
    "silver_raptor_player": "FiveThirtyEight RAPTOR player ratings archive",
    "silver_raptor_team": "FiveThirtyEight RAPTOR team ratings archive",
    "silver_rosters": "current team rosters",
    "silver_salaries": "player salary rows by season",
    "silver_schedule": "upcoming and played schedule entries",
    "silver_scoreboard": "recent scoreboard results",
    "silver_shots": "recent per-shot coordinates and results",
    "silver_standings": "current standings",
    "silver_team_games": "team game log with display-string dates",
    "silver_team_ratings": "team-level season ratings",
    "silver_wowy": "with-or-without-you lineup splits",
    "silver_zone_splits": "shooting-zone splits by player and team",
}

_TABLE_CAVEATS = {
    "silver_advanced": [
        "MIN is per-game minutes, not season totals; use MIN * GP for total minutes.",
    ],
    "silver_boxscores": [
        "Coverage ends at 2024-25; no 2025-26 rows.",
    ],
    "silver_hist_gamelogs": [
        "Holds season_type 'regular-season' and 'playoffs' rows; filter explicitly.",
        "Only game_ids prefixed 004 are playoff games; playoff-flagged rows with 002 ids are malformed.",
    ],
    "silver_hist_lineups": [
        "Filter season_type, measure_type, per_mode; never aggregate across variants.",
        "Ratings and pace exist only on measure_type='advanced' rows.",
    ],
    "silver_leaders_ast": ["MIN is total season minutes."],
    "silver_leaders_blk": ["MIN is total season minutes."],
    "silver_leaders_dreb": ["MIN is total season minutes."],
    "silver_leaders_fg_pct": ["MIN is total season minutes."],
    "silver_leaders_pts": ["MIN is total season minutes."],
    "silver_leaders_reb": ["MIN is total season minutes."],
    "silver_leaders_stl": ["MIN is total season minutes."],
    "silver_lineups": [
        "Coverage ends at 2024-25; silver_hist_lineups serves past seasons.",
    ],
    "silver_player_gamelogs": [
        "Incomplete per-game rows; season totals live in silver_leaders_* tables.",
    ],
    "silver_player_season": [
        "PLAYER_ID is the upstream source id and can differ from the static player id.",
    ],
    "silver_playoff_gamelogs": [
        "Thinly seeded; prefer silver_hist_gamelogs playoff rows for team playoff data.",
    ],
    "silver_playoffs": [
        "Only 2025-26 seeded; use silver_hist_gamelogs season_type='playoffs' for earlier playoffs.",
    ],
    "silver_team_games": [
        "GAME_DATE is a display string like 'OCT 22, 2025', not a date type.",
    ],
}

_INTERNAL_TABLES = {
    "chat_history", "fetch_log", "leaderboard_snapshots", "runs", "watchlists",
}


def _columns(con, table):
    return [
        {"name": row[1], "type": str(row[2])}
        for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()
    ]


def _join_keys(column_names):
    names = set(column_names)
    keys = [key for key in _JOIN_KEY_NAMES if key in names]
    if "_season" in names and "_season" not in keys:
        keys.append("_season")
    return keys


def _season_coverage(con, table, column_names):
    season_col = "_season" if "_season" in column_names else (
        "season" if "season" in column_names else None)
    if not season_col:
        return None
    lo, hi = con.execute(
        f'SELECT min("{season_col}"), max("{season_col}") FROM "{table}"'
    ).fetchone()
    if lo is None:
        return None
    return str(lo) if lo == hi else f"{lo} – {hi}"


def _provenance(con, table, column_names):
    out = {}
    if "_source" in column_names:
        out["sources"] = sorted(
            row[0] for row in
            con.execute(
                f'SELECT DISTINCT "_source" FROM "{table}"').fetchall()
            if row[0])
    if "_entity" in column_names:
        out["entities"] = sorted(
            row[0] for row in
            con.execute(
                f'SELECT DISTINCT "_entity" FROM "{table}"').fetchall()
            if row[0])
    if "_fetched_at" in column_names:
        last = con.execute(
            f'SELECT max("_fetched_at") FROM "{table}"').fetchone()[0]
        if last is not None:
            out["last_fetch"] = str(last)
    return out


def build_dictionary(warehouse_path) -> dict:
    import duckdb
    warehouse_path = Path(warehouse_path)
    digest = hashlib.sha256()
    with open(warehouse_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        names = sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
        tables = {}
        for name in names:
            cols = _columns(con, name)
            colnames = [c["name"] for c in cols]
            rows = con.execute(
                f'SELECT count(*) FROM "{name}"').fetchone()[0]
            entry = {
                "purpose": _TABLE_PURPOSES.get(
                    name, "internal pipeline table"
                    if name in _INTERNAL_TABLES
                    else "warehouse table"),
                "rows": rows,
                "seasons": _season_coverage(con, name, colnames),
                "join_keys": _join_keys(colnames),
                "columns": colnames,
            }
            prov = _provenance(con, name, colnames)
            if prov:
                entry["provenance"] = prov
            caveats = _TABLE_CAVEATS.get(name)
            if caveats:
                entry["caveats"] = caveats
            tables[name] = entry
    finally:
        con.close()
    import datetime
    return {
        "warehouse_file": warehouse_path.name,
        "warehouse_sha256": digest.hexdigest(),
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "tables": tables,
    }


def write_dictionary(warehouse_path, out_path=None) -> Path:
    out = Path(out_path) if out_path else (
        Path(warehouse_path).resolve().parent / DICTIONARY_FILE)
    doc = build_dictionary(warehouse_path)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse", required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)
    out = write_dictionary(args.warehouse, args.out or None)
    print(f"dictionary written -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
