"""Monte Carlo playoff simulator (plain function; senior wires the tool)."""
import math
import random
SEED = 42
HOME_ELO = 400 * math.log10(0.55 / 0.45)  # 55% home edge in Elo


def _amap():
    from nba_api.stats.static import teams as _t
    return {t["id"]: t["abbreviation"] for t in _t.get_teams()}


def _strengths(con, season, amap):
    tabs = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_team_ratings" in tabs:
        rows = con.execute("SELECT TEAM_ID, NET_RATING FROM silver_team_ratings"
                           " WHERE _season = ?", [season]).fetchall()
        s = {amap[i]: float(nr or 0) for i, nr in rows if amap.get(i)}
        if len(s) >= 8:
            return s, "silver_team_ratings.NET_RATING"
    if "silver_standings" in tabs:
        rows = con.execute("SELECT TeamID, WINS, LOSSES FROM silver_standings"
                           " WHERE _season = ?", [season]).fetchall()
        s = {amap[i]: ((w or 0) / ((w or 0) + (lo or 0)) - 0.5) * 40.0
             for i, w, lo in rows if amap.get(i) and (w or 0) + (lo or 0)}
        if len(s) >= 8:
            return s, "silver_standings win-pct proxy (pct-0.5)*40"
    return {}, "empty"


def _field(con, season, strength, amap):
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_standings)").fetchall()]
    except Exception:
        cols = []
    if "Conference" in cols:
        rows = con.execute("SELECT TeamID, Conference, PlayoffRank FROM silver_standings"
                           " WHERE _season = ?", [season]).fetchall()
        conf = {}
        for i, c, pr in rows:
            a = amap.get(i)
            try:
                pr = int(pr or 99)
            except (TypeError, ValueError):
                pr = 99
            if a in strength and pr <= 8:
                conf.setdefault(str(c or ""), []).append((pr, a))
        if len(conf.get("East", [])) == 8 and len(conf.get("West", [])) == 8:
            seeds = {(c, pr): a for c in ("East", "West") for pr, a in sorted(conf[c])}
            return seeds, "conference-1-8-vs-8-1"
    top = sorted(strength, key=strength.get, reverse=True)[:16]
    if len(top) >= 8:
        return {(None, i + 1): a for i, a in enumerate(top)}, "reseeded-1-16"
    return {}, "empty"


def _series(a, b, strength):
    hi, lo = (a, b) if strength[a] >= strength[b] else (b, a)
    d = strength[hi] - strength[lo]
    ph = 1 / (1 + 10 ** (-(d * 4 + HOME_ELO) / 400))
    pa = 1 / (1 + 10 ** (-(d * 4 - HOME_ELO) / 400))
    w = l = 0
    for h in (1, 1, 0, 0, 1, 0, 1):
        if random.random() < (ph if h else pa):
            w += 1
        else:
            l += 1
        if w == 4 or l == 4:
            break
    return hi if w == 4 else lo


def run_playoff_sim(season="2025-26", sims=2000):
    """Game-by-game 2-2-1-1-1 bracket sim; returns title/final probs (pct)."""
    from .. import store as _store
    random.seed(SEED)
    con = _store.connect()
    try:
        amap = _amap()
        strength, src = _strengths(con, season, amap)
        seeds, bracket = _field(con, season, strength, amap)
    finally:
        con.close()
    teams = list(dict.fromkeys(seeds.values()))
    if not teams:
        return {"teams": [], "title_probs": {}, "final_probs": {}, "sims": 0,
                "meta": {"error": "warehouse empty", "season": season}}
    if bracket.startswith("conference"):
        r0 = [(seeds[(c, x)], seeds[(c, y)]) for c in ("East", "West")
              for x, y in ((1, 8), (4, 5), (3, 6), (2, 7))]
    else:
        o = [seeds[(None, s)] for s in sorted(k[1] for k in seeds)]
        r0 = [(o[0], o[15]), (o[7], o[8]), (o[3], o[12]), (o[4], o[11]),
              (o[1], o[14]), (o[6], o[9]), (o[2], o[13]), (o[5], o[10])]
    titles = {t: 0 for t in teams}
    finals = {t: 0 for t in teams}
    for _ in range(sims):
        alive = [_series(a, b, strength) for a, b in r0]
        while len(alive) > 2:
            alive = [_series(alive[i], alive[i + 1], strength)
                     for i in range(0, len(alive), 2)]
        for f in alive:
            finals[f] += 1
        titles[_series(alive[0], alive[1], strength)] += 1
    return {"teams": teams,
            "title_probs": {t: round(100 * titles[t] / sims, 1) for t in teams},
            "final_probs": {t: round(100 * finals[t] / sims, 1) for t in teams},
            "sims": sims, "meta": {"season": season, "strength": src,
            "bracket": bracket, "seed": SEED, "home_edge_elo": round(HOME_ELO, 1)}}
