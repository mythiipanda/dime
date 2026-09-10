"""Runtime task generators. Ground truth comes from the warehouse directly.

Anti-circularity rule: this module imports app.store and app.sources only,
plus nba_api static tables for player-name resolution (the same upstream
source the streak tool reads for holder names). It never imports app.tools,
so the benchmark cannot reward the agent for agreeing with its own tool
wrappers.
"""

from datetime import datetime, timezone
import math

from app import store

from .schemas import GroundTruth, Task

SEASON = "2025-26"
CATS = ["PTS", "REB", "AST", "STL", "BLK"]


class SkipTask(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _q(sql: str, params: list | None = None) -> list:
    con = store.connect(read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


def _qd(sql: str, params: list | None = None) -> list[dict]:
    con = store.connect(read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()


def _tables() -> set[str]:
    return {r[0] for r in _q("SHOW TABLES")}


def _leader(cat: str):
    rows = _q(
        f"SELECT PLAYER_ID, PLAYER, TEAM, GP, {cat} FROM "
        f"silver_leaders_{cat.lower()} WHERE _season = ? ORDER BY RANK LIMIT 1",
        [SEASON],
    )
    if not rows:
        raise SkipTask(f"leaders table empty for {cat}")
    return rows[0]


def gen_lookup(rng, ctx) -> tuple[Task, GroundTruth]:
    cat = rng.choice(CATS)
    pid, name, team, gp, value = _leader(cat)
    pool = _q(
        "SELECT PLAYER FROM silver_leaders_pts WHERE _season = ? "
        "ORDER BY RANK LIMIT 50", [SEASON],
    )
    if not pool:
        raise SkipTask("no top-50 scorers in warehouse")
    sample = rng.choice(pool)[0]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="lookup",
        question=(f"Who leads the league in {cat} for the {SEASON} season, "
                  f"and how many does he have?"),
        entities=[sample, name], gold_tool_families=["lookup"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"leader_name": name, "leader_value": value, "team": team},
        computed_at=_now(), source=f"nba_api via silver_leaders_{cat.lower()}",
    )
    return task, truth


def gen_compare(rng, ctx) -> tuple[Task, GroundTruth]:
    # Gold tool get_compare reports PER-GAME values from cached gamelogs
    # (round(sum / gp, 1)), not season totals. Ground truth replicates that
    # math so quoting the tool's output is the correct strategy.
    cat = rng.choice(CATS)
    rows = _q(
        f"SELECT PLAYER_ID, PLAYER, GP, {cat} FROM silver_leaders_{cat.lower()} "
        "WHERE _season = ? ORDER BY RANK LIMIT 80", [SEASON],
    )
    rows = [r for r in rows if (r[2] or 0) > 0]
    if len(rows) < 2:
        raise SkipTask(f"too few leaders for {cat}")
    for _ in range(20):
        a, b = rng.sample(rows, 2)
        ga = _q("SELECT PTS, REB, AST, STL, BLK FROM silver_player_gamelogs "
                "WHERE _season = ? AND _entity = ?",
                [SEASON, f"player:{a[0]}"])
        gb = _q("SELECT PTS, REB, AST, STL, BLK FROM silver_player_gamelogs "
                "WHERE _season = ? AND _entity = ?",
                [SEASON, f"player:{b[0]}"])
        if not ga or not gb:
            # get_compare would fall back to live fetch; gen needs cached
            # gamelogs to pin down the same numbers.
            continue
        col = {"PTS": 0, "REB": 1, "AST": 2, "STL": 3, "BLK": 4}[cat]
        a_pg = round(sum(_fnum(g[col]) for g in ga) / len(ga), 1)
        b_pg = round(sum(_fnum(g[col]) for g in gb) / len(gb), 1)
        if a_pg == b_pg:
            continue  # tool rounds to 1dp; a tie there is ungradeable
        leader = a if a_pg > b_pg else b
        tid = ctx["task_id"]
        task = Task(
            task_id=tid, family="compare",
            question=(f"Compare {a[1]} vs {b[1]} on {cat} this season. "
                      f"Who leads per game and by how much?"),
            entities=[a[1], b[1]], gold_tool_families=["compare"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid,
            facts={"a_name": a[1], "b_name": b[1], "a_value": a_pg,
                   "b_value": b_pg, "leader_name": leader[1]},
            computed_at=_now(),
            source=f"nba_api via silver_player_gamelogs (per-game, as get_compare)",
        )
        return task, truth
    raise SkipTask(f"no gamelog-backed compare pair for {cat}")


def _parse_gamedate(raw: str) -> tuple:
    try:
        return (0, datetime.strptime(str(raw), "%b %d, %Y"))
    except (TypeError, ValueError):
        return (1, str(raw or ""))


def gen_chain(rng, ctx) -> tuple[Task, GroundTruth]:
    # Find players whose latest gamelog game has a cached boxscore directly,
    # instead of blind retries (boxscore coverage is thin; random sampling
    # almost always misses).
    box_ids = {str(r[0]) for r in _q(
        "SELECT DISTINCT GAME_ID FROM silver_boxscores WHERE _season = ?",
        [SEASON]) if r[0] is not None}
    if not box_ids:
        raise SkipTask("no cached boxscores in warehouse")
    cands = []
    for (entity,) in _q("SELECT DISTINCT _entity FROM silver_player_gamelogs "
                        "WHERE _season = ?", [SEASON]):
        try:
            pid = int(str(entity).split(":")[1])
        except (IndexError, ValueError):
            continue
        name_rows = _q("SELECT PLAYER FROM silver_leaders_pts WHERE "
                       "_season = ? AND PLAYER_ID = ? LIMIT 1",
                       [SEASON, pid])
        if not name_rows:
            continue
        games = _q("SELECT Game_ID, GAME_DATE, MATCHUP, PTS FROM "
                   "silver_player_gamelogs WHERE _season = ? AND _entity = ?",
                   [SEASON, entity])
        if not games:
            continue
        games = sorted(games, key=lambda g: _parse_gamedate(g[1]))
        gid, date, matchup, pts = games[-1]
        if str(gid) not in box_ids:
            continue
        cands.append((name_rows[0][0], str(gid), date, matchup, pts))
    if not cands:
        raise SkipTask("no sampled latest game has a cached boxscore")
    name, gid, date, matchup, pts = rng.choice(cands)
    box = _q("SELECT firstName, familyName, points FROM silver_boxscores "
             "WHERE GAME_ID = ?", [gid])
    if not box:
        raise SkipTask("no sampled latest game has a cached boxscore")
    top = max(box, key=lambda r: r[2] or 0)
    top_name = f"{top[0] or ''} {top[1] or ''}".strip()
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="chain",
        question=(f"What was {name}'s latest game ({date} {matchup}), and "
                  f"who scored the most points in that game's boxscore?"),
        entities=[name, str(gid)], gold_tool_families=["chain"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"player_name": name, "game_id": str(gid),
               "latest_pts": pts, "boxscore_top_scorer": top_name,
               "boxscore_top_pts": top[2]},
        computed_at=_now(),
        source="nba_api via silver_player_gamelogs plus silver_boxscores",
    )
    return task, truth


def gen_adjudicate(rng, ctx) -> tuple[Task, GroundTruth]:
    ents = _q("SELECT DISTINCT _entity FROM silver_on_off WHERE _season = ?",
              [SEASON])
    if not ents:
        raise SkipTask("no on_off rows in warehouse")
    cands = []
    for (entity,) in ents:
        try:
            pid = int(str(entity).split(":")[1])
        except (IndexError, ValueError):
            continue
        lead = _q("SELECT PLAYER, RANK FROM silver_leaders_pts WHERE "
                  "_season = ? AND PLAYER_ID = ? LIMIT 1", [SEASON, pid])
        if lead:
            cands.append((pid, lead[0][0], lead[0][1]))
    if not cands:
        raise SkipTask("no on_off player found in leaders")
    total = _q("SELECT COUNT(*) FROM silver_leaders_pts WHERE _season = ?",
               [SEASON])[0][0]
    pid, name, rank = rng.choice(cands)
    pct = round(100 * (1 - (rank - 1) / max(total, 1)), 1)
    rows = _q("SELECT \"On\", \"Off\", \"On-Off\" FROM silver_on_off WHERE "
              "_season = ? AND _entity = ?", [SEASON, f"player:{pid}"])
    net = None
    for on, off, diff in rows:
        try:
            net = round(float(diff if diff not in (None, "") else
                              float(on or 0) - float(off or 0)), 1)
            break
        except (TypeError, ValueError):
            continue
    if net is None:
        raise SkipTask(f"no usable on_off split for {name}")
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="adjudicate",
        question=(f"Do {name}'s percentile rank and on/off numbers agree "
                  f"this season? Give both numbers."),
        entities=[name], gold_tool_families=["adjudicate"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"player_name": name, "percentile": pct, "onoff_net": net},
        computed_at=_now(),
        source="nba_api via silver_leaders_pts plus pbpstats via silver_on_off",
    )
    return task, truth


def gen_trade(rng, ctx) -> tuple[Task, GroundTruth]:
    # Ground truth replicates get_trade_check's salary-matching rule exactly:
    # teams/payrolls from the salary sheet (so the tool's payroll matching
    # accepts the players), 125% + $250k below the first apron, 100% above it.
    # A 1-for-1 never trips the second-apron aggregation ban.
    APRON1 = 209_661_000
    rows = _q("SELECT PLAYER_NAME, TEAM, SALARY_2025_26 FROM silver_salaries "
              "WHERE SALARY_2025_26 > 0")
    if len(rows) < 2:
        raise SkipTask("salary sheet too thin")
    payroll: dict = {}
    for _, team, sal in rows:
        payroll[team] = payroll.get(team, 0) + (sal or 0)

    def _allowed(sal: int, team: str) -> int:
        if payroll.get(team, 0) > APRON1:
            return sal
        return int(sal * 1.25 + 250_000)

    for _ in range(50):
        a, b = rng.sample(rows, 2)
        if a[1] == b[1]:
            continue
        allow_a = _allowed(a[2], a[1])
        allow_b = _allowed(b[2], b[1])
        break
    else:
        raise SkipTask("no cross-team salary pair found")
    legal = (b[2] <= allow_a) and (a[2] <= allow_b)
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="trade",
        question=(f"Can {a[1]} trade {a[0]} straight up for {b[0]} "
                  f"of {b[1]}? Check the salary-matching rule."),
        entities=[a[0], b[0]], gold_tool_families=["trade"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"player_a": a[0], "team_a": a[1], "salary_a": a[2],
               "player_b": b[0], "team_b": b[1], "salary_b": b[2],
               "allowed_a": allow_a, "allowed_b": allow_b,
               "legal_numeric": int(legal)},
        computed_at=_now(),
        source="bref_contracts via silver_salaries "
               "(same matching rule as get_trade_check)",
    )
    return task, truth


def gen_brief(rng, ctx) -> tuple[Task, GroundTruth]:
    dates = _q("SELECT DISTINCT _entity FROM silver_scoreboard "
               "WHERE _season = ?", [SEASON])
    if not dates:
        raise SkipTask("no scoreboard dates in warehouse")
    entity = rng.choice(dates)[0]
    day = entity.split("date:", 1)[1] if "date:" in entity else entity
    games = _q("SELECT GAME_ID, HOME_TEAM_ABBREVIATION, "
               "VISITOR_TEAM_ABBREVIATION FROM silver_scoreboard WHERE "
               "_season = ? AND _entity = ?", [SEASON, entity])
    if not games:
        raise SkipTask(f"no games cached for {day}")
    teams = sorted({g[1] for g in games if g[1]} |
                   {g[2] for g in games if g[2]})
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="brief",
        question=(f"Give me the slate briefing for {day}: how many games "
                  f"are on and which teams play?"),
        entities=teams, gold_tool_families=["brief"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"game_date": day, "game_count": len(games),
               "teams": ", ".join(teams)},
        computed_at=_now(), source="nba_api via silver_scoreboard",
    )
    return task, truth


def gen_finder(rng, ctx) -> tuple[Task, GroundTruth]:
    if "silver_hist_gamelogs" not in _tables():
        raise SkipTask("no history tables in warehouse")
    teams = _q("SELECT DISTINCT team_abbreviation FROM silver_hist_gamelogs "
               "WHERE _season = ?", [SEASON])
    if not teams:
        raise SkipTask("history table empty for season")
    abbr = rng.choice(teams)[0]
    rows = _q("SELECT wl FROM silver_hist_gamelogs WHERE _season = ? AND "
              "team_abbreviation = ? ORDER BY game_date", [SEASON, abbr])
    best = cur = 0
    for (wl,) in rows:
        cur = cur + 1 if wl == "W" else 0
        best = max(best, cur)
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="finder",
        question=(f"What is {abbr}'s longest win streak this season, "
                  f"and how many games are in the sample?"),
        entities=[abbr], gold_tool_families=["finder"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"team": abbr, "longest_win_streak": best,
               "games": len(rows)},
        computed_at=_now(), source="warehouse via silver_hist_gamelogs",
    )
    return task, truth


def _fnum(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _opp_abbrev(matchup: str) -> str:
    toks = str(matchup or "").split()
    if not toks:
        return ""
    return toks[-1].strip(".,;:!?()[]")


def _pct(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def gen_comps(rng, ctx) -> tuple[Task, GroundTruth]:
    # Ground truth mirrors get_comps' feature pipeline exactly (18 features:
    # 8 counting stats per-36, FG3%/FT%, 8 advanced; mean-imputation via
    # zero z-scores; zero-variance features dropped; similarity =
    # round(100 / (1 + d / 20), 1)) so quoting the tool is the right play.
    count_cols = ["PTS", "REB", "AST", "STL", "BLK", "FG3A", "FTA", "TOV"]
    pct_cols = ["FG3_PCT", "FT_PCT"]
    adv_cols = ["USG_PCT", "TS_PCT", "AST_PCT", "TM_TOV_PCT", "PIE",
                "OFF_RATING", "DEF_RATING", "NET_RATING"]
    top50 = _q("SELECT PLAYER_ID, PLAYER, MIN FROM silver_leaders_pts "
               "WHERE _season = ? ORDER BY RANK LIMIT 50", [SEASON])
    cands = [r for r in top50 if (_pct(r[2]) or 0) >= 400]
    if not cands:
        raise SkipTask("no top-50 scorer with 400+ minutes")
    trow = rng.choice(cands)
    tid_target, tname = trow[0], trow[1]
    cols = ", ".join(["PLAYER_ID", "PLAYER", "MIN"] + count_cols + pct_cols)
    pool = _q(f"SELECT {cols} FROM silver_leaders_pts WHERE _season = ?",
              [SEASON])
    pool = [r for r in pool if (_pct(r[2]) or 0) >= 400]
    if len(pool) < 10:
        raise SkipTask("comp pool too small")
    adv: dict = {}
    for r in _q("SELECT PLAYER_ID, USG_PCT, TS_PCT, AST_PCT, TM_TOV_PCT, "
                "PIE, OFF_RATING, DEF_RATING, NET_RATING FROM silver_advanced "
                "WHERE _season = ?", [SEASON]):
        adv[str(r[0])] = r[1:]
    use_adv = bool(adv)

    def _vec(row) -> list:
        minutes = _pct(row[2])
        out = []
        for i in range(3, 11):
            v = _pct(row[i])
            out.append(36 * v / minutes
                       if (minutes or 0) > 0 and v is not None else None)
        out += [_pct(row[11]), _pct(row[12])]
        if use_adv:
            arow = adv.get(str(row[0]), (None,) * 8)
            out += [_pct(v) for v in arow]
        return out

    vecs = [(r[0], r[1], _vec(r)) for r in pool]
    nfeat = len(vecs[0][2])
    stats: list = []
    for j in range(nfeat):
        vals = [v[j] for _, _, v in vecs
                if isinstance(v[j], (int, float))]
        if len(vals) < 2:
            stats.append(None)
            continue
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / len(vals)
        if var <= 0:
            stats.append(None)
            continue
        stats.append((mean, math.sqrt(var)))
    keep = [j for j, s in enumerate(stats) if s is not None]
    if not keep:
        raise SkipTask("comp features have zero variance")

    def _z(v, s):
        if v is None or s[1] <= 1e-9:
            return 0.0
        return (v - s[0]) / s[1]

    z = {pid: [_z(v[j], stats[j]) for j in keep]
         for pid, _, v in vecs}
    tkey = next((pid for pid in z if str(pid) == str(tid_target)), None)
    if tkey is None:
        raise SkipTask("comp target not in pool")
    zt = z[tkey]
    if all(v == 0.0 for v in zt):
        raise SkipTask("comp target has no usable stats")
    dists = []
    for pid, zv in z.items():
        if str(pid) == str(tkey):
            continue
        dists.append((math.sqrt(sum((a - b) ** 2
                                    for a, b in zip(zt, zv))), pid))
    dists.sort(key=lambda d: d[0])
    if len(dists) < 3:
        raise SkipTask("comp pool too small")
    by_id = {r[0]: r[1] for r in pool}
    names = [by_id[pid] for _, pid in dists[:3]]
    sims = [round(100 / (1 + d / 20), 1) for d, _ in dists[:3]]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="comps",
        question=(f"Which players play most like {tname} statistically "
                  f"this season? Name the 3 closest."),
        entities=[tname] + names, gold_tool_families=["comps"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"names": {"comp1": names[0], "comp2": names[1],
                         "comp3": names[2]},
                "similarity_1": sims[0], "similarity_2": sims[1],
                "similarity_3": sims[2]},
        computed_at=_now(),
        source="nba_api via silver_leaders_pts plus silver_advanced "
               "(same 18-feature pipeline as get_comps)",
    )
    return task, truth


def gen_splits(rng, ctx) -> tuple[Task, GroundTruth]:
    rated = _q("SELECT TEAM_ID FROM silver_team_ratings "
               "ORDER BY DEF_RATING ASC LIMIT 10")
    if not rated:
        raise SkipTask("no team ratings in warehouse")
    id2abbr: dict = {}
    for tid, abbr in _q("SELECT TEAM_ID, TEAM FROM silver_leaders_pts "
                        "WHERE _season = ?", [SEASON]):
        id2abbr.setdefault(tid, abbr)
        id2abbr.setdefault(str(tid), abbr)
    top_abbr = {id2abbr.get(t[0]) for t in rated} - {None, ""}
    if not top_abbr:
        raise SkipTask("cannot map top defenses to abbreviations")
    ents = _q("SELECT _entity FROM silver_player_gamelogs WHERE _season = ? "
              "GROUP BY _entity HAVING COUNT(*) >= 20", [SEASON])
    if not ents:
        raise SkipTask("no player gamelogs in warehouse")
    picked = None
    for _ in range(10):
        entity = rng.choice(ents)[0]
        try:
            pid = int(str(entity).split(":")[1])
        except (IndexError, ValueError):
            continue
        name_rows = _q("SELECT PLAYER FROM silver_leaders_pts WHERE "
                       "_season = ? AND PLAYER_ID = ? LIMIT 1",
                       [SEASON, pid])
        if not name_rows:
            continue
        games = _q("SELECT GAME_DATE, MATCHUP, PTS FROM "
                   "silver_player_gamelogs WHERE _season = ? AND _entity = ?",
                   [SEASON, entity])
        games = sorted(games, key=lambda g: _parse_gamedate(g[0]))
        last15 = games[-15:]
        if len(last15) < 15:
            continue
        ppg_all = round(sum(_fnum(g[2]) for g in last15) / 15, 1)
        vs = [_fnum(g[2]) for g in last15
              if _opp_abbrev(g[1]) in top_abbr]
        if not vs:
            continue
        picked = (name_rows[0][0], round(sum(vs) / len(vs), 1), ppg_all,
                  len(vs))
        break
    if picked is None:
        raise SkipTask("no sampled player faced a top-10 defense lately")
    name, ppg_vs, ppg_all, k = picked
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="splits",
        question=(f"How does {name} perform against top-10 defenses over "
                  f"his last 15 games? Give his PPG in those matchups and "
                  f"his overall last-15 PPG."),
        entities=[name], gold_tool_families=["splits"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"player_name": name, "last15_games": 15,
               "vs_top10_games": k, "ppg_vs_top10": ppg_vs,
               "ppg_last15": ppg_all},
        computed_at=_now(),
        source="nba_api via silver_player_gamelogs plus silver_team_ratings",
    )
    return task, truth


def _tnorm(s) -> str:
    import unicodedata as _ud
    return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                  if not _ud.combining(c)).strip().lower()


def gen_trade_value(rng, ctx) -> tuple[Task, GroundTruth]:
    # Ground truth replicates get_trade_value's value model exactly:
    # production_score = round(sum(per-game stat * weight), 2) with weights
    # PTS 1.0 / REB 1.2 / AST 1.5 / STL 2.0 / BLK 2.0 / TOV -1.5,
    # dollars_per_point over qualified (gp>=20, salaried) players,
    # est_market_value_m = round(score * dpp / 1e6, 1), winner by side delta.
    PROD_SEASON, SAL_SEASON = "2025-26", "2026-27"
    tables = _tables()
    leaders: dict = {}
    for r in _q("SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV, "
                "FG3M, FG3_PCT FROM silver_leaders_pts WHERE _season = ?",
                [PROD_SEASON]):
        leaders.setdefault(_tnorm(r[0]), {
            "name": r[0], "team": r[1], "gp": r[2] or 0,
            "tot": {"PTS": r[3] or 0, "REB": r[4] or 0, "AST": r[5] or 0,
                    "STL": r[6] or 0, "BLK": r[7] or 0, "TOV": r[8] or 0}})
    if not leaders:
        raise SkipTask("no leader rows for trade value")
    lcols = {row[1] for row in _q("PRAGMA table_info(silver_leaders_pts)")}
    weights = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
               "STL": 2.0, "BLK": 2.0, "TOV": -1.5}
    use_w = {c: (0.0 if c not in lcols else w) for c, w in weights.items()}
    salaries: dict = {}
    scols: set = set()
    sparams: list = []
    if "silver_salaries" in tables:
        scols = {row[1] for row in _q("PRAGMA table_info(silver_salaries)")}
        scol = ("SALARY_2025_26" if "SALARY_2025_26" in scols
                else next((c for c in scols if "SALARY" in c.upper()), ""))
        if "_season" in scols:
            sparams = [SAL_SEASON]
        if scol:
            q = f"SELECT PLAYER_NAME, {scol} FROM silver_salaries"
            if "_season" in scols:
                q += " WHERE _season = ?"
            for r in _q(q, sparams):
                if r[1] is not None:
                    salaries.setdefault(_tnorm(r[0]), int(r[1]))
    if "silver_cap_players" in tables:
        ccols = {row[1] for row in _q("PRAGMA table_info(silver_cap_players)")}
        q = "SELECT player, salary FROM silver_cap_players"
        cparams: list = []
        if "_season" in ccols:
            q += " WHERE _season = ?"
            cparams = [SAL_SEASON]
        for r in _q(q, cparams):
            if r[1] is not None:
                salaries.setdefault(_tnorm(r[0]), int(r[1]))
    if not salaries:
        raise SkipTask("no salary rows for trade value")

    def _score(tot: dict, gp: int) -> float:
        return sum(tot[c] / gp * use_w[c] for c in use_w)

    dpp_total = dpp_score = 0.0
    for key, lead in leaders.items():
        gp = lead["gp"]
        if gp < 20 or key not in salaries:
            continue
        dpp_total += salaries[key]
        dpp_score += _score(lead["tot"], gp)
    if not dpp_score:
        raise SkipTask("no qualified salary plus production overlap")
    dpp = dpp_total / dpp_score
    # Sample from the salary-sheet roster so get_trade_value's payroll
    # matching accepts the (team, player) pairs in the question.
    sheet: dict = {}
    sq = "SELECT PLAYER_NAME, TEAM FROM silver_salaries"
    if "_season" in scols:
        sq += " WHERE _season = ?"
    for r in _q(sq, sparams):
        sheet.setdefault(_tnorm(r[0]), (r[0], (r[1] or "").upper()))
    elig = []
    for key, lead in leaders.items():
        if lead["gp"] < 20 or key not in salaries or key not in sheet:
            continue
        sname, steam = sheet[key]
        score = round(_score(lead["tot"], lead["gp"]), 2)
        est_m = round(score * dpp / 1e6, 1)
        elig.append({"name": sname, "team": steam, "est_m": est_m})
    if len(elig) < 2:
        raise SkipTask("too few trade-value-eligible players")
    a = b = None
    delta = 0.0
    for _ in range(50):
        x, y = rng.sample(elig, 2)
        if x["team"] == y["team"]:
            continue
        d = round(x["est_m"] - y["est_m"], 1)
        if abs(d) >= 0.5:
            a, b, delta = x, y, d
            break
    if a is None:
        raise SkipTask("no decisive cross-team trade-value pair found")
    winner = a["name"] if delta >= 0.5 else b["name"]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="trade_value",
        question=(f"Who wins this trade on production value vs salary: "
                  f"{a['name']} ({a['team']}) for {b['name']} "
                  f"({b['team']})? Name the winner."),
        entities=[a["name"], b["name"]],
        gold_tool_families=["trade_value"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"player_a": a["name"], "player_b": b["name"],
               "value_a": a["est_m"], "value_b": b["est_m"],
               "names": {"winner": winner}},
        computed_at=_now(),
        source="nba_api via silver_leaders_pts plus bref via silver_salaries "
               "(same value model as get_trade_value)",
    )
    return task, truth


def gen_awards(rng, ctx) -> tuple[Task, GroundTruth]:
    # Ground truth replicates get_award_race's MVP model exactly: z-scored
    # weighted components (PPG .35, team win% .20, net rating .15, APG .15,
    # RPG .15) over qualified candidates (GP>=20, MIN>=500); candidate score
    # = round(total, 2). Quoting the tool's scores is the correct strategy.
    import statistics as _st
    pool = _q(
        """SELECT l.PLAYER AS player, l.TEAM AS team,
        l.GP AS gp, l.MIN AS mins,
        l.PTS * 1.0 / NULLIF(l.GP, 0) AS ppg,
        l.REB * 1.0 / NULLIF(l.GP, 0) AS rpg,
        l.AST * 1.0 / NULLIF(l.GP, 0) AS apg,
        a.NET_RATING AS net_rating,
        s.WINS * 1.0 / NULLIF(s.WINS + s.LOSSES, 0) AS team_win_pct
        FROM silver_leaders_pts l
        LEFT JOIN silver_advanced a
        ON CAST(a.PLAYER_ID AS VARCHAR) = CAST(l.PLAYER_ID AS VARCHAR)
        AND a._season = l._season
        LEFT JOIN silver_standings s
        ON s.TeamID = l.TEAM_ID AND s._season = l._season
        WHERE l._season = ?""",
        [SEASON],
    )
    comps = [("ppg", 0.35), ("team_win_pct", 0.20), ("net_rating", 0.15),
             ("apg", 0.15), ("rpg", 0.15)]
    # NB: keys must follow the SELECT column order, not comps order.
    keys = ["player", "team", "gp", "mins",
            "ppg", "rpg", "apg", "net_rating", "team_win_pct"]
    eligible = []
    for r in pool:
        row = dict(zip(keys, r))
        try:
            if (row["gp"] or 0) < 20 or (row["mins"] or 0) < 500:
                continue
            if any(row[c] is None for c, _ in comps):
                continue
            row.update({c: float(row[c]) for c, _ in comps})
        except (TypeError, ValueError):
            continue
        eligible.append(row)
    if len(eligible) < 3:
        raise SkipTask("too few qualified MVP candidates")
    means, stds = {}, {}
    for c, _ in comps:
        vals = [row[c] for row in eligible]
        means[c] = sum(vals) / len(vals)
        stds[c] = _st.pstdev(vals) if len(vals) > 1 else 0.0
    scored = []
    for row in eligible:
        total = 0.0
        for c, w in comps:
            std = stds[c]
            z = 0.0 if std < 1e-9 else (row[c] - means[c]) / std
            total += w * z
        scored.append((total, row))
    scored.sort(key=lambda t: t[0], reverse=True)
    top3 = [(round(total, 2), row["player"]) for total, row in scored[:3]]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="awards",
        question="Who are the top-3 MVP candidates right now? Name all three.",
        entities=[n for _, n in top3], gold_tool_families=["awards"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"names": {"mvp1": top3[0][1], "mvp2": top3[1][1],
                         "mvp3": top3[2][1]},
               "mvp_score_1": top3[0][0],
               "mvp_score_2": top3[1][0],
               "mvp_score_3": top3[2][0]},
        computed_at=_now(),
        source="nba_api via silver_leaders_pts plus silver_advanced plus "
               "silver_standings (same z-score model as get_award_race)",
    )
    return task, truth

# ---------------------------------------------------------------------------
# streaks family: mirrors get_streaks' pipeline exactly (compute_streaks
# over warehouse gamelogs: per-holder runs, longest-run tie-break to the
# later end date, cross-holder ranking by streak desc, end_date desc,
# holder name asc). Mode is always longest: active streaks have multiple
# winners and are ungradeable. Quoting the tool's top row is the right play.
# ---------------------------------------------------------------------------

# (question noun, stat key, threshold, scope)
_STREAK_CONFIGS = [
    ("30+ point", "PTS", 30.0, "player"),
    ("10+ rebound", "REB", 10.0, "player"),
    ("10+ assist", "AST", 10.0, "player"),
    ("4+ three-pointer", "FG3M", 4.0, "player"),
    ("win", "W", None, "team"),
]


def _static_player_names() -> dict:
    try:
        from nba_api.stats.static import players as _players
        return {p.get("id"): p.get("full_name")
                for p in _players.get_players()}
    except Exception:
        return {}


def _streak_player_games() -> list[dict]:
    names = _static_player_names()
    games = []
    for pid, gdate, pts, reb, ast, stl, blk, fg3m in _q(
            "SELECT Player_ID, GAME_DATE, PTS, REB, AST, STL, BLK, FG3M "
            "FROM silver_player_gamelogs WHERE _season = ? "
            "ORDER BY Player_ID, GAME_DATE", [SEASON]):
        parsed = _parse_gamedate(gdate)
        d = parsed[1].date() if parsed[0] == 0 else None
        if d is None:
            continue
        try:
            ipid = int(pid)
        except (TypeError, ValueError):
            continue
        games.append({
            "holder": names.get(ipid) or f"Player {ipid}",
            "holder_id": ipid, "date": d,
            "PTS": pts, "REB": reb, "AST": ast,
            "STL": stl, "BLK": blk, "FG3M": fg3m,
        })
    return games


def _streak_team_games() -> tuple[list[dict], dict]:
    cols = {r[1] for r in _q("PRAGMA table_info(silver_hist_gamelogs)")}
    q = ("SELECT team_abbreviation, team_name, game_date, wl FROM "
         "silver_hist_gamelogs WHERE _season = ?")
    if "season_type" in cols:
        q += " AND season_type = 'regular-season'"
    games, abbr2name = [], {}
    for abbr, tname, gdate, wl in _q(q + " ORDER BY team_abbreviation, "
                                     "game_date", [SEASON]):
        try:
            d = datetime.strptime(str(gdate or "").strip(),
                                  "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        key = str(abbr or "").upper()
        abbr2name[key] = tname or key
        games.append({"holder": key, "holder_id": key, "date": d,
                      "WL": str(wl or "").upper()})
    return games, abbr2name


def _rank_streaks(games: list[dict], stat_key: str,
                  threshold: float | None) -> list[dict]:
    # Verbatim mirror of the tool's longest-mode ranking.
    def _cond(g: dict) -> bool:
        if stat_key == "W":
            return str(g.get("WL") or "").upper() == "W"
        return _fnum(g.get(stat_key)) >= (threshold or 0.0)

    by_holder: dict = {}
    for g in games:
        if g.get("date") is None:
            continue
        by_holder.setdefault((g["holder_id"], g["holder"]), []).append(g)
    out = []
    for (hid, holder), gs in by_holder.items():
        gs = sorted(gs, key=lambda g: g["date"])
        runs: list = []
        i = 0
        while i < len(gs):
            if not _cond(gs[i]):
                i += 1
                continue
            j = i
            while j + 1 < len(gs) and _cond(gs[j + 1]):
                j += 1
            runs.append((i, j))
            i = j + 1
        if not runs:
            continue
        best = max(ei - si for si, ei in runs)
        si, ei = max((r for r in runs if r[1] - r[0] == best),
                     key=lambda r: r[1])
        out.append({"holder": holder, "holder_id": hid,
                    "streak": ei - si + 1,
                    "end_date": gs[ei]["date"].isoformat()})
    out.sort(key=lambda s: str(s["holder"]))
    out.sort(key=lambda s: s["end_date"], reverse=True)
    out.sort(key=lambda s: -s["streak"])
    return out[:10]


def gen_streaks(rng, ctx) -> tuple[Task, GroundTruth]:
    idx = int(ctx["task_id"].split("-")[1])
    order = [_STREAK_CONFIGS[(idx + i) % len(_STREAK_CONFIGS)]
             for i in range(len(_STREAK_CONFIGS))]
    head, tail = order[0], order[1:]
    rng.shuffle(tail)
    for noun, stat_key, thr, scope in [head] + tail:
        if scope == "player":
            games = _streak_player_games()
            abbr2name = {}
        else:
            games, abbr2name = _streak_team_games()
        if not games:
            continue
        ranked = _rank_streaks(games, stat_key, thr)
        if not ranked or ranked[0]["streak"] < 2:
            continue
        top = ranked[0]
        if scope == "player":
            if str(top["holder"]).startswith("Player "):
                continue  # unresolved name: ungradeable
            name = top["holder"]
            question = (f"Who has the longest streak of {noun} games this "
                        f"season, and how long is the streak?")
            facts = {"names": {"streak_leader": name},
                     "streak_games": top["streak"], "threshold": thr}
        else:
            name = abbr2name.get(top["holder"], top["holder"])
            question = ("Which team has the longest win streak this season, "
                        "and how long is it?")
            facts = {"names": {"streak_leader": name},
                     "streak_games": top["streak"]}
        tid = ctx["task_id"]
        task = Task(
            task_id=tid, family="streaks", question=question,
            entities=[name], gold_tool_families=["streaks"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid, facts=facts, computed_at=_now(),
            source="nba_api via silver_player_gamelogs / "
                   "silver_hist_gamelogs (same streak ranking as get_streaks)",
        )
        return task, truth
    raise SkipTask("no gradeable streak in warehouse")


# ---------------------------------------------------------------------------
# lineups family: mirrors get_lineup_stats' pipeline exactly (play-level
# possession aggregates with reconstructed blowout margins; estimated
# MIN*2 fallback when possession data is missing; per-100 ratings
# round(x,1); 100-possession sample floor). Ground truth is the best net
# rating over ALL floor-passing units: the question asks for the best at
# the 100-possession floor and the agent can page past the tool's
# default limit-10 display slice.
# ---------------------------------------------------------------------------

_BLOWOUT_MARGIN = 20


def _lineup_key_gid(gid) -> tuple | None:
    try:
        parts = [int(p) for p in str(gid).split("-")
                 if p.strip().isdigit()]
        if len(parts) == 5:
            return tuple(sorted(parts))
    except (TypeError, ValueError):
        pass
    return None


def _lineup_possession_aggs(team_id: int) -> dict | None:
    rows = _qd(
        "SELECT game_id, possession_number, offense_team_id, "
        "defense_team_id, points, "
        "off_player_1, off_player_2, off_player_3, off_player_4, "
        "off_player_5, def_player_1, def_player_2, def_player_3, "
        "def_player_4, def_player_5 FROM silver_hist_possessions "
        "WHERE _season = ? AND (offense_team_id = ? OR "
        "defense_team_id = ?) AND count_as_possession = 'true'",
        [SEASON, team_id, team_id])
    if not rows:
        return None
    rows.sort(key=lambda r: (str(r.get("game_id")),
                             int(r.get("possession_number") or 0)))
    agg: dict = {}
    runs: dict = {}
    for r in rows:
        try:
            off_tid = int(r["offense_team_id"])
            def_tid = int(r["defense_team_id"])
            pts = int(r["points"] or 0)
        except (TypeError, ValueError, KeyError):
            continue
        game = str(r.get("game_id"))
        run = runs.setdefault(game, {})
        off_run, def_run = run.get(off_tid, 0), run.get(def_tid, 0)
        if off_tid == team_id:
            margin = off_run - def_run
            players = [r.get(f"off_player_{i}") for i in range(1, 6)]
        elif def_tid == team_id:
            margin = def_run - off_run
            players = [r.get(f"def_player_{i}") for i in range(1, 6)]
        else:
            continue
        if any(p is None for p in players):
            continue
        try:
            unit = tuple(sorted(int(p) for p in players))
        except (TypeError, ValueError):
            continue
        a = agg.setdefault(unit, {"off_poss": 0, "def_poss": 0, "pf": 0,
                                  "pa": 0, "blowout": 0})
        if off_tid == team_id:
            a["off_poss"] += 1
            a["pf"] += pts
        else:
            a["def_poss"] += 1
            a["pa"] += pts
        if abs(margin) >= _BLOWOUT_MARGIN:
            a["blowout"] += 1
        run[off_tid] = off_run + pts
        run[def_tid] = def_run
    return agg or None


def _lineup_shown_units(team_id: int, min_poss: int = 100,
                        limit: int | None = None) -> list[dict]:
    rows = _qd("SELECT GROUP_NAME, GROUP_ID, GP, MIN, PTS, PLUS_MINUS "
               "FROM silver_lineups WHERE _season = ? AND _entity = ?",
               [SEASON, f"team:{team_id}"])
    if not rows:
        return []
    agg = _lineup_possession_aggs(team_id)
    units = []
    for r in rows:
        key = _lineup_key_gid(r.get("GROUP_ID"))
        a = agg.get(key) if (agg is not None and key is not None) else None
        if a is not None:
            off_poss, def_poss = a["off_poss"], a["def_poss"]
            pf, pa = float(a["pf"]), float(a["pa"])
            poss = off_poss + def_poss
        else:
            poss = int(round(float(r.get("MIN") or 0) * 2))
            off_poss = def_poss = poss // 2
            pf = float(r.get("PTS") or 0)
            pa = pf - float(r.get("PLUS_MINUS") or 0)
        if off_poss <= 0 or def_poss <= 0:
            off_r = def_r = net_r = 0.0
        else:
            off_r = round(pf / off_poss * 100, 1)
            def_r = round(pa / def_poss * 100, 1)
            net_r = round(off_r - def_r, 1)
        units.append({"name": r.get("GROUP_NAME") or "unknown",
                      "poss": poss, "OFF_RATING": off_r,
                      "DEF_RATING": def_r, "NET_RATING": net_r})
    units.sort(key=lambda u: u["poss"], reverse=True)
    visible = [u for u in units if u["poss"] >= min_poss]
    # Ground truth spans ALL floor-passing units, not the tool's default
    # limit-10 display slice: the question asks for the best net rating at
    # the 100-possession floor, and the agent can page deeper via limit.
    return visible if limit is None else visible[:limit]


def gen_lineups(rng, ctx) -> tuple[Task, GroundTruth]:
    id2abbr: dict = {}
    for tid, abbr in _q("SELECT TEAM_ID, TEAM FROM silver_leaders_pts "
                        "WHERE _season = ?", [SEASON]):
        id2abbr.setdefault(tid, abbr)
        id2abbr.setdefault(str(tid), abbr)
    cands = []
    for (entity,) in _q("SELECT DISTINCT _entity FROM silver_lineups "
                        "WHERE _season = ?", [SEASON]):
        try:
            tid = int(str(entity).split(":")[1])
        except (IndexError, ValueError):
            continue
        abbr = id2abbr.get(tid) or id2abbr.get(str(tid))
        if abbr:
            cands.append((tid, abbr))
    for tid, abbr in rng.sample(cands, len(cands)):
        shown = _lineup_shown_units(tid)
        if len(shown) < 2:
            continue
        nets = [u["NET_RATING"] for u in shown]
        best = max(nets)
        if nets.count(best) > 1:
            continue  # tied best net is ungradeable
        top = next(u for u in shown if u["NET_RATING"] == best)
        tid2 = ctx["task_id"]
        task = Task(
            task_id=tid2, family="lineups",
            question=(f"Which {abbr} five-man lineup has the best net "
                      f"rating per 100 possessions this season (minimum 100 "
                      f"possessions)? Give the lineup and its net rating."),
            entities=[abbr], gold_tool_families=["lineups"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid2,
            # No names dict: five-man GROUP_NAMEs share surnames across
            # units, so last-token name_recall false-positives on wrong
            # lineups. The four numeric facts uniquely identify the unit.
            facts={"net_rating": top["NET_RATING"],
                   "off_rating": top["OFF_RATING"],
                   "def_rating": top["DEF_RATING"],
                   "possessions": top["poss"]},
            computed_at=_now(),
            source="nba_api via silver_lineups plus silver_hist_possessions "
                   "(same ratings plus sample floor as get_lineup_stats)",
        )
        return task, truth
    raise SkipTask("no team with a unique best lineup net rating")


GENERATORS = {
    "lookup": gen_lookup,
    "compare": gen_compare,
    "chain": gen_chain,
    "adjudicate": gen_adjudicate,
    "trade": gen_trade,
    "brief": gen_brief,
    "finder": gen_finder,
    "comps": gen_comps,
    "splits": gen_splits,
    "trade_value": gen_trade_value,
    "awards": gen_awards,
    "streaks": gen_streaks,
    "lineups": gen_lineups,
}
