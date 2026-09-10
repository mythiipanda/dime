"""Mirror check for the gamelog family: independent replica vs the real
search_game_logs tool. Asserts exact equality on the matching game set
(date, opponent, home/away, pts/reb/ast), the total, and the capped flag,
across a sampled spread of players and filter combos.
Run from backend/: .venv/bin/python -m bench.mirror_gamelog_check
"""

import random
import sys

sys.path.insert(0, ".")

from .ground import (SEASON, _glog_games, _glog_matches, _glog_templates)


def _static():
    from nba_api.stats.static import players as _players, teams as _teams
    names = {p.get("id"): p.get("full_name") for p in _players.get_players()}
    fulls = {str(t.get("abbreviation", "")).upper(): t.get("full_name")
             for t in _teams.get_teams()}
    return names, fulls


def main() -> None:
    from app.tools.gamelog import search_game_logs
    from app import store

    con = store.connect(read_only=True)
    try:
        ents = [r[0] for r in con.execute(
            "SELECT DISTINCT Player_ID FROM silver_player_gamelogs "
            "WHERE _season = ?", [SEASON]).fetchall()]
    finally:
        con.close()
    names, fulls = _static()
    templates = _glog_templates()
    rng = random.Random(1234)
    checked = mismatches = 0
    seen: set = set()
    while checked < 30 and len(seen) < 5000:
        pid = int(rng.choice(ents))
        ti = rng.randrange(len(templates))
        key = (pid, ti)
        if key in seen:
            continue
        seen.add(key)
        name = names.get(pid)
        if not name:
            continue
        games = _glog_games(pid)
        if len(games) < 10:
            continue
        built = templates[ti](rng, games, name, fulls.get)
        if built is None:
            continue
        _, filters, kwargs = built
        mine = [g for g in games if _glog_matches(g, filters)]
        res = search_game_logs.invoke(
            {"player": str(pid), "season": SEASON, "limit": 50, **kwargs})
        rows = (res or {}).get("rows") or {}
        got = rows.get("matches") or []
        mine_key = [(g["date"], g["opponent"], g["home"],
                     round(g["pts"], 1), round(g["reb"], 1),
                     round(g["ast"], 1)) for g in mine]
        got_key = [(m.get("date"), m.get("opponent"), m.get("home"),
                    round(float(m.get("pts") or 0), 1),
                    round(float(m.get("reb") or 0), 1),
                    round(float(m.get("ast") or 0), 1)) for m in got]
        bad = []
        if not (res or {}).get("ok"):
            bad.append("tool_error")
        if rows.get("total") != len(mine):
            bad.append(f"total {rows.get('total')} != {len(mine)}")
        if rows.get("capped") not in (False, None):
            bad.append("capped")
        if got_key != mine_key:
            bad.append(f"set_mismatch ({len(got_key)} vs {len(mine_key)})")
        status = "OK " if not bad else "MISS"
        if bad:
            mismatches += 1
        print(f"{status} pid={pid} filters={kwargs} n={len(mine)}"
              + (f" {bad}" if bad else ""))
        checked += 1
    print(f"checked={checked} mismatches={mismatches}")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
