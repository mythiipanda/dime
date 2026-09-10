"""Runtime task generators. Ground truth comes from the warehouse directly.

Anti-circularity rule: this module imports app.store and app.sources only.
It never imports app.tools, so the benchmark cannot reward the agent for
agreeing with its own tool wrappers.
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
}
