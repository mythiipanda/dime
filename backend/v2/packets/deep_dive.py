import math
from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

import duckdb
from fastapi import HTTPException

from v2.boards.service import _name
from .models import Callout, Chart, Citation, Column, Kpi, Kpis, Packet, Section, Series, Table, Text, format_value


BASE = "silver_player_season"
ADV = "silver_advanced"
METRICS = [("PPG", "Points", BASE, "per_game"), ("RPG", "Rebounds", BASE, "per_game"),
           ("APG", "Assists", BASE, "per_game"), ("SPG", "Steals", BASE, "per_game"),
           ("BPG", "Blocks", BASE, "per_game"), ("TS_PCT", "TS%", ADV, "pct"),
           ("USG_PCT", "Usage", ADV, "pct"), ("NET_RATING", "Net rating", ADV, "rating")]


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def unique(rows):
    return rows[0] if len(rows) == 1 else {}


class Data:
    def __init__(self, con, season):
        self.con, self.season = con, season
        self.available = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        self.citations, self.gaps = {}, []

    def read(self, table, columns, where, params, limit=2500, order=""):
        if table not in self.available:
            self.gaps.append(f"{table}: table unavailable")
            return [], None
        sql = f'SELECT {", ".join(chr(34) + c + chr(34) for c in columns + ["_source", "_fetched_at", "_entity"])} FROM "{table}" WHERE {where}'
        if order:
            sql += " ORDER BY " + order
        sql += " LIMIT ?"
        bound = [*params, limit + 1]
        try:
            cur = self.con.execute(sql, bound)
            rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
        except (duckdb.CatalogException, duckdb.BinderException):
            self.gaps.append(f"{table}: required columns unavailable")
            return [], None
        if len(rows) > limit:
            self.gaps.append(f"{table}: exceeds safe row bound; omitted rather than using a partial population")
            return [], None
        if not rows:
            self.gaps.append(f"{table}: no matching rows")
        cid = f"c{len(self.citations) + 1}"
        dates = [str(r['_fetched_at']) for r in rows if r.get('_fetched_at')]
        self.citations[cid] = Citation(source_table=table, table=table, columns=columns,
            season="2026-27" if table == "silver_cap_players" else self.season,
            sql=sql, params=bound, fetched_at=max(dates) if dates else None,
            source=rows[0].get('_source') if rows else None,
            row_key={"scope": where, "parameters": params},
            salary_vintage={"season": "2026-27", "fetched_at": max(dates) if dates else None} if table == "silver_cap_players" else None)
        return rows, cid

    def for_row(self, cid, row, row_key):
        if not cid or not row:
            return None
        selected = f"c{len(self.citations) + 1}"
        fetched_at = str(row["_fetched_at"]) if row.get("_fetched_at") else None
        citation = self.citations[cid]
        self.citations[selected] = citation.model_copy(update={
            "row_key": row_key,
            "fetched_at": fetched_at,
            "source": row.get("_source"),
            "salary_vintage": {"season": citation.season, "fetched_at": fetched_at} if citation.salary_vintage else None,
        })
        return selected

    def derived(self, primary, supporting, transformation):
        if not primary:
            return None
        cid = f"c{len(self.citations) + 1}"
        self.citations[cid] = self.citations[primary].model_copy(update={
            "supporting_cites": list(dict.fromkeys(c for c in supporting if c and c != primary)),
            "transformation": transformation,
        })
        return cid


def table(rows, specs, cites, note=None, title=None, collapsed=False):
    return Table(columns=[Column(key=k, label=label, unit=unit) for k, label, unit in specs],
                 rows=rows, cites=cites, note=note, title=title, collapsed=collapsed)


def chart(rows, x, series, cid, kind="bar"):
    return Chart(chart=kind, x=x, series=[Series(key=k, label=label) for k, label in series], data=rows, cite=cid)


def unavailable(data, message):
    data.gaps.append(message)
    return Callout(md=message)


def build_packet(con, player, season):
    d = Data(con, season)
    base, bc = d.read(BASE, ["PLAYER_ID", "PLAYER", "TEAM", "AGE", "GP", "MPG", "PPG", "RPG", "APG", "SPG", "BPG"], '"_season" = ?', [season])
    adv, ac = d.read(ADV, ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "TS_PCT", "USG_PCT", "NET_RATING", "PIE"], '"_season" = ?', [season])
    identities = defaultdict(set)
    names = {}
    for row in base + adv:
        pid, name = row["PLAYER_ID"], row.get("PLAYER") or row.get("PLAYER_NAME")
        if pid is not None and name:
            identities[int(pid)].add(_name(name))
            names.setdefault(int(pid), name)
    matches = [pid for pid, spellings in identities.items() if str(player).strip() == str(pid) or _name(str(player)) in spellings]
    if len(matches) != 1:
        candidates = [{"id": pid, "name": names[pid]} for pid in sorted(matches)]
        if not matches:
            candidates = [{"id": pid, "name": name} for pid, name in sorted(names.items()) if _name(str(player)) in _name(name)][:20]
        raise HTTPException(422, detail={"reason": "ambiguous_player" if matches else "unknown_player", "candidates": candidates})
    pid = matches[0]
    b = unique([r for r in base if r["PLAYER_ID"] == pid])
    a = unique([r for r in adv if r["PLAYER_ID"] == pid])
    if not b or not a:
        d.gaps.append("Season profile or advanced row missing/ambiguous; affected metrics are null")
    rapm, rc = d.read("silver_rapm", ["player_id", "rapm", "possessions"], '"_season" = ? AND "player_id" = ?', [season, str(pid)], 10)
    salary, sc = d.read("silver_cap_players", ["player", "team", "salary"], '"_season" = ?', ["2026-27"], 2500)
    salary_matches = [r for r in salary if _name(r["player"]) in identities[pid]]
    collision = any(other != pid and spellings & identities[pid] for other, spellings in identities.items())
    s = unique(salary_matches) if not collision else {}
    profile_bc = d.for_row(bc, b, {"PLAYER_ID": pid, "_season": season})
    profile_ac = d.for_row(ac, a, {"PLAYER_ID": pid, "_season": season})
    salary_cite = d.for_row(sc, s, {"player": s.get("player"), "team": s.get("team"), "_season": "2026-27"})
    items = []
    def kpi(label, raw, unit, cid, reason=None, context=None):
        value = raw if isinstance(raw, str) else number(raw)
        if value is not None and unit == "pct":
            value *= 100
        items.append(Kpi(label=label, value=value, unit=unit, display="—" if value is None else str(round(value, 2)) if isinstance(value, float) else value,
            cite=cid, null_reason=reason or "missing_or_ambiguous_value" if value is None else None, context=context))
    for key, label, unit in [("TEAM", "Team", "text"), ("AGE", "Age", "years"), ("GP", "GP", "count"), ("MPG", "MPG", "per_game"), ("PPG", "PPG", "per_game"), ("RPG", "RPG", "per_game"), ("APG", "APG", "per_game")]:
        kpi(label, b.get(key), unit, profile_bc)
    for key, label, unit in [("TS_PCT", "TS%", "pct"), ("USG_PCT", "USG%", "pct"), ("NET_RATING", "Net rating", "rating"), ("PIE", "PIE", "pct")]:
        kpi(label, a.get(key), unit, profile_ac)
    kpi("RAPM", unique(rapm).get("rapm"), "points_per_100_possessions", rc)
    kpi("2026-27 salary", s.get("salary"), "usd", salary_cite, "unmatched_or_ambiguous_salary_name", "2026-27 salary; vintage: " + str(d.citations[salary_cite].fetched_at if salary_cite else "unavailable"))
    sections = [Section(id="profile", title="Profile", blocks=[Kpis(items=items)])]
    if any(i.value is None for i in items):
        sections[0].blocks.append(unavailable(d, "Some profile KPIs are missing or ambiguous; nulls are not estimates."))

    qualified = {}
    for row in base:
        peers = [r for r in base if r["PLAYER_ID"] == row["PLAYER_ID"]]
        if len(peers) == 1 and (number(row.get("GP")) or 0) >= 20 and (number(row.get("MPG")) or 0) >= 15:
            qualified[row["PLAYER_ID"]] = row
    qc = d.derived(bc or ac, [bc, ac], "Midrank percentile: 100*(below + 0.5*equal)/n, unique GP>=20 and MPG>=15 base players; missing/ambiguous metric rows excluded.")
    ranks, rank_cites = [], {}
    for key, label, source, unit in METRICS:
        population = base if source == BASE else adv
        indexed = defaultdict(list)
        for row in population:
            indexed[row["PLAYER_ID"]].append(row)
        values = [number(rs[0].get(key)) for peer, rs in indexed.items() if peer in qualified and len(rs) == 1 and number(rs[0].get(key)) is not None]
        value = number((b if source == BASE else a).get(key))
        percentile = 100 * (sum(v < value for v in values) + .5 * sum(v == value for v in values)) / len(values) if values and value is not None and pid in qualified else None
        ranks.append({"metric": label, "value": value * 100 if value is not None and unit == "pct" else value, "unit": unit, "percentile": percentile, "n": len(values), "null_reason": None if percentile is not None else "unqualified_or_missing_value"})
        cid = qc
        if cid:
            rank_cites[str(len(ranks)-1)] = cid
    blocks = [Text(md="Qualified cohort: GP ≥20 and MPG ≥15 in the selected season. Percentiles use midrank ties (below + half equal) / valid cohort size; higher means more, not necessarily better. [^" + bc + "]" if bc else "Qualified cohort unavailable.", cites=[bc] if bc else [])]
    blocks += [table(ranks, [("metric", "Metric", None), ("value", "Value", None), ("percentile", "Percentile", "pct"), ("n", "Valid peers", "count")], rank_cites), chart(ranks, "metric", [("percentile", "Percentile")], qc)]
    valid = [(i, r) for i, r in enumerate(ranks) if r["percentile"] is not None]
    if valid:
        lo, hi = min(valid, key=lambda x:x[1]["percentile"]), max(valid, key=lambda x:x[1]["percentile"])
        for word, (i, r) in [("Strongest", hi), ("Weakest", lo)]:
            cid = rank_cites[str(i)]
            blocks.append(Text(md=f"{word} measured percentile: {r['metric']} at {format_value(r['percentile'], 'pct')}. [^{cid}]", cites=[cid]))
    else:
        blocks.append(unavailable(d, "No qualified percentile comparison is available."))
    sections.append(Section(id="league_context", title="League context", blocks=blocks))

    zones, zc = d.read("silver_zone_splits", ["PLAYER_ID", "ZONE", "FGA", "FGM"], '"_season" = ?', [season], 10000)
    zc = d.derived(zc, [bc], "Shares use recorded FGA totals. League FG%=100*sum(FGM)/sum(FGA), over GP>=20 and MPG>=15 players; duplicate-zone players excluded. Zero-attempt buckets contribute no attempts and have null FG%.")
    grouped = defaultdict(list)
    for row in zones:
        grouped[(row["PLAYER_ID"], row["ZONE"])].append(row)
    ambiguous_zones = {peer for (peer, zone), rows in grouped.items() if len(rows) != 1}
    if ambiguous_zones:
        d.gaps.append("Duplicate shot-zone rows: affected players excluded, not arbitrarily selected.")
    own = [rs[0] for (peer, zone), rs in grouped.items() if peer == pid and len(rs) == 1]
    if pid in ambiguous_zones:
        own = []
    zone_qualified = set(qualified) - ambiguous_zones
    covered = {peer for peer, zone in grouped if peer in zone_qualified}
    if len(covered) != len(qualified):
        d.gaps.append(f"Shot-zone cohort coverage: {len(covered)} of {len(qualified)} qualified players.")
    def attempts_total(rows):
        values = [number(r["FGA"]) for r in rows]
        return sum(values) if values and all(v is not None and v >= 0 for v in values) else None
    total = attempts_total(own)
    league_total = attempts_total([rs[0] for (peer, zone), rs in grouped.items() if peer in zone_qualified and len(rs) == 1])
    zr = []
    for row in own:
        peers = [rs[0] for (peer, zone), rs in grouped.items() if peer in zone_qualified and zone == row["ZONE"] and len(rs) == 1]
        attempts = attempts_total(peers)
        positive_makes = [number(r["FGM"]) for r in peers if number(r["FGA"]) is not None and number(r["FGA"]) > 0]
        makes = sum(positive_makes) if all(v is not None for v in positive_makes) else None
        fga, fgm = number(row["FGA"]), number(row["FGM"])
        share = 100*fga/total if total and fga is not None else None
        fg = 100*fgm/fga if fga and fgm is not None else None
        league_fg = 100*makes/attempts if attempts and makes is not None else None
        league_share = 100*attempts/league_total if league_total and attempts is not None else None
        zr.append({"zone":row["ZONE"], "fga":fga, "share":share, "fg_pct":fg, "league_share":league_share, "league_fg_pct":league_fg, "share_delta": share-league_share if share is not None and league_share is not None else None, "efficiency_delta":fg-league_fg if fg is not None and league_fg is not None else None, "null_reason": "no_attempts_or_missing_value" if any(v is None for v in (fga, share, fg, league_fg, league_share)) else None})
    if any(r["null_reason"] for r in zr):
        d.gaps.append("Some shot-zone rates are null: zero attempts or missing/nonfinite input.")
    blocks = [table(zr, [("zone","Zone",None),("fga","FGA","count"),("share","FGA share","pct"),("fg_pct","FG%","pct"),("league_share","League FGA share","pct"),("league_fg_pct","League FG%","pct")], {"*":zc}), chart(zr,"zone",[("fg_pct","Player FG%"),("league_fg_pct","Qualified league FG%")],zc)] if zr and zc else []
    for key, label in [("share_delta","share"),("efficiency_delta","efficiency")]:
        eligible = [r for r in zr if r[key] is not None]
        if eligible:
            r = max(eligible,key=lambda r:abs(r[key]))
            blocks.append(Text(md=f"Largest absolute {label} delta: {r['zone']} ({format_value(r[key], 'percentage_points')}). [^{zc}]", cites=[zc]))
    if not blocks:
        blocks.append(unavailable(d,"Shot profile unavailable for this player."))
    sections.append(Section(id="shot_profile", title="Shot profile", summary="League zones are attempt-weighted over the qualified cohort; distance buckets are not geometric shot-chart zones.", blocks=blocks))

    logs, lc = d.read("silver_player_gamelogs", ["Player_ID","Game_ID","GAME_DATE","MATCHUP","MIN","PTS","REB","AST","FGA","FTA"], '"_season" = ? AND "Player_ID" = ?', [season,pid], 200)
    dated, seen = [], set()
    for row in logs:
        day = None
        for fmt in ("%b %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                day = datetime.strptime(str(row["GAME_DATE"]),fmt).date().isoformat()
                break
            except ValueError:
                pass
        if day is None or row["Game_ID"] in seen:
            dated = []
            d.gaps.append("Game logs contain invalid dates or duplicate games; form omitted.")
            break
        seen.add(row["Game_ID"])
        dated.append({**row,"date":day})
    dated.sort(key=lambda r:(r["date"],str(r["Game_ID"])))
    def averages(label, rows):
        def avg(key):
            vs=[number(r[key]) for r in rows]
            return sum(vs)/len(vs) if vs and None not in vs else None
        pts, fga, fta = avg("PTS"), avg("FGA"), avg("FTA")
        denom = 2*(fga+.44*fta) if fga is not None and fta is not None else None
        result = {"split":label,"gp":len(rows),"pts":pts,"reb":avg("REB"),"ast":avg("AST"),"ts_pct":100*pts/denom if denom and pts is not None else None}
        if any(v is None for v in result.values()):
            result["null_reason"] = "no_games_or_missing_input"
        return result
    blocks=[]
    if dated and lc:
        splits=[averages("Season",dated),averages("Last 10",dated[-10:])]
        splits += [averages(label,[r for r in dated if marker in str(r["MATCHUP"])]) for label,marker in [("Home","vs."),("Away","@")]]
        splits += [averages(month,[r for r in dated if r["date"].startswith(month)]) for month in sorted({r["date"][:7] for r in dated})]
        line=[]
        for i,r in enumerate(dated):
            window=[number(g["PTS"]) for g in dated[max(0,i-4):i+1]]
            line.append({"date":r["date"],"pts":number(r["PTS"]),"rolling_5":sum(window)/5 if len(window)==5 and None not in window else None})
        blocks=[table(splits,[("split","Split",None),("gp","Games","count"),("pts","PTS","per_game"),("reb","REB","per_game"),("ast","AST","per_game"),("ts_pct","TS%","pct")],{"*":lc},"TS% = 100 × ΣPTS / (2 × (ΣFGA + 0.44 × ΣFTA)); season averages here use available game logs."),chart(line,"date",[("pts","PTS"),("rolling_5","5-game average")],lc,"line")]
    else:
        blocks=[unavailable(d,"Form and splits unavailable: no unambiguous dated game logs.")]
    sections.append(Section(id="form_splits",title="Form & splits",blocks=blocks))

    blocks=[]
    appendix = None
    for source, cols, where, params, label in [
        ("silver_on_off",["Stat","On","Off","On-Off"],'"_season" = ? AND "_entity" = ?',[season,f"player:{pid}"],"On/off (provider values; percentage fields converted to 0–100)"),
        ("silver_clutch",["PLAYER_ID","GP","MIN","PTS","AST","REB"],'"_season" = ? AND "PLAYER_ID" = ?',[season,pid],"Clutch totals"),
        ("silver_hustle_player",["PLAYER_ID","G","MIN","DEFLECTIONS","CONTESTED_SHOTS","SCREEN_ASSISTS"],'"_season" = ? AND "PLAYER_ID" = ?',[season,pid],"Hustle totals")]:
        rows,cid=d.read(source,cols,where,params,200)
        if source != "silver_on_off" and len(rows)!=1:
            rows=[]
        if rows and cid:
            clean=[]
            for row in rows:
                entry = {k: row[k] if k == "Stat" else number(row[k]) for k in cols}
                if source == "silver_on_off":
                    entry["unit"] = "pct" if "%" in str(row["Stat"]) else "provider_stat"
                    if entry["unit"] == "pct":
                        for key in ("On", "Off", "On-Off"):
                            if entry[key] is not None:
                                entry[key] *= 100
                if any(value is None for value in entry.values()):
                    entry["null_reason"] = "missing_or_nonfinite_value"
                clean.append(entry)
            labels = {"Stat":"Statistic", "On":"On court", "Off":"Off court", "On-Off":"On minus off",
                      "GP":"Games", "G":"Games", "MIN":"Minutes", "PTS":"Points", "AST":"Assists", "REB":"Rebounds",
                      "DEFLECTIONS":"Deflections", "CONTESTED_SHOTS":"Contested shots", "SCREEN_ASSISTS":"Screen assists"}
            specs = [(k,labels.get(k,k),"rating" if k == "On-Off" else "count" if k in ("GP","G","PTS","AST","REB","DEFLECTIONS","CONTESTED_SHOTS","SCREEN_ASSISTS") else None) for k in cols if k != "PLAYER_ID"]
            if source == "silver_on_off":
                specs.append(("unit", "Unit", None))
                appendix = table(clean,specs,{"*":cid},"Full provider statistics; only labels containing % are multiplied by 100; other values retain provider units.","On/off appendix",True)
                indexed = {r["Stat"]:r for r in clean}
                curated = []
                offense, defense = indexed.get("Pts per 100 Possessions"), indexed.get("Pts per 100 Possessions - Defense")
                if offense and defense:
                    curated.append({"Stat":"Net rating", **{k:offense[k]-defense[k] if offense[k] is not None and defense[k] is not None else None for k in ("On","Off","On-Off")}, "unit":"rating"})
                for key, human in [("Net Rating","Net rating"),("Pts per 100 Possessions","Offensive rating"),("Pts per 100 Possessions - Defense","Defensive rating"),("TS%","True shooting"),("eFG%","Effective field goal"),("Pace","Pace"),("DReb%","Defensive rebound"),("Live Ball TO%","Live-ball turnover")]:
                    if key in indexed and not any(r["Stat"] == human for r in curated):
                        curated.append({**indexed[key],"Stat":human})
                selected_cite = d.derived(cid, [], "Curated provider stats; net rating is offensive points per 100 possessions minus defensive points per 100 possessions.")
                if curated:
                    blocks.append(table(curated[:8],specs,{"*":selected_cite},"Team outcomes with the player on/off; net rating is offense minus defense, not causal impact.","On/off highlights"))
                else:
                    blocks.append(unavailable(d,"Key on/off statistics unavailable; see the full appendix."))
            else:
                blocks.append(table(clean,specs,{"*":cid},"Provider totals, not per-game rates.",label))
        else:
            blocks.append(unavailable(d,f"{label}: data missing or ambiguous."))
    if len(rapm)==1:
        blocks.append(Kpis(items=[next(i for i in items if i.label=="RAPM")]))
    else:
        blocks.append(unavailable(d,"RAPM unavailable or ambiguous."))
    if appendix:
        blocks.append(appendix)
    sections.append(Section(id="impact",title="Impact",blocks=blocks))

    history,hc=d.read("silver_hist_player_seasons",["player_id","season","gp","min","pts","reb","ast","ts_pct"], '"player_id" = ? AND "season" <= ? AND "season" < ?', [pid,2025,int(season[:4])+1],100, '"season"')
    if hc:
        d.citations[hc].season = "through 2024-25"
    cc = d.derived(hc or bc or ac, [hc, bc, ac], "Historical seasons through 2024-25, followed by requested base season; current TS%=100*silver_advanced.TS_PCT. Duplicate season rows are null, not arbitrarily selected.")
    counts=defaultdict(int)
    for r in history:
        counts[r["season"]]+=1
    career=[]
    cites={}
    seen_seasons = set()
    for r in history:
        if r["season"] in seen_seasons:
            continue
        seen_seasons.add(r["season"])
        if counts[r["season"]]!=1:
            d.gaps.append(f"Ambiguous career rows for {r['season']}; metrics are null")
            career.append({"season":f"{r['season']-1}-{str(r['season'])[-2:]}", **{key:None for key in ("gp","mpg","ppg","rpg","apg","ts_pct")}, "null_reason":"ambiguous_season_rows"})
            cites[str(len(career)-1)]=cc
            continue
        career.append({"season":f"{r['season']-1}-{str(r['season'])[-2:]}","gp":number(r["gp"]),"mpg":number(r["min"]),"ppg":number(r["pts"]),"rpg":number(r["reb"]),"apg":number(r["ast"]),"ts_pct":100*number(r["ts_pct"]) if number(r["ts_pct"]) is not None else None})
        cites[str(len(career)-1)]=cc
    if b:
        career.append({"season":season,"gp":number(b.get("GP")),"mpg":number(b.get("MPG")),"ppg":number(b.get("PPG")),"rpg":number(b.get("RPG")),"apg":number(b.get("APG")),"ts_pct":100*number(a.get("TS_PCT")) if number(a.get("TS_PCT")) is not None else None})
        cites[str(len(career)-1)]=cc
    for row in career:
        if any(value is None for value in row.values()):
            row.setdefault("null_reason", "missing_or_nonfinite_value")
    blocks=[table(career,[("season","Season",None),("gp","GP","count"),("mpg","MPG","per_game"),("ppg","PPG","per_game"),("rpg","RPG","per_game"),("apg","APG","per_game"),("ts_pct","TS%","pct")],cites,"Current TS% is from silver_advanced; historical coverage is through 2024-25."),chart(career,"season",[("ppg","PPG"),("ts_pct","TS%")],cc,"line")] if career else [unavailable(d,"Career trajectory unavailable.")]
    if not history:
        blocks.append(unavailable(d,"Historical career seasons unavailable; only the current season may be shown."))
    sections.append(Section(id="career",title="Career trajectory",blocks=blocks))
    ppg = next(i for i in items if i.label == "PPG")
    if ppg.value is not None and ppg.cite:
        sections[0].summary = f"{names[pid]} averages {ppg.display} points per game in {season} [^{ppg.cite}]."
    if valid:
        sections[1].summary = next(b.md for b in sections[1].blocks if isinstance(b, Text) and b.md.startswith("Strongest"))
    if zr and zc:
        measured = [r for r in zr if r["share"] is not None]
        if measured:
            largest = max(measured,key=lambda r:r["share"])
            sections[2].summary = f"{largest['zone']} accounts for the largest recorded attempt share at {format_value(largest['share'],'pct')} [^{zc}]."
    if dated and lc:
        last = averages("Last 10",dated[-10:])
        sections[3].summary = f"Across the last {format_value(last['gp'],'count')} available games, scoring averages {format_value(last['pts'])} points per game [^{lc}]."
    rapm_item = next(i for i in items if i.label == "RAPM")
    if rapm_item.value is not None and rapm_item.cite:
        sections[4].summary = f"RAPM measures {rapm_item.display} points per 100 possessions in this warehouse snapshot [^{rapm_item.cite}]."
    elif appendix:
        sections[4].summary = f"Available on/off outcomes describe team performance with and without {names[pid]}, not causal impact [^{appendix.cites['*']}]."
    if career and cc:
        latest = career[-1]
        if latest.get("ppg") is not None:
            sections[5].summary = f"The latest available season, {latest['season']}, records {format_value(latest['ppg'])} points per game [^{cc}]."
    return Packet(id=uuid4(),kind="player_deep_dive",title=f"{names[pid]} · Player deep dive",subtitle=f"{b.get('TEAM') or 'Team unavailable'} · {season}",season=season,generated_at=datetime.now(UTC),inputs={"player":player,"player_id":pid},sections=sections,citations=d.citations,
        limitations=list(dict.fromkeys(["Descriptive packet, not a projection.","Salary is a separate 2026-27 vintage, not selected-season salary; no multi-year contract schedule.",*d.gaps])))
