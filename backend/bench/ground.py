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


# ---------------------------------------------------------------------------
# prediction family: mirrors get_game_prediction's pipeline exactly. Team
# ratings and league averages from silver_team_ratings, home-court 3.0
# split into both teams' projected scoring when the warehouse cache holds
# a scheduled meeting in the next 14 days (neutral site otherwise),
# injury penalties from silver_injuries, then a seeded Monte Carlo with
# np.random.default_rng(seed): normal draws, sd 12.5, plus the tool's
# tiny away tie-break noise. Win probability is the simulated home-win
# share; projected scores/totals are the simulated means. The question
# says "default settings" so the agent calls with the same defaults
# (n_sims 10000, seed 7) the ground truth replicates. The pair is
# canonicalized (sorted by abbreviation) for the question and the
# replica alike, so the facts are a pure function of the unordered pair
# and win probabilities are keyed by team abbreviation, not home/away.
# ---------------------------------------------------------------------------

_PRED_HOME_COURT_PTS = 3.0
_PRED_SCORING_SD = 12.5
_PRED_N_SIMS = 10_000
_PRED_SEED = 7
_PRED_STATUS_PENALTY = {
    "OUT": 1.0, "IR": 1.0, "SEASON": 1.0,
    "DOUBTFUL": 0.6, "QUESTIONABLE": 0.3, "DAY-TO-DAY": 0.3,
}
_PRED_MAX_INJURY_PENALTY = 3.0


def _pred_team_table() -> dict[str, dict]:
    try:
        from nba_api.stats.static import teams as _teams
        return {str(t.get("abbreviation", "")).upper(): t
                for t in _teams.get_teams()}
    except Exception:
        return {}


def _pred_rating_row(tid: int) -> dict | None:
    rows = _q("SELECT OFF_RATING, DEF_RATING, NET_RATING, PACE, GP, W, L "
              "FROM silver_team_ratings WHERE TEAM_ID = ? AND _season = ?",
              [tid, SEASON])
    if not rows:
        return None
    off, dfn, net, pace = (float(v) for v in rows[0][:4]) \
        if all(v is not None for v in rows[0][:4]) else (None,) * 4
    if off is None:
        return None
    return {"off": off, "def": dfn, "net": net, "pace": pace}


def _pred_league_means() -> tuple[float, float]:
    rows = _q("SELECT AVG(OFF_RATING), AVG(DEF_RATING) FROM "
              "silver_team_ratings WHERE _season = ? GROUP BY TEAM_ID",
              [SEASON])
    vals = [(float(r[0]), float(r[1])) for r in rows
            if r[0] is not None and r[1] is not None]
    if not vals:
        raise SkipTask("no team ratings for league means")
    return (sum(v[0] for v in vals) / len(vals),
            sum(v[1] for v in vals) / len(vals))


def _pred_meeting(ida: int, idb: int) -> tuple:
    # Verbatim mirror of the tool's _find_meeting: next-14-days scoreboard
    # scan, first row matching the pair sorted by the entity date string.
    from datetime import timedelta as _td
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    now = _dt.now(ZoneInfo("America/New_York"))
    days = [(now + _td(days=i)).strftime("%m/%d/%Y") for i in range(14)]
    ents = [f"date:{d}" for d in days]
    rows = _qd(
        "SELECT _entity, HOME_TEAM_ID, VISITOR_TEAM_ID FROM "
        "silver_scoreboard WHERE _season = ? AND _entity IN ("
        + ",".join("?" for _ in ents) + ")",
        [SEASON, *ents])
    cands = sorted(
        (r for r in rows
         if r["HOME_TEAM_ID"] is not None
         and r["VISITOR_TEAM_ID"] is not None
         and {int(r["HOME_TEAM_ID"]), int(r["VISITOR_TEAM_ID"])}
         == {ida, idb}),
        key=lambda r: (str(r["_entity"] or "")[5:]
                       if str(r["_entity"] or "").startswith("date:")
                       else ""))
    if not cands:
        return None, None, ""
    row = cands[0]
    return (int(row["HOME_TEAM_ID"]), int(row["VISITOR_TEAM_ID"]),
            str(row["_entity"] or "")[5:])


def _pred_injury_penalty(full_name: str) -> float:
    try:
        import ast as _ast
        rows = _q("SELECT injuries FROM silver_injuries "
                  "WHERE display_name = ? AND _season = ?",
                  [full_name, SEASON])
    except Exception:
        return 0.0
    if not rows or rows[0][0] is None:
        return 0.0
    try:
        items = _ast.literal_eval(str(rows[0][0]))
    except (ValueError, SyntaxError):
        return 0.0
    penalty = 0.0
    for item in items or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().upper()
        name = str((item.get("athlete") or {}).get("displayName") or "")
        if _PRED_STATUS_PENALTY.get(status, 0.0) > 0 and name:
            penalty += _PRED_STATUS_PENALTY[status]
    return round(min(penalty, _PRED_MAX_INJURY_PENALTY), 2)


def _pred_facts(abbr_a: str, abbr_b: str,
                preserve_order: bool = False) -> dict:
    # Returns the estimate dict the tool reports, or raises SkipTask.
    # Order-independent by default: the neutral-site home/away assignment
    # (which side takes the injury penalty) must not depend on caller arg
    # order, so the pair is canonicalized up front and the facts are a pure
    # function of the unordered team pair. Win probabilities are keyed by
    # team abbreviation, not by home/away role.
    #
    # preserve_order=True mirrors the product tool exactly: in the neutral
    # case get_game_prediction assigns the home role to its FIRST arg
    # (h_id = home_id or ida), so injury-penalty sides and the away
    # tie-break noise draw order follow caller order. Score-time grading
    # uses this with the agent's observed args; the stored (canonical)
    # truth keeps the default.
    if preserve_order:
        abbr_a, abbr_b = abbr_a.upper(), abbr_b.upper()
    else:
        abbr_a, abbr_b = sorted([abbr_a.upper(), abbr_b.upper()])
    teams = _pred_team_table()
    ta, tb = teams.get(abbr_a), teams.get(abbr_b)
    if ta is None or tb is None:
        raise SkipTask("team abbr not in static table")
    ida, idb = int(ta["id"]), int(tb["id"])
    ra, rb = _pred_rating_row(ida), _pred_rating_row(idb)
    if ra is None or rb is None:
        raise SkipTask("ratings missing for prediction pair")
    lg_off, lg_def = _pred_league_means()
    home_id, away_id, resolved = _pred_meeting(ida, idb)
    neutral = home_id is None
    h_id, aw_id = (home_id or ida), (away_id or idb)
    ha = next((t for t in teams.values() if int(t["id"]) == h_id), None)
    wa = next((t for t in teams.values() if int(t["id"]) == aw_id), None)
    if ha is None or wa is None:
        raise SkipTask("home/away abbr lookup failed")
    home_abbr, away_abbr = (str(ha["abbreviation"]).upper(),
                            str(wa["abbreviation"]).upper())
    hp = _pred_injury_penalty(str(ha.get("full_name", "")))
    ap = _pred_injury_penalty(str(wa.get("full_name", "")))
    hr = _pred_rating_row(h_id)
    ar = _pred_rating_row(aw_id)
    if hr is None or ar is None:
        raise SkipTask("ratings missing for home/away team")
    pace = (hr["pace"] + ar["pace"]) / 2
    home_per100 = lg_off + (hr["off"] - lg_off) + (ar["def"] - lg_def)
    away_per100 = lg_off + (ar["off"] - lg_off) + (hr["def"] - lg_def)
    home_ppg = home_per100 * pace / 100
    away_ppg = away_per100 * pace / 100
    hca = 0.0 if neutral else _PRED_HOME_COURT_PTS
    home_ppg = home_ppg + hca / 2 - hp / 2 + ap / 2
    away_ppg = away_ppg - hca / 2 + hp / 2 - ap / 2
    import numpy as _np
    rng = _np.random.default_rng(_PRED_SEED)
    home = rng.normal(home_ppg, _PRED_SCORING_SD, _PRED_N_SIMS)
    away = (rng.normal(away_ppg, _PRED_SCORING_SD, _PRED_N_SIMS)
            + rng.normal(0, 0.5, _PRED_N_SIMS))
    p_home = float(_np.mean(home > away))
    return {
        "home_abbr": home_abbr, "away_abbr": away_abbr,
        "neutral": neutral, "home_court_pts": hca,
        f"win_prob_{home_abbr}": round(p_home, 3),
        f"win_prob_{away_abbr}": round(1 - p_home, 3),
        "proj_score_home": round(float(_np.mean(home)), 1),
        "proj_score_away": round(float(_np.mean(away)), 1),
        "projected_total": round(float(_np.mean(home + away)), 1),
    }


def pred_truth_facts(facts: dict) -> dict:
    # Maps the replica's estimate dict to the graded facts shape (shared
    # by gen_prediction's canonical truth and the score-time rescore path).
    return {
        "names": {"home": facts["home_abbr"],
                  "away": facts["away_abbr"]},
        f"win_prob_{facts['home_abbr']}":
            facts[f"win_prob_{facts['home_abbr']}"],
        f"win_prob_{facts['away_abbr']}":
            facts[f"win_prob_{facts['away_abbr']}"],
        "proj_score_home": facts["proj_score_home"],
        "proj_score_away": facts["proj_score_away"],
        "projected_total": facts["projected_total"],
    }


def gen_prediction(rng, ctx) -> tuple[Task, GroundTruth]:
    teams = _pred_team_table()
    rated = {r[0] for r in _q(
        "SELECT TEAM_ID FROM silver_team_ratings WHERE _season = ?",
        [SEASON])}
    cands = [a for a, t in teams.items() if int(t["id"]) in rated]
    if len(cands) < 2:
        raise SkipTask("too few rated teams for prediction")
    for _ in range(30):
        # Canonical order (matches _pred_facts' internal canonicalization)
        # so the question's team order, the replica's role assignment, and
        # the agent's most likely call order all agree.
        a, b = sorted(rng.sample(cands, 2))
        try:
            facts = _pred_facts(a, b)
        except SkipTask:
            continue
        ta = next(t for t in teams.values()
                  if str(t["abbreviation"]).upper() == a)
        tb = next(t for t in teams.values()
                  if str(t["abbreviation"]).upper() == b)
        tid = ctx["task_id"]
        task = Task(
            task_id=tid, family="prediction",
            question=(f"Give me the pre-game Monte Carlo estimate for the "
                      f"{ta['full_name']} vs the {tb['full_name']} "
                      f"({SEASON} season): who is favored, each team's win "
                      f"probability, and the projected score and total. "
                      f"Use default simulation settings."),
            entities=[ta["full_name"], tb["full_name"]],
            gold_tool_families=["prediction"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid,
            facts=pred_truth_facts(facts),
            computed_at=_now(),
            source="warehouse via silver_team_ratings plus silver_injuries "
                   "(same Monte Carlo pipeline as get_game_prediction)",
        )
        return task, truth
    raise SkipTask("no usable prediction pair found")


# ---------------------------------------------------------------------------
# freshness family: mirrors get_warehouse_freshness exactly (per-table row
# count plus MAX(_fetched_at), expected cadence and stale flag from the
# FRESHNESS_RULES table, daily-in-season downgraded to weekly off-season).
# Ground truth is the panel meta plus row counts for two sampled tables;
# stale flags move with the clock, but the benchmark generates tasks at
# run time and the agent calls minutes later, so the window is tiny.
# ---------------------------------------------------------------------------

_FRESH_DAY = 24 * 3600
_FRESH_IN_SEASON = frozenset({10, 11, 12, 1, 2, 3, 4, 5, 6})
# Mirrors FRESHNESS_RULES in app/tools/league.py.
_FRESH_RULES: dict[str, tuple[str, float | None]] = {
    "silver_scoreboard": ("daily in season", 36 * 3600),
    "silver_standings": ("daily in season", 36 * 3600),
    "silver_injuries": ("daily in season", 36 * 3600),
    "silver_leaders_pts": ("daily in season", 36 * 3600),
    "silver_leaders_ast": ("daily in season", 36 * 3600),
    "silver_leaders_reb": ("daily in season", 36 * 3600),
    "silver_leaders_stl": ("daily in season", 36 * 3600),
    "silver_leaders_blk": ("daily in season", 36 * 3600),
    "silver_player_gamelogs": ("daily in season", 36 * 3600),
    "silver_team_games": ("daily in season", 36 * 3600),
    "silver_boxscores": ("daily in season", 36 * 3600),
    "silver_hustle_player": ("daily in season", 36 * 3600),
    "silver_advanced": ("daily in season", 36 * 3600),
    "silver_four_factors": ("daily in season", 36 * 3600),
    "silver_clutch": ("daily in season", 36 * 3600),
    "silver_team_ratings": ("daily in season", 36 * 3600),
    "silver_on_off": ("daily in season", 36 * 3600),
    "silver_lineups": ("daily in season", 36 * 3600),
    "silver_rosters": ("daily in season", 36 * 3600),
    "silver_salaries": ("weekly", 7 * _FRESH_DAY),
    "silver_cap_players": ("weekly", 7 * _FRESH_DAY),
    "silver_combine": ("weekly", 7 * _FRESH_DAY),
    "silver_playoffs": ("seasonal", 400 * _FRESH_DAY),
    "silver_playoff_gamelogs": ("seasonal", 400 * _FRESH_DAY),
    "silver_hist_gamelogs": ("static", None),
    "silver_hist_hustle": ("static", None),
    "silver_hist_lineups": ("static", None),
    "silver_hist_possessions": ("static", None),
    "silver_hist_shots": ("static", None),
    "silver_hist_standings": ("static", None),
    "silver_raptor_player": ("static", None),
    "silver_raptor_team": ("static", None),
}


def _fresh_parse_ts(raw):
    from datetime import datetime as _dt
    try:
        ts = _dt.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _fresh_panel() -> tuple[list[dict], dict]:
    now = datetime.now(timezone.utc)
    tables = sorted(r[0] for r in _q("SHOW TABLES")
                    if r[0].startswith("silver_"))
    rows_out = []
    for t in tables:
        has_ts = any(r[1] == "_fetched_at"
                     for r in _q(f"PRAGMA table_info({t})"))
        mx = "MAX(_fetched_at)" if has_ts else "CAST(NULL AS VARCHAR)"
        n, last = _q(f"SELECT COUNT(*), {mx} FROM {t}")[0]
        label, max_age = _FRESH_RULES.get(t, ("unknown", None))
        expected, threshold = label, max_age
        if label == "daily in season" and now.month not in _FRESH_IN_SEASON:
            expected, threshold = "weekly (offseason)", 7 * _FRESH_DAY
        ts = _fresh_parse_ts(last) if last else None
        age_hours = (round((now - ts).total_seconds() / 3600, 1)
                     if ts is not None else None)
        stale = (threshold is not None and age_hours * 3600 > threshold
                 if (ts is not None and t in _FRESH_RULES) else None)
        rows_out.append({"table": t, "rows": n, "stale": stale,
                         "expected": expected})
    meta = {"tables": len(rows_out),
            "stale": sum(1 for r in rows_out if r["stale"]),
            "unknown": sum(1 for r in rows_out if r["stale"] is None),
            "in_season": now.month in _FRESH_IN_SEASON}
    return rows_out, meta


def gen_freshness(rng, ctx) -> tuple[Task, GroundTruth]:
    rows_out, meta = _fresh_panel()
    if not rows_out:
        raise SkipTask("no silver tables in warehouse")
    by_table = {r["table"]: r["rows"] for r in rows_out}
    for pick in ("silver_team_ratings", "silver_leaders_pts"):
        if pick not in by_table:
            raise SkipTask(f"{pick} missing from warehouse")
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="freshness",
        question=("Give me the warehouse freshness panel: how many silver "
                  "tables are tracked, how many are stale, how many have "
                  "unknown freshness, and the row counts for "
                  "silver_team_ratings and silver_leaders_pts."),
        entities=["silver_team_ratings", "silver_leaders_pts"],
        gold_tool_families=["freshness"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"table_count": meta["tables"], "stale_count": meta["stale"],
               "unknown_count": meta["unknown"],
               "rows_team_ratings": by_table["silver_team_ratings"],
               "rows_leaders_pts": by_table["silver_leaders_pts"]},
        computed_at=_now(),
        source="warehouse silver_* tables "
               "(same freshness rules as get_warehouse_freshness)",
    )
    return task, truth


# ---------------------------------------------------------------------------
# headtohead family: mirrors get_head_to_head's domain model exactly
# (summarize: per-game means plus W/L over a game-log set; deltas: the
# vs-opponent line minus the season baseline). Only pairs with 5+ games
# are sampled so the small-sample flag stays off and the averages are
# gradeable.
# ---------------------------------------------------------------------------

_H2H_COLS = ("GAME_DATE", "Game_ID", "MATCHUP", "WL", "MIN", "FGM", "FGA",
             "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "STL", "BLK",
             "TOV", "PTS", "PLUS_MINUS")


def _h2h_games(pid: int) -> list[dict]:
    rows = _q("SELECT " + ", ".join(_H2H_COLS) + " FROM "
              "silver_player_gamelogs WHERE Player_ID = ? AND _season = ?",
              [pid, SEASON])
    out = [dict(zip(_H2H_COLS, r)) for r in rows]
    out.sort(key=lambda r: _parse_gamedate(r.get("GAME_DATE"))[1]
             if _parse_gamedate(r.get("GAME_DATE"))[0] == 0
             else datetime.min, reverse=True)
    return out


def _h2h_summarize(rows: list[dict]) -> dict:
    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0
    gp = len(rows)
    if gp == 0:
        return {"gp": 0, "ppg": 0.0, "rpg": 0.0, "apg": 0.0,
                "fg_pct": 0.0, "ts_pct": 0.0, "w": 0, "l": 0}
    fgm = sum(_f(r.get("FGM")) for r in rows)
    fga = sum(_f(r.get("FGA")) for r in rows)
    pts = sum(_f(r.get("PTS")) for r in rows)
    fta = sum(_f(r.get("FTA")) for r in rows)
    ts_den = 2 * (fga + 0.44 * fta)
    return {
        "gp": gp,
        "ppg": round(pts / gp, 1),
        "rpg": round(sum(_f(r.get("REB")) for r in rows) / gp, 1),
        "apg": round(sum(_f(r.get("AST")) for r in rows) / gp, 1),
        "fg_pct": round(fgm / fga, 3) if fga else 0.0,
        "ts_pct": round(pts / ts_den, 3) if ts_den > 0 else 0.0,
        "w": sum(1 for r in rows if str(r.get("WL") or "").upper() == "W"),
        "l": sum(1 for r in rows if str(r.get("WL") or "").upper() == "L"),
    }


def _h2h_facts(pid: int, abbr: str) -> dict:
    games = _h2h_games(pid)
    if not games:
        raise SkipTask("no gamelogs for head-to-head player")
    opp_games = [g for g in games if _opp_abbrev(g.get("MATCHUP")) == abbr]
    base = _h2h_summarize(games)
    opp = _h2h_summarize(opp_games)
    return {
        "vs_gp": opp["gp"], "vs_ppg": opp["ppg"],
        "base_ppg": base["ppg"],
        "delta_ppg": round(opp["ppg"] - base["ppg"], 1),
        "w": opp["w"], "l": opp["l"],
        "small_sample": opp["gp"] < 5,
    }


def gen_headtohead(rng, ctx) -> tuple[Task, GroundTruth]:
    teams = _pred_team_table()
    ents = _q("SELECT _entity FROM silver_player_gamelogs WHERE _season = ? "
              "GROUP BY _entity HAVING COUNT(*) >= 15", [SEASON])
    if not ents:
        raise SkipTask("no player gamelogs in warehouse")
    for _ in range(30):
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
        name = name_rows[0][0]
        games = _h2h_games(pid)
        counts: dict = {}
        for g in games:
            abbr = _opp_abbrev(g.get("MATCHUP"))
            if abbr:
                counts[abbr] = counts.get(abbr, 0) + 1
        opps = [a for a, c in counts.items()
                if c >= 5 and a in teams]
        if not opps:
            continue
        abbr = rng.choice(opps)
        facts = _h2h_facts(pid, abbr)
        opp_full = teams[abbr]["full_name"]
        tid = ctx["task_id"]
        task = Task(
            task_id=tid, family="headtohead",
            question=(f"How has {name} performed against the {opp_full} "
                      f"this season? Give his vs-opponent PPG, his season "
                      f"baseline PPG, the delta, the number of games in the "
                      f"sample, and his team's W-L record in those games."),
            entities=[name, opp_full], gold_tool_families=["headtohead"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid,
            facts={"names": {"player": name},
                   "vs_ppg": facts["vs_ppg"], "base_ppg": facts["base_ppg"],
                   "delta_ppg": facts["delta_ppg"],
                   "vs_gp": facts["vs_gp"], "team_w": facts["w"],
                   "team_l": facts["l"]},
            computed_at=_now(),
            source="nba_api via silver_player_gamelogs "
                   "(same summarize/deltas model as get_head_to_head)",
        )
        return task, truth
    raise SkipTask("no head-to-head pair with 5+ games found")


# ---------------------------------------------------------------------------
# zones family: mirrors get_team_shot_zones exactly. The five-zone
# taxonomy (rim / short_mid / long_mid / corner_3 / atb_3) is classified
# from x_legacy/y_legacy in tenths of a foot, same rule order as the
# tool; baselines are pooled across all teams for the season; deltas are
# in percentage points. Aggregation runs in SQL; shares round to 4dp and
# pp deltas to 2dp exactly like the tool. Raw shares are fractions, so
# the question grades the pp delta (agents quote it verbatim) plus the
# total shots, not the 0.xxxx fraction.
# ---------------------------------------------------------------------------

_ZONE_YEAR = int(SEASON[:4]) + 1


def _zone_rows() -> list[dict]:
    sql = """
    WITH z AS (
        SELECT team_id, team_tricode,
               CASE
                 WHEN COALESCE(x_legacy * x_legacy + y_legacy * y_legacy,
                              99999999) < 6400 THEN 'rim'
                 WHEN shot_value = 3 AND ABS(x_legacy) >= 220 THEN 'corner_3'
                 WHEN shot_value = 3 THEN 'atb_3'
                 WHEN COALESCE(x_legacy * x_legacy + y_legacy * y_legacy,
                              99999999) < 19600 THEN 'short_mid'
                 ELSE 'long_mid'
               END AS zone,
               CASE WHEN LOWER(shot_result) = 'made' THEN 1 ELSE 0 END AS made,
               CASE WHEN LOWER(shot_result) = 'made' AND shot_value = 3
                    THEN 1 ELSE 0 END AS three_made
        FROM silver_hist_shots WHERE season = ?
    )
    SELECT team_id, team_tricode, zone,
           COUNT(*) AS fga, SUM(made) AS fgm, SUM(three_made) AS three_made
    FROM z GROUP BY team_id, team_tricode, zone
    """
    return _qd(sql, [_ZONE_YEAR])


def _zone_leader_rows() -> list[dict]:
    agg: dict = {}
    for r in _zone_rows():
        tid = int(r["team_id"])
        entry = agg.setdefault(tid, {"abbr": r["team_tricode"],
                                     "zones": {}})
        entry["zones"][r["zone"]] = {"fga": int(r["fga"]),
                                     "fgm": int(r["fgm"]),
                                     "three_made": int(r["three_made"])}
    keys = ["rim", "short_mid", "long_mid", "corner_3", "atb_3"]
    total_fga = sum(z["fga"] for t in agg.values()
                    for z in t["zones"].values())
    if not total_fga:
        raise SkipTask("no shot rows for zones season")
    base_share = {}
    for key in keys:
        fga = sum(t["zones"].get(key, {}).get("fga", 0)
                  for t in agg.values())
        base_share[key] = round(fga / total_fga, 4)
    rows = []
    for tid, t in agg.items():
        team_fga = sum(z["fga"] for z in t["zones"].values())
        row = {"abbr": t["abbr"], "shots": team_fga}
        for key in keys:
            z = t["zones"].get(key, {"fga": 0, "fgm": 0, "three_made": 0})
            share = z["fga"] / team_fga if team_fga else 0.0
            row[f"{key}_share_delta_pp"] = round(
                (share - base_share[key]) * 100, 2)
        rows.append(row)
    return rows


def gen_zones(rng, ctx) -> tuple[Task, GroundTruth]:
    rows = _zone_leader_rows()
    if not rows:
        raise SkipTask("no zone rows for season")
    top = max(rows, key=lambda r: r["rim_share_delta_pp"])
    if sum(1 for r in rows
           if r["rim_share_delta_pp"] == top["rim_share_delta_pp"]) > 1:
        raise SkipTask("tied best rim-share delta is ungradeable")
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="zones",
        question=(f"Across the {SEASON} season, which team takes the "
                  f"largest share of its shot attempts at the rim? Name "
                  f"the team, its rim share delta vs the league baseline "
                  f"in percentage points, and its total shots."),
        entities=[top["abbr"]], gold_tool_families=["zones"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"names": {"zone_leader": top["abbr"]},
               "rim_share_delta_pp": top["rim_share_delta_pp"],
               "shots": top["shots"]},
        computed_at=_now(),
        source="sportsdataverse via silver_hist_shots "
               "(same zone taxonomy plus pp deltas as get_team_shot_zones)",
    )
    return task, truth


# ---------------------------------------------------------------------------
# impact family: mirrors get_impact_estimate's box_prior_shrinkage pipeline
# exactly. 2025-26 has zero RAPTOR rows in the warehouse, so every sampled
# player takes the shrinkage path: marginal on-court lift (player on-court
# NET_RATING minus team NET_RATING) shrunk toward an OLS box-score prior
# (lift ~ USG_PCT + TS_PCT + AST_PCT + REB_PCT + TM_TOV_PCT, fitted on
# 3000+ possession trainers) with shrinkage K=1500 possessions, rounded to
# 2dp. The linear solver is a verbatim copy of the tool's own Gaussian
# elimination; all data comes from warehouse reads, so anti-circularity
# holds. Facts grade the 2dp estimate (numeric_acc already tolerates
# agent-side rounding: fact 2.47 matches a quoted "2.5" or "2") and the
# estimate disclosure through the names mechanism ("estimate" must appear
# in the answer; the tool always labels its output an estimate).
# ---------------------------------------------------------------------------

_IMPACT_FEATURES = ("USG_PCT", "TS_PCT", "AST_PCT", "REB_PCT", "TM_TOV_PCT")
_IMPACT_PRIOR_MIN_POSS = 3000
_IMPACT_SHRINK_K = 1500
_IMPACT_NAME_SUFFIXES = ("Jr", "II", "III", "IV", "V")


def _impact_solve(a: list[list[float]],
                  b: list[float]) -> list[float] | None:
    # Verbatim mirror of the tool's Gaussian elimination solver (pure
    # math; the warehouse data it runs on comes from ground truth reads).
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) \
            / m[i][i]
        if abs(m[i][i]) < 1e-12:
            return None
    return x


def _impact_box_prior() -> tuple[float, dict[str, float]] | None:
    # Mirror of the tool's _fit_box_prior: OLS of lift on the five box
    # features over 3000+ possession trainers. Returns
    # (intercept, {feature: coef}).
    rows = _qd("SELECT TEAM_ID, POSS, NET_RATING, " +
               ", ".join(_IMPACT_FEATURES) +
               " FROM silver_advanced WHERE _season = ?", [SEASON])
    team_net: dict = {}
    for tid, net in _q("SELECT TEAM_ID, NET_RATING FROM silver_team_ratings"
                       " WHERE _season = ?", [SEASON]):
        if net is not None:
            team_net[tid] = net
    trainers = [
        r for r in rows
        if (r.get("POSS") or 0) >= _IMPACT_PRIOR_MIN_POSS
        and r.get("NET_RATING") is not None
        and r.get("TEAM_ID") in team_net
        and all(r.get(f) is not None for f in _IMPACT_FEATURES)
    ]
    if len(trainers) < 30:
        return None
    xs = [[1.0] + [float(r[f]) for f in _IMPACT_FEATURES]
          for r in trainers]
    ys = [float(r["NET_RATING"]) - float(team_net[r["TEAM_ID"]])
          for r in trainers]
    p = 6
    ata = [[sum(x[i] * x[j] for x in xs) for j in range(p)]
           for i in range(p)]
    aty = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(p)]
    beta = _impact_solve(ata, aty)
    if beta is None:
        return None
    return beta[0], dict(zip(_IMPACT_FEATURES, beta[1:]))


def _impact_estimate(pid: int) -> tuple[str, str, float, float, float]:
    # Mirror of the box_prior_shrinkage path. Returns (player_name,
    # team_abbr, estimate_per_100, lift_per_100, prior_per_100).
    rows = _qd("SELECT PLAYER_NAME, TEAM_ABBREVIATION, TEAM_ID, POSS, "
               "NET_RATING, " + ", ".join(_IMPACT_FEATURES) +
               " FROM silver_advanced WHERE _season = ?"
               " AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)"
               " LIMIT 1", [SEASON, str(pid)])
    if not rows:
        raise SkipTask("player has no advanced row for season")
    row = rows[0]
    team_net: dict = {}
    for tid, net in _q("SELECT TEAM_ID, NET_RATING FROM silver_team_ratings"
                       " WHERE _season = ?", [SEASON]):
        if net is not None:
            team_net[tid] = net
    lift = (float(row["NET_RATING"])
            - float(team_net.get(row["TEAM_ID"], 0.0)))
    prior = _impact_box_prior()
    if prior is None:
        raise SkipTask("box prior could not be fitted")
    if any(row.get(f) is None for f in _IMPACT_FEATURES):
        # The tool falls back to the intercept here; the warehouse has no
        # NULL features for 2025-26, so this is unreachable in practice.
        raise SkipTask("player box features incomplete")
    intercept, coefs = prior
    prior_value = float(intercept) + sum(
        float(coefs[f]) * float(row[f]) for f in _IMPACT_FEATURES)
    poss = float(row.get("POSS") or 0)
    k = _IMPACT_SHRINK_K
    w_meas = poss / (poss + k) if poss > 0 else 0.0
    estimate = w_meas * lift + (1 - w_meas) * prior_value
    return (row["PLAYER_NAME"], row["TEAM_ABBREVIATION"],
            round(estimate, 2), round(lift, 2), round(prior_value, 2))


def gen_impact(rng, ctx) -> tuple[Task, GroundTruth]:
    rows = _q("SELECT PLAYER_ID, PLAYER_NAME, TEAM_ABBREVIATION FROM "
              "silver_advanced WHERE _season = ? AND GP >= 5", [SEASON])
    rows = [r for r in rows
            if str(r[1]).split()[-1].rstrip(".") not in
            _IMPACT_NAME_SUFFIXES]
    if not rows:
        raise SkipTask("no advanced rows for impact season")
    picked = None
    for _ in range(30):
        pid = rng.choice(rows)[0]
        try:
            picked = _impact_estimate(int(pid))
            break
        except (SkipTask, TypeError, ValueError):
            continue
    if picked is None:
        raise SkipTask("no gradeable impact estimate found")
    name, team, est, _lift, _prior = picked
    templates = [
        f"How good has {name} been this season? Give me his estimated "
        f"per-100 impact.",
        f"Estimate {name}'s impact per 100 possessions for the {SEASON} "
        f"season. What's the number?",
        f"What is {name}'s ({team}) estimated on-court impact this season, "
        f"per 100 possessions?",
    ]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="impact", question=rng.choice(templates),
        entities=[name], gold_tool_families=["impact"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"names": {"player": name, "disclosure": "estimate"},
               "estimate_per_100": est},
        computed_at=_now(),
        source="nba_api via silver_advanced plus silver_team_ratings "
               "(same box-prior shrinkage pipeline as get_impact_estimate)",
    )
    return task, truth


# ---------------------------------------------------------------------------
# gamelog family: mirrors search_game_logs' filter pipeline exactly
# (per-player gamelog rows from silver_player_gamelogs, Stathead 10+
# counting over PTS/REB/AST/STL/BLK for double/triple-doubles, opponent
# from the last MATCHUP token, home = "vs." in MATCHUP, month and
# date-range filters on strptime-parsed game dates, most-recent-first
# ordering). Ground truth is the matching game set: each game's date
# (YYYY-MM-DD) is graded through the names mechanism, so the exact SET
# of dates must appear in the answer; the total match count and each
# game's points/rebounds/assists are numeric facts (the scorer's
# tolerance covers agent-side rounding). Only 1..8-match filter combos
# are sampled so the agent can plausibly list every game.
# ---------------------------------------------------------------------------

_GLOG_MAX_MATCHES = 8
_GLOG_TAIL = (" Give each game's date (YYYY-MM-DD), points, rebounds and "
              "assists, plus the total count.")


def _glog_team_of(matchup) -> str:
    # Verbatim mirror of the tool's team_wide grouping: first token of
    # MATCHUP, uppercased, with UNK fallback.
    return str(matchup or "").split(" ")[0].upper() or "UNK"


def _glog_games(pid: int | None = None) -> list[dict]:
    # Verbatim mirror of the tool's _load_player_games: normalized rows,
    # most recent first. ISO date strings sort lexicographically, same
    # as the tool's date-desc ordering. pid None loads every player in
    # a single query; each row carries player_id and team so the
    # warehouse-wide mirrors can group exactly like the tool.
    games = []
    if pid is None:
        rows = _q(
            "SELECT Player_ID, GAME_DATE, MATCHUP, PTS, REB, AST, STL, BLK "
            "FROM silver_player_gamelogs WHERE _season = ?",
            [SEASON])
        normed = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7])
                  for r in rows]
    else:
        rows = _q(
            "SELECT GAME_DATE, MATCHUP, PTS, REB, AST, STL, BLK FROM "
            "silver_player_gamelogs WHERE Player_ID = ? AND _season = ?",
            [pid, SEASON])
        normed = [(pid, r[0], r[1], r[2], r[3], r[4], r[5], r[6])
                  for r in rows]
    for prow, gdate, matchup, pts, reb, ast, stl, blk in normed:
        try:
            d = datetime.strptime(str(gdate or "").strip(),
                                  "%b %d, %Y").date()
        except (TypeError, ValueError):
            continue
        mu = str(matchup or "")
        toks = mu.split()
        try:
            prow_id = int(prow) if prow is not None else 0
        except (TypeError, ValueError):
            continue
        games.append({
            "date": d.isoformat(),
            "opponent": toks[-1].upper() if toks else "",
            "home": "vs." in mu,
            "pts": _fnum(pts), "reb": _fnum(reb), "ast": _fnum(ast),
            "dd": sum(1 for v in (pts, reb, ast, stl, blk)
                      if _fnum(v) >= 10),
            "player_id": prow_id,
            "team": _glog_team_of(matchup),
        })
    games.sort(key=lambda g: g["date"], reverse=True)
    return games


def _glog_matches(g: dict, f: dict) -> bool:
    # Verbatim mirror of the tool's _matches: every filter ANDs.
    if f.get("min_points") is not None and g["pts"] < f["min_points"]:
        return False
    if f.get("min_rebounds") is not None and g["reb"] < f["min_rebounds"]:
        return False
    if f.get("min_assists") is not None and g["ast"] < f["min_assists"]:
        return False
    if f.get("min_pra") is not None and \
            g["pts"] + g["reb"] + g["ast"] < f["min_pra"]:
        return False
    if f.get("double_double") and g["dd"] < 2:
        return False
    if f.get("triple_double") and g["dd"] < 3:
        return False
    if f.get("opponent") is not None and g["opponent"] != f["opponent"]:
        return False
    if f.get("month") is not None and int(g["date"][5:7]) != f["month"]:
        return False
    if f.get("start_date") is not None and g["date"] < f["start_date"]:
        return False
    if f.get("end_date") is not None and g["date"] > f["end_date"]:
        return False
    if f.get("home_away") is not None and \
            g["home"] != (f["home_away"] == "home"):
        return False
    return True


def _glog_league_leaders(games: list[dict], filters: dict,
                         names: dict) -> list[dict]:
    # Verbatim mirror of the tool's league_wide branch: per-player match
    # counts sorted by (-count, resolved name).
    counts: dict = {}
    for g in games:
        if _glog_matches(g, filters):
            pid = g["player_id"]
            counts[pid] = counts.get(pid, 0) + 1
    return [
        {"player_id": pid, "name": names.get(pid, str(pid)), "count": c}
        for pid, c in sorted(
            counts.items(),
            key=lambda kv: (-kv[1], names.get(kv[0], str(kv[0]))))
    ]


def _glog_team_leaders(games: list[dict], filters: dict,
                       fulls: dict) -> list[dict]:
    # Verbatim mirror of the tool's team_wide branch: per-team-night
    # match counts sorted by (-count, abbr), unknown abbrs fall back
    # to the abbr itself like the tool's ValueError fallback.
    counts: dict = {}
    for g in games:
        if _glog_matches(g, filters):
            abbr = g["team"]
            counts[abbr] = counts.get(abbr, 0) + 1
    return [
        {"abbr": abbr, "team": fulls.get(abbr, abbr), "count": c}
        for abbr, c in sorted(counts.items(),
                              key=lambda kv: (-kv[1], kv[0]))
    ]


def _glog_templates() -> list:
    # Each template returns (question, ground-truth filters, tool kwargs,
    # tail, detail) or None when it cannot be phrased for this player's
    # games. detail True = list-style grading (1..8 matches); False =
    # count-only grading (total only, 0 allowed).
    def _t_points(rng, games, name, full_of):
        thr = rng.choice([30, 40])
        return (f"List all of {name}'s {thr}-point games this season "
                f"({SEASON}).",
                {"min_points": thr}, {"min_points": thr}, _GLOG_TAIL, True)

    def _t_triple(rng, games, name, full_of):
        return (f"List all of {name}'s triple-doubles this season "
                f"({SEASON}).",
                {"triple_double": True}, {"triple_double": True},
                _GLOG_TAIL, True)

    def _t_dd_vs(rng, games, name, full_of):
        opp = rng.choice(sorted({g["opponent"] for g in games
                                 if g["opponent"]}))
        full = full_of(opp)
        if not full:
            return None
        return (f"List all of {name}'s double-doubles against the {full} "
                f"this season ({SEASON}).",
                {"double_double": True, "opponent": opp},
                {"double_double": True, "opponent": opp}, _GLOG_TAIL, True)

    def _t_vs(rng, games, name, full_of):
        opp = rng.choice(sorted({g["opponent"] for g in games
                                 if g["opponent"]}))
        full = full_of(opp)
        if not full:
            return None
        return (f"How did {name} do against the {full} this season "
                f"({SEASON})? List every game.",
                {"opponent": opp}, {"opponent": opp}, _GLOG_TAIL, True)

    def _t_month(rng, games, name, full_of):
        m = rng.choice(sorted({int(g["date"][5:7]) for g in games}))
        thr = rng.choice([20, 25])
        mname = datetime(2000, m, 1).strftime("%B")
        return (f"List all of {name}'s {thr}-point games in {mname} this "
                f"season ({SEASON}).",
                {"month": m, "min_points": thr},
                {"month": m, "min_points": thr}, _GLOG_TAIL, True)

    def _t_home(rng, games, name, full_of):
        ha = rng.choice(["home", "away"])
        thr = rng.choice([25, 30])
        return (f"List all of {name}'s {thr}-point {ha} games this season "
                f"({SEASON}).",
                {"home_away": ha, "min_points": thr},
                {"home_away": ha, "min_points": thr}, _GLOG_TAIL, True)

    def _t_pra(rng, games, name, full_of):
        thr = rng.choice([40, 45, 50])
        return (f"List all of {name}'s games with {thr}+ "
                f"points+rebounds+assists (PRA) this season ({SEASON}).",
                {"min_pra": thr}, {"min_pra": thr}, _GLOG_TAIL, True)

    def _t_count(rng, games, name, full_of):
        thr = rng.choice([30, 40, 50])
        return (f"How many {thr}-point games did {name} have this season "
                f"({SEASON})?",
                {"min_points": thr}, {"min_points": thr},
                " Give the count.", False)

    return [_t_points, _t_triple, _t_dd_vs, _t_vs, _t_month, _t_home,
            _t_pra, _t_count]


def _glog_static() -> tuple[dict, dict]:
    names: dict = {}
    fulls: dict = {}
    try:
        from nba_api.stats.static import players as _players, \
            teams as _teams
        for p in _players.get_players():
            names[p.get("id")] = p.get("full_name")
        for t in _teams.get_teams():
            fulls[str(t.get("abbreviation", "")).upper()] = \
                t.get("full_name")
    except Exception:
        pass
    return names, fulls


def _gen_gamelog_existence(rng, ctx, names: dict) -> tuple[Task, GroundTruth]:
    games = _glog_games(None)
    kind = rng.choice(["points", "triple"])
    tid = ctx["task_id"]
    if kind == "points":
        thr = rng.choice([60, 70, 85])
        leaders = _glog_league_leaders(games, {"min_points": thr}, names)
        if len(leaders) > 6:
            raise SkipTask("too many 60+ game holders to grade")
        question = rng.choice([
            f"Did anyone score {thr} points in a game this season "
            f"({SEASON})?",
            f"Was there a {thr}-point game this season ({SEASON})?",
            f"Has anyone dropped {thr} in a game this season ({SEASON})?",
        ])
        tail = (" Give the total count of such games and every player "
                "who did it, with each player's count.")
        graded = leaders
    else:
        leaders = _glog_league_leaders(games, {"triple_double": True},
                                       names)
        if len(leaders) < 5:
            raise SkipTask("too few triple-double holders to grade")
        graded = leaders[:5]
        question = (f"Did anyone record a triple-double this season "
                    f"({SEASON})?")
        tail = (" Give the total count of such games and the five "
                "players with the most triple-doubles, with each "
                "player's count.")
    facts: dict = {
        "total": sum(l["count"] for l in leaders),
        "names": {f"player_{i}": l["name"]
                  for i, l in enumerate(graded, 1)},
    }
    for i, l in enumerate(graded, 1):
        facts[f"player_{i}_count"] = l["count"]
    task = Task(
        task_id=tid, family="gamelog", question=question + tail,
        entities=[], gold_tool_families=["gamelog"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid, facts=facts, computed_at=_now(),
        source="nba_api via silver_player_gamelogs (same league-wide "
               "grouping as search_game_logs)",
    )
    return task, truth


def _gen_gamelog_team(rng, ctx, fulls: dict) -> tuple[Task, GroundTruth]:
    games = _glog_games(None)
    kind = rng.choice(["p40", "p50", "td"])
    if kind == "p40":
        filters, desc = {"min_points": 40}, "40-point games"
    elif kind == "p50":
        filters, desc = {"min_points": 50}, "50-point games"
    else:
        filters, desc = {"triple_double": True}, "triple-doubles"
    leaders = _glog_team_leaders(games, filters, fulls)
    if len(leaders) < 3:
        raise SkipTask("too few teams to grade")
    top3 = leaders[:3]
    facts: dict = {
        "names": {f"team_{i}": l["team"]
                  for i, l in enumerate(top3, 1)},
    }
    for i, l in enumerate(top3, 1):
        facts[f"team_{i}_count"] = l["count"]
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="gamelog",
        question=(f"Which team had the most {desc} this season "
                  f"({SEASON})? Give the top 3 teams and each team's "
                  f"count."),
        entities=[], gold_tool_families=["gamelog"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid, facts=facts, computed_at=_now(),
        source="nba_api via silver_player_gamelogs (same team-night "
               "grouping as search_game_logs team_wide)",
    )
    return task, truth


def gen_gamelog(rng, ctx) -> tuple[Task, GroundTruth]:
    names, fulls = _glog_static()
    variant = rng.choice(["player", "player", "existence", "team_wide"])
    if variant == "existence":
        return _gen_gamelog_existence(rng, ctx, names)
    if variant == "team_wide":
        return _gen_gamelog_team(rng, ctx, fulls)
    ents = _q("SELECT DISTINCT Player_ID FROM silver_player_gamelogs "
              "WHERE _season = ?", [SEASON])
    if not ents:
        raise SkipTask("no player gamelogs in warehouse")
    templates = _glog_templates()
    for _ in range(40):
        pid = int(rng.choice(ents)[0])
        name = names.get(pid)
        if not name or str(name).split()[-1].rstrip(".") in \
                _IMPACT_NAME_SUFFIXES:
            # Suffix names (Jr/II/III) break name_recall's last-token
            # match; the impact family skips them for the same reason.
            continue
        games = _glog_games(pid)
        if len(games) < 10:
            continue
        built = rng.choice(templates)(rng, games, name, fulls.get)
        if built is None:
            continue
        question, filters, _kwargs, tail, detail = built
        matches = [g for g in games if _glog_matches(g, filters)]
        if detail:
            if not 1 <= len(matches) <= _GLOG_MAX_MATCHES:
                continue
            gnames = {"player": name}
            facts = {}
            for i, g in enumerate(matches, 1):
                gnames[f"game_{i}"] = g["date"]
                facts[f"game_{i}_pts"] = round(g["pts"], 1)
                facts[f"game_{i}_reb"] = round(g["reb"], 1)
                facts[f"game_{i}_ast"] = round(g["ast"], 1)
            facts["names"] = gnames
            facts["total"] = len(matches)
        else:
            facts = {"total": len(matches)}
        tid = ctx["task_id"]
        task = Task(
            task_id=tid, family="gamelog",
            question=question + tail,
            entities=[name], gold_tool_families=["gamelog"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid, facts=facts, computed_at=_now(),
            source="nba_api via silver_player_gamelogs "
                   "(same filter pipeline as search_game_logs)",
        )
        return task, truth
    raise SkipTask("no gradeable gamelog filter combo found")


# ---------------------------------------------------------------------------
# elo family: mirrors get_elo_standings exactly. The ELO math is replicated
# here as pure functions (same constants: start 1500, K=20, build HCA=100,
# MOV multiplier ((|margin|+3)^0.8)/(7.5+0.006*|diff|)), over the same
# silver_hist_gamelogs rows, ordered by game_date/game_id with games sorted
# by game_id -- but this module never imports app.tools, so the benchmark
# cannot reward the agent for agreeing with its own tool wrappers.
# Question flavors: league ELO rank, 82-game win equivalents, and the
# ELO-implied neutral-court spread between two teams.
# ---------------------------------------------------------------------------

_ELO_START = 1500.0
_ELO_K = 20.0
_ELO_HCA_BUILD = 100
_ELO_PER_POINT = 28.0


def _elo_expected(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))


def _elo_mov_mult(margin: float | None, diff: float) -> float:
    if margin is None:
        return 1.0
    return ((abs(margin) + 3) ** 0.8) / (7.5 + 0.006 * abs(diff))


def _elo_build_table(season: str) -> list[dict]:
    rows = _q(
        """SELECT team_abbreviation, game_id, game_date, matchup, wl,
        plus_minus FROM silver_hist_gamelogs
        WHERE _season = ? ORDER BY game_date, game_id""",
        [season],
    )
    if not rows:
        raise SkipTask(f"no hist gamelogs for season {season}")
    games: dict[str, list] = {}
    for r in rows:
        games.setdefault(r[1], []).append(r)
    elo: dict[str, float] = {}
    for _, pair in sorted(games.items()):
        if len(pair) != 2:
            continue
        wa, wb = pair[0][4], pair[1][4]
        if (wa == "W") == (wb == "W"):
            continue
        wrow, lrow = (pair[0], pair[1]) if wa == "W" else (pair[1], pair[0])
        margin = wrow[5]
        if margin is None:
            margin = -(lrow[5]) if lrow[5] is not None else None
        if margin is not None:
            margin = abs(margin)
        wteam, lteam = wrow[0], lrow[0]
        elo.setdefault(wteam, _ELO_START)
        elo.setdefault(lteam, _ELO_START)
        w_adj = elo[wteam] + (_ELO_HCA_BUILD if "vs." in str(wrow[3]) else 0)
        l_adj = elo[lteam] + (_ELO_HCA_BUILD if "vs." in str(lrow[3]) else 0)
        diff = w_adj - l_adj
        shift = (_ELO_K * _elo_mov_mult(margin, diff)
                 * (1 - _elo_expected(diff)))
        elo[wteam] += shift
        elo[lteam] -= shift
    table = []
    for t, v in elo.items():
        e = round(v)
        pct = round(_elo_expected(e - _ELO_START), 4)
        table.append({"abbr": t, "elo": e, "elo_win_pct": pct,
                      "win_equiv": round(pct * 82, 1)})
    table.sort(key=lambda d: d["elo"], reverse=True)
    for i, row in enumerate(table, 1):
        row["rank"] = i
        row["spread_vs_avg"] = round((row["elo"] - _ELO_START)
                                     / _ELO_PER_POINT, 1)
    return table


def _elo_implied_spread(elo_a: int, elo_b: int) -> float:
    return round((elo_a - elo_b) / _ELO_PER_POINT, 1)


def gen_elo(rng, ctx) -> tuple[Task, GroundTruth]:
    table = _elo_build_table(SEASON)
    if len(table) < 2:
        raise SkipTask("elo table has fewer than 2 teams")
    teams = _pred_team_table()
    by_abbr = {t["abbr"]: t for t in table}
    named = [t for t in table
             if teams.get(t["abbr"], {}).get("full_name")]
    if not named:
        raise SkipTask("no team names resolvable for elo table")
    variant = rng.choice(["rank", "rank", "wins", "spread"])
    tid = ctx["task_id"]
    if variant == "spread":
        for _ in range(20):
            a, b = rng.sample(named, 2)
            spread = _elo_implied_spread(a["elo"], b["elo"])
            if spread == 0:
                continue  # a pick-em is ungradeable on direction
            full_a = teams[a["abbr"]]["full_name"]
            full_b = teams[b["abbr"]]["full_name"]
            task = Task(
                task_id=tid, family="elo",
                question=(f"If the {full_a} played the {full_b} on a "
                          f"neutral court this season, what would the "
                          f"ELO-implied spread be from the {full_a} "
                          f"perspective? Give the spread (negative means "
                          f"{full_a} are underdogs) and each team's ELO "
                          f"rating."),
                entities=[a["abbr"], b["abbr"]],
                gold_tool_families=["elo"],
                timeout_s=ctx["timeout_s"], seed=ctx["seed"],
            )
            truth = GroundTruth(
                task_id=tid,
                facts={"names": {"team_a": full_a, "team_b": full_b},
                       "spread": spread,
                       "elo_a": a["elo"], "elo_b": b["elo"]},
                computed_at=_now(),
                source="silver_hist_gamelogs (same 538-style ELO math as "
                       "get_elo_standings: K=20, HCA=100, MOV-adjusted, "
                       "spread = elo_diff / 28)",
            )
            return task, truth
        raise SkipTask("no elo spread pair with a nonzero spread found")
    row = rng.choice(named)
    full = teams[row["abbr"]]["full_name"]
    if variant == "wins":
        task = Task(
            task_id=tid, family="elo",
            question=(f"How many wins is the {full} ELO rating worth over "
                      f"an 82-game season? Give the win-equivalent number "
                      f"and the team's ELO rating."),
            entities=[row["abbr"]], gold_tool_families=["elo"],
            timeout_s=ctx["timeout_s"], seed=ctx["seed"],
        )
        truth = GroundTruth(
            task_id=tid,
            facts={"names": {"team": full}, "win_equiv": row["win_equiv"],
                   "elo": row["elo"]},
            computed_at=_now(),
            source="silver_hist_gamelogs (same 538-style ELO math as "
                   "get_elo_standings: win_equiv = round(win_pct * 82, 1))",
        )
        return task, truth
    task = Task(
        task_id=tid, family="elo",
        question=(f"Where do the {full} rank in the ELO power ratings "
                  f"for the {SEASON} season? Give the rank and the team's "
                  f"ELO rating."),
        entities=[row["abbr"]], gold_tool_families=["elo"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"names": {"team": full}, "rank": row["rank"],
               "elo": row["elo"]},
        computed_at=_now(),
        source="silver_hist_gamelogs (same 538-style ELO math as "
               "get_elo_standings)",
    )
    return task, truth


# ---------------------------------------------------------------------------
# rotation family: mirrors get_rotation_check's warehouse-first pipeline
# exactly. Players come from silver_hist_player_seasons (season totals are
# per-game MIN * GP; MPG keeps the warehouse per-game value), on/off DIFF
# from the "Pts per 100 Possessions" row of silver_on_off (entity
# f"player:{pid}"). The enriched list is the top 15 by MPG (per-game
# role, not cumulative minutes); tiers sort by MPG desc with core = the
# top 5 at 20+ GP, bench = next 5 of the rest, fringe = next 5
# (CORE_GP_FLOOR = 20, same as the tool's _tier_players). Five question
# variants: thin (15+/10+ MPG counts, the thin-rotation flags' core
# facts), closing (best net rating among the same top-25-by-possessions,
# 100+ possession display slice the tool shows, deduped by lineup name
# since the re-seeded silver_lineups carries duplicate rows per unit),
# starter_onoff (average on/off of the MPG core; bench players 6-10 have
# near-zero on/off coverage warehouse-wide, so the starter-vs-bench
# comparison is ungradeable on current data), minutes (core players'
# share of the top-15 rotation's minutes), and clutch (top clutch-minute
# rotation players from silver_clutch). The tool calls get_lineup_stats
# with min_possessions=100 and limit=25 for its units, so the closing
# ground truth re-implements that unit pipeline (_rot_shown_units):
# dedupe to one canonical row per GROUP_ID (largest MIN, tie-break
# latest _fetched_at), per-100 ratings from the same play-level
# possession aggs, 100-possession floor, top-25 slice. Never imports
# app.tools (anti-circularity).
# ---------------------------------------------------------------------------

_ROT_CORE_GP_FLOOR = 20


def _rot_onoff(pid) -> tuple[float | None, bool]:
    # Verbatim mirror of the tool's _fetch_rotation_onoff: DIFF is the
    # "Pts per 100 Possessions" row's "On-Off" column; CACHED is True
    # whenever any on/off row exists for the player (even without a
    # parseable Pts-per-100 row), exactly as the tool reports it.
    try:
        rows = _qd('SELECT Stat, "On-Off" FROM silver_on_off '
                   'WHERE _season = ? AND _entity = ?',
                   [SEASON, f"player:{pid}"])
    except Exception:
        return None, False
    if not rows:
        return None, False
    for r in rows:
        if r.get("Stat") == "Pts per 100 Possessions":
            try:
                return float(r.get("On-Off")), True
            except (TypeError, ValueError):
                return None, True
    return None, True


def _rot_enriched(abbr: str) -> list[dict]:
    rows = _qd("SELECT player_id, player_name, gp, min "
               "FROM silver_hist_player_seasons "
               "WHERE _season = ? AND team_abbreviation = ?",
               [SEASON, abbr])
    enriched = []
    for r in rows:
        try:
            pid = r.get("player_id")
            name = r.get("player_name") or ""
            gp_f = int(r.get("gp") or 0)
            mpg = float(r.get("min") or 0)
        except (TypeError, ValueError):
            continue
        min_f = round(mpg * gp_f, 1) if gp_f > 0 else 0.0
        diff, cached = _rot_onoff(pid)
        enriched.append({"PLAYER": name, "PLAYER_ID": pid, "GP": gp_f,
                         "MIN": min_f, "MPG": round(mpg, 1),
                         "DIFF": diff, "CACHED": cached})
    # Top 15 by per-game minutes (MPG), mirroring the tool: a star who
    # missed games stays in the tiering set instead of being squeezed
    # out by cumulative-minutes sorting.
    enriched.sort(key=lambda p: float(p.get("MPG") or 0), reverse=True)
    return enriched[:15]


def _rot_tiers(players: list[dict]) -> tuple[list[dict], list[dict],
                                             list[dict]]:
    # Verbatim mirror of the tool's _tier_players: tiers sort by MPG
    # (per-game role); core is the top 5 at CORE_GP_FLOOR+ games, bench
    # and fringe are the next 5 each of the remainder.
    by_mpg = sorted(players, key=lambda p: float(p.get("MPG") or 0),
                    reverse=True)
    core = [p for p in by_mpg
            if (p.get("GP") or 0) >= _ROT_CORE_GP_FLOOR][:5]
    core_ids = {id(p) for p in core}
    rest = [p for p in by_mpg if id(p) not in core_ids]
    return core, rest[:5], rest[5:10]


def _rot_avg_diff(players: list[dict]) -> float | None:
    # Verbatim mirror of the tool's _avg_diff: average of cached DIFFs,
    # rounded to 1dp; None when no cached rows.
    diffs = [p.get("DIFF") for p in players
             if p.get("CACHED") and isinstance(p.get("DIFF"), (int, float))]
    if not diffs:
        return None
    return round(sum(diffs) / len(diffs), 1)


def _rot_shown_units(tid: int, min_poss: int = 100,
                     limit: int = 25) -> list[dict]:
    # Mirrors get_lineup_stats' unit pipeline exactly as the rotation
    # tool consumes it: collapse silver_lineups to one canonical row per
    # GROUP_ID (largest MIN wins; ties break to the latest _fetched_at,
    # compared as ISO strings), build per-100 ratings from the
    # play-level possession aggs (MIN*2 estimated fallback), sort by
    # possessions desc, apply the sample floor, take the limit slice.
    rows = _qd("SELECT GROUP_NAME, GROUP_ID, GP, MIN, PTS, PLUS_MINUS, "
               "_fetched_at FROM silver_lineups "
               "WHERE _season = ? AND _entity = ?",
               [SEASON, f"team:{tid}"])
    if not rows:
        return []

    def _canon_key(r: dict) -> tuple:
        try:
            minutes = float(r.get("MIN") or 0)
        except (TypeError, ValueError):
            minutes = 0.0
        return (minutes, str(r.get("_fetched_at") or ""))

    canon: dict[str, dict] = {}
    for r in rows:
        gid = str(r.get("GROUP_ID") or r.get("GROUP_NAME") or "")
        prev = canon.get(gid)
        if prev is None or _canon_key(r) > _canon_key(prev):
            canon[gid] = r
    agg = _lineup_possession_aggs(tid)
    units = []
    for r in canon.values():
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
    return visible[:limit]


def _rot_closing(tid: int) -> dict | None:
    # The tool's _closing_candidates takes the highest-NET_RATING units
    # of that same 25-row display slice (top 5). The closing pick is the
    # slice's max net; a tied best net across distinct units is
    # ungradeable (the agent cannot know the tool's tie order).
    units = _rot_shown_units(tid, min_poss=100, limit=25)
    if not units:
        return None
    nets = [u["NET_RATING"] for u in units]
    best = max(nets)
    if nets.count(best) > 1:
        return None
    return next(u for u in units if u["NET_RATING"] == best)


def _rot_closers(tid: int, ids: set) -> list[dict] | None:
    # Mirrors the tool's clutch_context exactly: silver_clutch MIN desc,
    # rotation player ids only, top 3. Returns None when fewer than 2
    # closers exist, or when any of the top closers has a suffix name
    # (Jr/II/...) — last-token name_recall cannot match those even on a
    # verbatim answer, so the variant is skipped (same rule as the
    # gamelog/impact families).
    rows = _qd("SELECT PLAYER_ID, PLAYER_NAME, MIN FROM silver_clutch "
               "WHERE _season = ? AND TEAM_ID = ? ORDER BY MIN DESC",
               [SEASON, tid])
    out = []
    for r in rows:
        if ids and r.get("PLAYER_ID") not in ids:
            continue
        name = r.get("PLAYER_NAME") or ""
        try:
            mins = round(float(r.get("MIN") or 0), 2)
        except (TypeError, ValueError):
            continue
        out.append({"name": name, "min": mins})
        if len(out) >= 3:
            break
    if len(out) < 2:
        return None
    for c in out:
        last = str(c["name"]).split()[-1].rstrip(".") if c["name"] else ""
        if last in _IMPACT_NAME_SUFFIXES:
            return None
    return out


def gen_rotation(rng, ctx) -> tuple[Task, GroundTruth]:
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
        players = _rot_enriched(abbr)
        if len(players) < 10:
            continue
        core, bench, fringe = _rot_tiers(players)
        top15 = (core + bench + fringe)[:15]
        ids = {p.get("PLAYER_ID") for p in players
               if p.get("PLAYER_ID") is not None}
        variants = ["thin"]
        closing = _rot_closing(tid)
        if closing is not None:
            variants.append("closing")
        starter_avg = _rot_avg_diff(core)
        if starter_avg is not None:
            # Bench (players 6-10) on/off coverage is near-zero
            # warehouse-wide, so the starter-vs-bench comparison is
            # ungradeable on current data; the core's side and the
            # minutes share each get their own variant instead.
            variants.append("starter_onoff")
        share = None
        total_min = sum(p["MIN"] for p in top15)
        if total_min > 0:
            # Verbatim mirror of the tool: the 0-1 ratio is rounded to
            # 3dp first, then expressed as a percent for the question.
            share = round(round(sum(p["MIN"] for p in core) / total_min, 3)
                          * 100, 1)
            variants.append("minutes")
        closers = _rot_closers(tid, ids)
        if closers is not None:
            variants.append("clutch")
        variant = rng.choice(variants)
        tid2 = ctx["task_id"]
        base = dict(task_id=tid2, family="rotation", entities=[abbr],
                    gold_tool_families=["rotation"],
                    timeout_s=ctx["timeout_s"], seed=ctx["seed"])
        if variant == "thin":
            task = Task(
                **base,
                question=(f"How thin is the {abbr} rotation this season? "
                          f"Give the number of rotation players averaging "
                          f"15+ minutes per game and the number averaging "
                          f"10+ minutes per game."),
            )
            truth = GroundTruth(
                task_id=tid2,
                facts={
                    "players_15plus_mpg": sum(
                        1 for p in players if p["MPG"] >= 15),
                    "players_10plus_mpg": sum(
                        1 for p in players if p["MPG"] >= 10),
                },
                computed_at=_now(),
                source="nba_api via silver_hist_player_seasons (same MPG "
                       "counts as get_rotation_check's thin-rotation "
                       "flags)",
            )
            return task, truth
        if variant == "closing":
            task = Task(
                **base,
                question=(f"Which {abbr} five-man lineup is the best "
                          f"closing candidate this season (minimum 100 "
                          f"possessions)? Give its net rating per 100 "
                          f"possessions, offensive rating, defensive "
                          f"rating, and possessions."),
            )
            truth = GroundTruth(
                task_id=tid2,
                # No names dict: five-man GROUP_NAMEs share surnames
                # across units, so last-token name_recall
                # false-positives on wrong lineups (same reason as the
                # lineups family). The four numeric facts uniquely
                # identify the unit.
                facts={"net_rating": closing["NET_RATING"],
                       "off_rating": closing["OFF_RATING"],
                       "def_rating": closing["DEF_RATING"],
                       "possessions": closing["poss"]},
                computed_at=_now(),
                source="nba_api via silver_lineups plus "
                       "silver_hist_possessions (same 100-possession "
                       "floor and top-25 display slice as "
                       "get_rotation_check's closing candidates)",
            )
            return task, truth
        if variant == "starter_onoff":
            task = Task(
                **base,
                question=(f"What is the average on/off (points per 100 "
                          f"possessions) of the {abbr} core rotation "
                          f"players this season (top 5 by minutes per "
                          f"game, at least 20 games played)?"),
            )
            truth = GroundTruth(
                task_id=tid2,
                facts={"starter_avg_onoff": starter_avg},
                computed_at=_now(),
                source="nba_api via silver_hist_player_seasons plus "
                       "silver_on_off (same core tier and on/off "
                       "averaging as get_rotation_check's "
                       "starter_bench_split)",
            )
            return task, truth
        if variant == "minutes":
            task = Task(
                **base,
                question=(f"How top-heavy is the {abbr} rotation this "
                          f"season? Give the percent of the top-15 "
                          f"rotation's total minutes taken by the core "
                          f"rotation players (top 5 by minutes per game, "
                          f"at least 20 games played)."),
            )
            truth = GroundTruth(
                task_id=tid2,
                facts={"starter_min_share_pct": share},
                computed_at=_now(),
                source="nba_api via silver_hist_player_seasons (same "
                       "starter minutes share as get_rotation_check's "
                       "starter_bench_split)",
            )
            return task, truth
        # clutch
        facts = {"names": {f"closer_{i}": c["name"]
                           for i, c in enumerate(closers, 1)}}
        for i, c in enumerate(closers, 1):
            facts[f"closer_{i}_min"] = c["min"]
        task = Task(
            **base,
            question=(f"Who are the {abbr} top clutch-minute players "
                      f"this season (clutch = last 5 minutes, margin "
                      f"5 or less)? Give the names and clutch minutes "
                      f"of the top {len(closers)}."),
        )
        truth = GroundTruth(
            task_id=tid2, facts=facts, computed_at=_now(),
            source="nba_api via silver_clutch (same player-scope "
                   "clutch context as get_rotation_check)",
        )
        return task, truth
    raise SkipTask("no team with a gradeable rotation variant")


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
    "prediction": gen_prediction,
    "freshness": gen_freshness,
    "headtohead": gen_headtohead,
    "zones": gen_zones,
    "impact": gen_impact,
    "gamelog": gen_gamelog,
    "elo": gen_elo,
    "rotation": gen_rotation,
}
