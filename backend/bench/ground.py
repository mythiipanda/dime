"""Runtime task generators. Ground truth comes from the warehouse directly.

Anti-circularity rule: this module imports app.store and app.sources only.
It never imports app.tools, so the benchmark cannot reward the agent for
agreeing with its own tool wrappers.
"""

from datetime import datetime, timezone

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
    cat = rng.choice(CATS)
    rows = _q(
        f"SELECT PLAYER_ID, PLAYER, GP, {cat} FROM silver_leaders_{cat.lower()} "
        "WHERE _season = ? ORDER BY RANK LIMIT 80", [SEASON],
    )
    rows = [r for r in rows if (r[2] or 0) > 0]
    if len(rows) < 2:
        raise SkipTask(f"too few leaders for {cat}")
    a, b = rng.sample(rows, 2)
    leader = a if (a[3] or 0) >= (b[3] or 0) else b
    tid = ctx["task_id"]
    task = Task(
        task_id=tid, family="compare",
        question=(f"Compare {a[1]} vs {b[1]} on {cat} this season. "
                  f"Who leads and by how much?"),
        entities=[a[1], b[1]], gold_tool_families=["compare"],
        timeout_s=ctx["timeout_s"], seed=ctx["seed"],
    )
    truth = GroundTruth(
        task_id=tid,
        facts={"a_name": a[1], "b_name": b[1], "a_value": a[3],
               "b_value": b[3], "leader_name": leader[1]},
        computed_at=_now(), source=f"nba_api via silver_leaders_{cat.lower()}",
    )
    return task, truth


def _parse_gamedate(raw: str) -> tuple:
    try:
        return (0, datetime.strptime(str(raw), "%b %d, %Y"))
    except (TypeError, ValueError):
        return (1, str(raw or ""))


def gen_chain(rng, ctx) -> tuple[Task, GroundTruth]:
    ents = _q("SELECT DISTINCT _entity FROM silver_player_gamelogs "
              "WHERE _season = ?", [SEASON])
    if not ents:
        raise SkipTask("no player gamelogs in warehouse")
    tried: set[str] = set()
    box: list = []
    name, gid, date, matchup, pts = "", "", "", "", 0
    for _ in range(10):
        ents = _q("SELECT DISTINCT _entity FROM silver_player_gamelogs "
                  "WHERE _season = ?", [SEASON])
        cands = [e[0] for e in ents if e[0] not in tried]
        if not cands:
            break
        entity = rng.choice(cands)
        tried.add(entity)
        try:
            pid = int(entity.split(":")[1])
        except (IndexError, ValueError):
            continue
        name_rows = _q("SELECT PLAYER FROM silver_leaders_pts WHERE "
                       "_season = ? AND PLAYER_ID = ? LIMIT 1",
                       [SEASON, pid])
        if not name_rows:
            continue
        name = name_rows[0][0]
        games = _q("SELECT Game_ID, GAME_DATE, MATCHUP, PTS FROM "
                   "silver_player_gamelogs WHERE _season = ? AND _entity = ?",
                   [SEASON, entity])
        if not games:
            continue
        games = sorted(games, key=lambda g: _parse_gamedate(g[1]))
        gid, date, matchup, pts = games[-1]
        box = _q("SELECT firstName, familyName, points FROM silver_boxscores "
                 "WHERE GAME_ID = ?", [str(gid)])
        if not box:
            continue
        break
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
    rows = _q("SELECT PLAYER_NAME, TEAM, SALARY_2025_26 FROM silver_salaries "
              "WHERE SALARY_2025_26 > 0")
    if len(rows) < 2:
        raise SkipTask("salary sheet too thin")
    for _ in range(50):
        a, b = rng.sample(rows, 2)
        if a[1] != b[1]:
            break
    else:
        raise SkipTask("no cross-team salary pair found")
    allow_a = int(a[2] * 1.25 + 250_000)
    allow_b = int(b[2] * 1.25 + 250_000)
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
        computed_at=_now(), source="bref_contracts via silver_salaries",
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


GENERATORS = {
    "lookup": gen_lookup,
    "compare": gen_compare,
    "chain": gen_chain,
    "adjudicate": gen_adjudicate,
    "trade": gen_trade,
    "brief": gen_brief,
    "finder": gen_finder,
}
