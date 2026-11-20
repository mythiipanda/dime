import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


def _card_stat(p: dict, *keys: str) -> str:
    for k in keys:
        v = p.get(k)
        if v is not None:
            return str(v)
    return "\u2014"


def _card_pct(p: dict, *keys: str) -> str:
    for k in keys:
        v = p.get(k)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        if f <= 1.0:
            f *= 100
        return f"{f:.1f}%"
    return "\u2014"


def _build_debate_html(players: list[dict], season: str, topic: str) -> tuple[str, str, str]:
    import html as _html

    def _row(label: str, va: str, vb: str) -> str:
        return (
            f'<div class="row"><span class="stat-a">{_html.escape(va)}</span>'
            f'<span class="label">{_html.escape(label)}</span>'
            f'<span class="stat-b">{_html.escape(vb)}</span></div>'
        )

    stats_html = "".join(
        _row(label, fmt(players[0], *keys), fmt(players[1], *keys))
        for label, keys, fmt in (
            ("PPG", ("ppg", "PTS"), _card_stat),
            ("RPG", ("rpg", "REB"), _card_stat),
            ("APG", ("apg", "AST"), _card_stat),
            ("FG%", ("fg_pct", "FG_PCT"), _card_pct),
            ("3P%", ("fg3_pct", "FG3_PCT"), _card_pct),
            ("Games", ("gp", "G", "GP"), _card_stat),
        )
    )
    name_a = _html.escape(_card_stat(players[0], "name", "PLAYER", "player"))
    name_b = _html.escape(_card_stat(players[1], "name", "PLAYER", "player"))
    topic_html = f'<div class="topic">{_html.escape(str(topic).strip())}</div>' if str(topic or "").strip() else ""
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name_a} vs {name_b} \u2014 Dime Debate Card</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; background: #f5f5f4;
  display: flex; justify-content: center; padding: 24px; margin: 0; }}
.card {{ background: #fff; border-radius: 16px; padding: 32px; max-width: 520px;
  width: 100%; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
.header {{ text-align: center; margin-bottom: 24px; }}
.topic {{ display: inline-block; font-size: 12px; font-weight: 600;
  color: #0891b2; border: 1px solid #0891b2; border-radius: 999px;
  padding: 3px 12px; margin-bottom: 10px; letter-spacing: 1px; }}
.vs {{ font-size: 13px; color: #78716c; letter-spacing: 2px; margin: 8px 0; }}
h1 {{ font-size: 22px; margin: 0; color: #1c1917; }}
.season {{ font-size: 13px; color: #a8a29e; margin-top: 4px; }}
.row {{ display: flex; align-items: center; padding: 10px 0;
  border-bottom: 1px solid #f5f5f4; }}
.row:last-child {{ border-bottom: none; }}
.stat-a, .stat-b {{ flex: 1; font-size: 17px; font-weight: 600; color: #1c1917; }}
.stat-a {{ text-align: left; }}
.stat-b {{ text-align: right; }}
.label {{ flex: 1; text-align: center; font-size: 12px; color: #a8a29e;
  letter-spacing: 1px; }}
.footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #d6d3d1; }}
.accent {{ color: #0891b2; }}
</style></head><body>
<div class="card">
<div class="header">
{topic_html}
<h1>{name_a} <span class="accent">vs</span> {name_b}</h1>
<div class="season">{_html.escape(season)} season \u00b7 via Dime</div>
</div>
{stats_html}
<div class="footer">Settle the debate with data</div>
</div></body></html>"""
    return doc, name_a, name_b


@tool(
    description='Generate a shareable HTML debate card comparing two players.\n\nReturns a self-contained HTML file with side-by-side stats,\nstyled for sharing. Saves to workspace and returns the path.\nOptional topic labels the debate (e.g. "MVP race").'
)
def get_debate_card(a: str, b: str, season: str | None = None, topic: str = "") -> dict[str, Any]:
    import asyncio as _asyncio
    import unicodedata as _ud
    from pathlib import Path as _Path

    pkg = _pkg()
    season = pkg.resolve_season(season)

    async def _fetch() -> dict:
        res = await pkg.get_compare.ainvoke({"a": a, "b": b, "season": season})
        return res if isinstance(res, dict) else {"ok": False}

    try:
        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            comp = _asyncio.run(_fetch())
        else:
            import concurrent.futures as _cf

            with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
                comp = _ex.submit(lambda: _asyncio.run(_fetch())).result(timeout=120)
    except Exception as exc:
        comp = {"ok": False, "error": str(exc)[:160]}
    if not comp.get("ok"):
        return {"tool": "get_debate_card", "ok": False, "error": comp.get("error", "comparison failed")}

    rows = comp.get("rows", {})
    players = [rows.get(key, {}) for key in ("a", "b") if isinstance(rows.get(key, {}), dict)]
    if len(players) < 2:
        return {"tool": "get_debate_card", "ok": False, "error": "could not load both players"}

    html_doc, name_a, name_b = _build_debate_html(players, season, topic)
    out_dir = _Path(__file__).resolve().parent.parent.parent.parent / "data" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)

    def _slug(s: str) -> str:
        folded = _ud.normalize("NFKD", s).encode("ascii", "ignore").decode()
        return "".join(c for c in folded if c.isalnum())[:20] or "player"

    out_path = out_dir / f"debate_{_slug(name_a)}_vs_{_slug(name_b)}_{season.replace('-', '')}.html"
    out_path.write_text(html_doc, encoding="utf-8")

    def _line(p: dict) -> dict:
        return {
            "name": _card_stat(p, "name", "PLAYER", "player"),
            "team": _card_stat(p, "team", "TEAM", "team"),
            "ppg": _card_stat(p, "ppg", "PTS"),
            "rpg": _card_stat(p, "rpg", "REB"),
            "apg": _card_stat(p, "apg", "AST"),
            "fg_pct": _card_stat(p, "fg_pct", "FG_PCT"),
            "fg3_pct": _card_stat(p, "fg3_pct", "FG3_PCT"),
            "ts_pct": _card_stat(p, "ts_pct", "TS_PCT"),
            "usg_pct": _card_stat(p, "usg_pct", "USG_PCT"),
        }

    return {
        "tool": "get_debate_card",
        "ok": True,
        "rows": {"path": str(out_path), "players": [name_a, name_b], "stats": [_line(p) for p in players]},
        "meta": {"season": season, "format": "html"},
    }


@tool(description="Multi-part player report: season line, advanced profile, shots, clutch.")
def get_player_report(player: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ..league import get_clutch

    try:
        pid = pkg.coerce_player_id(player)
    except ValueError as exc:
        return {"tool": "get_player_report", "ok": False, "error": str(exc)}
    avg = pkg.get_season_averages.invoke({"player_id": pid, "season": season})
    if not avg.get("ok") or not avg.get("rows"):
        _err: dict[str, Any] = {"tool": "get_player_report", "ok": False, "error": avg.get("error", "season line unavailable")}
        if avg.get("season_error") is True:
            _err["season_error"] = True
        return _err
    line = avg["rows"][0]
    name = str(line.get("PLAYER") or player)

    historical = season != pkg.last_completed_season()
    adv = {"ok": False} if historical else pkg.get_advanced.invoke({"player": pid, "season": season})
    shots = {"ok": False} if historical else pkg.get_shot_zones.invoke({"player_id": pid, "season": season})
    clutch = {"ok": False} if historical else get_clutch.invoke({"scope": "player", "season": season, "player": name})
    a = adv.get("rows") if adv.get("ok") and isinstance(adv.get("rows"), dict) else None
    z = shots.get("rows") if shots.get("ok") and isinstance(shots.get("rows"), list) else []
    cr = clutch.get("rows") if clutch.get("ok") and isinstance(clutch.get("rows"), list) else []
    crow = next((r for r in cr if str(r.get("PLAYER_NAME", "")).lower() == name.lower()), None)
    top_zones = sorted(z, key=lambda r: float(r.get("share") or 0), reverse=True)[:3]
    efficiency = line.get("TS_PCT")
    efficiency_text = f" {100 * float(efficiency):.1f}% true shooting." if isinstance(efficiency, (int, float)) else ""
    lines = [
        f"{name}, {season}: {line.get('PPG'):g} PPG, {line.get('RPG'):g} RPG, {line.get('APG'):g} APG in {line.get('GP'):g} games."
        + efficiency_text
    ]
    if a:
        lines.append(
            f"Advanced: {a.get('TS_PCT'):g}% true shooting, {a.get('USG_PCT'):g}% usage, "
            f"{a.get('PIE'):g} PIE, {a.get('NET_RATING'):+g} net rating."
        )
    if top_zones:
        lines.append(
            "Shot profile: "
            + "; ".join(
                f"{pkg._SHOT_ZONE_LABELS.get(str(r.get('zone')), r.get('zone'))} "
                f"{100 * float(r.get('share') or 0):.1f}% of shots at {100 * float(r.get('FG_PCT') or 0):.1f}% FG"
                for r in top_zones
            )
            + "."
        )
    if crow:
        lines.append(
            f"Clutch: {crow.get('PTS')} points in {crow.get('GP')} games, "
            f"{100 * float(crow.get('FG_PCT') or 0):.1f}% FG, plus-minus {int(crow.get('PLUS_MINUS') or 0):+d}."
        )
    return {
        "tool": "get_player_report",
        "ok": True,
        "rows": {"season_line": line, "advanced": a, "shot_profile": z, "clutch": crow},
        "meta": {
            "source": "warehouse composite",
            "season": season,
            "player": name,
            "deterministic_answer": "\n".join(lines),
            **({"season_to_date": avg["meta"]["season_to_date"]} if "season_to_date" in avg.get("meta", {}) else {}),
        },
    }


def _eval_tier(gp: int, minutes: float, pie_rank: int, usage_rank: int, rapm_rank: int | None) -> str:
    if gp >= 40 and pie_rank <= 10 and rapm_rank is not None and rapm_rank <= 25:
        return "superstar"
    if gp >= 40 and pie_rank <= 40 and (usage_rank <= 60 or (rapm_rank is not None and rapm_rank <= 75)):
        return "star"
    if gp >= 20 and minutes >= 25:
        return "starter"
    return "role player"


def _eval_lines(
    name: str, tier: str, season: str, gp: int, minutes: float, a: dict[str, Any],
    usage_rank: int, ts_rank: int, pie_rank: int,
    rapm: float | None, rapm_rank: int | None, rapm_n: int | None,
    value_row: dict[str, Any] | None, comp_rows: list[dict[str, Any]],
) -> list[str]:
    lines = [
        f"{name} grades as a {tier} for the {season} season.",
        f"Profile: {gp} games, {minutes:g} MPG, {a.get('USG_PCT'):g}% usage (rank {usage_rank}), "
        f"{a.get('TS_PCT'):g}% true shooting (rank {ts_rank}), and {a.get('PIE'):g} PIE (rank {pie_rank}).",
    ]
    if rapm is not None:
        lines.append(f"Impact context: {rapm:+g} RAPM-lite, rank {rapm_rank} of {rapm_n} qualified players; RAPM-lite is an estimate.")
    if isinstance(value_row, dict):
        pred = int(value_row.get("PREDICTED") or 0)
        sal = int(value_row.get("SALARY") or 0)
        residual = int(value_row.get("RESIDUAL") or 0)
        lines.append(
            f"Modeled value: ${pred / 1e6:.1f}M against a ${sal / 1e6:.1f}M salary "
            f"({residual / 1e6:+.1f}M salary-minus-model residual)."
        )
    comp_names = [str(r.get("PLAYER")) for r in comp_rows[:5] if r.get("PLAYER")]
    if comp_names:
        lines.append("Closest statistical comps: " + ", ".join(comp_names) + ".")
    return lines


@tool(
    description="Grounded player tier, advanced profile, modeled value, and comps.\n\nTier rules are deterministic and transparent. Current-season impact uses\nRAPM-lite as a context metric, never as the sole tier label."
)
def get_player_evaluation(player: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    from ..league import get_contract_value

    try:
        pid = pkg.coerce_player_id(player)
    except ValueError as exc:
        return {"tool": "get_player_evaluation", "ok": False, "error": str(exc)}
    adv = pkg.get_advanced.invoke({"player": pid, "season": season})
    if not adv.get("ok") or not isinstance(adv.get("rows"), dict):
        return {"tool": "get_player_evaluation", "ok": False, "error": adv.get("error", "advanced profile unavailable")}
    a = adv["rows"]
    name = str(a.get("PLAYER_NAME") or player)
    gp = int(a.get("GP") or 0)
    minutes = (float(a.get("MIN") or 0) / gp) if gp > 0 else 0.0
    pie_rank = int(a.get("PIE_RANK") or 9999)
    usage_rank = int(a.get("USG_PCT_RANK") or 9999)
    ts_rank = int(a.get("TS_PCT_RANK") or 9999)

    rapm = rapm_rank = rapm_n = None
    try:
        rows = pkg._read_df(
            "SELECT name, rapm, possessions, ROW_NUMBER() OVER (ORDER BY rapm DESC) AS impact_rank, "
            "COUNT(*) OVER () AS impact_n FROM silver_rapm WHERE _season = ? AND rapm IS NOT NULL AND possessions >= 2000 "
            "QUALIFY LOWER(name) = LOWER(?)",
            [season, name],
        )
        if rows:
            rapm = round(float(rows[0]["rapm"]), 2)
            rapm_rank = int(rows[0]["impact_rank"])
            rapm_n = int(rows[0]["impact_n"])
    except Exception:
        pass

    tier = _eval_tier(gp, minutes, pie_rank, usage_rank, rapm_rank)
    value = get_contract_value.invoke({"season": season, "min_gp": 20, "player": name})
    value_row = (value.get("rows") or [None])[0] if isinstance(value.get("rows"), list) else None
    comps = pkg.get_comps.invoke({"player_id": pid, "season": season, "k": 5})
    comp_rows = comps.get("rows") if comps.get("ok") else []
    comp_rows = comp_rows if isinstance(comp_rows, list) else []
    profile = {
        "gp": gp,
        "minutes": minutes,
        "usage_pct": a.get("USG_PCT"),
        "usage_rank": usage_rank,
        "true_shooting_pct": a.get("TS_PCT"),
        "true_shooting_rank": ts_rank,
        "pie": a.get("PIE"),
        "pie_rank": pie_rank,
        "net_rating": a.get("NET_RATING"),
        "rapm_lite": rapm,
        "rapm_lite_rank": rapm_rank,
        "rapm_lite_pool": rapm_n,
    }
    lines = _eval_lines(name, tier, season, gp, minutes, a, usage_rank, ts_rank, pie_rank, rapm, rapm_rank, rapm_n, value_row, comp_rows)
    return {
        "tool": "get_player_evaluation",
        "ok": True,
        "rows": {
            "player": name,
            "player_id": str(pid),
            "team": a.get("TEAM_ABBREVIATION"),
            "season": season,
            "tier": tier,
            "profile": profile,
            "modeled_value": value_row,
            "comps": comp_rows[:5],
        },
        "meta": {
            "source": "warehouse composite",
            "season": season,
            "tier_rule": (
                "superstar = 40+ GP, top-10 PIE and top-25 RAPM-lite; star = 40+ GP, top-40 PIE and either "
                "top-60 usage or top-75 RAPM-lite; starter = 20+ GP and 25+ MPG; otherwise role player"
            ),
            "value_method": (value.get("meta") or {}).get("formula"),
            "deterministic_answer": "\n".join(lines),
        },
    }


def _rapm_note() -> str:
    pkg = _pkg()
    try:
        con = pkg.store.connect(read_only=True)
        try:
            seasons = sorted(
                {row[0] for row in con.execute("SELECT DISTINCT _season FROM silver_rapm").fetchall() if row[0]},
                key=lambda s: s[:4],
            )
        finally:
            con.close()
    except Exception:
        return "The warehouse has no season range to report."
    if not seasons:
        return "The warehouse has no season range to report."
    if len(seasons) == 1:
        return f"RAPM-lite covers {seasons[0]}; FiveThirtyEight RAPTOR covers 2014-15 through 2021-22."
    return f"RAPM-lite covers {seasons[0]}\u2013{seasons[-1]}; FiveThirtyEight RAPTOR covers 2014-15 through 2021-22."


@tool(
    description="Overall top-N players board ranked by the warehouse impact metric.\n\nCurrent seasons (RAPM-lite coverage, e.g. 2025-26): rank by RAPM-lite\nwith a possessions floor. Historical seasons 2014-15..2021-22: rank by\nFiveThirtyEight WAR. Other seasons return an honest coverage note -\nnever a single-stat board presented as an overall ranking."
)
def get_player_rankings(n: int = 15, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        n = max(1, min(int(n), 50))
    except (TypeError, ValueError):
        n = 15
    meta: dict[str, Any] = {"season": season, "n": n}
    try:
        r = pkg._read_df(
            "SELECT name, rapm, possessions FROM silver_rapm WHERE _season = ? AND rapm IS NOT NULL AND possessions >= 2000 "
            "ORDER BY rapm DESC LIMIT ?",
            [season, n],
        )
        if r:
            rows = [
                {"rank": i + 1, "player": row.get("name"), "rapm": round(float(row.get("rapm")), 2), "possessions": int(row.get("possessions") or 0)}
                for i, row in enumerate(r)
            ]
            meta["metric"] = "rapm_lite"
            return {"tool": "get_player_rankings", "ok": True, "rows": rows, "meta": meta}
    except Exception:
        pass
    try:
        r = pkg._read_df(
            "SELECT PLAYER_NAME, RAPTOR_TOTAL, WAR_TOTAL FROM silver_raptor_player WHERE _season = ? AND WAR_TOTAL IS NOT NULL "
            "ORDER BY WAR_TOTAL DESC LIMIT ?",
            [season, n],
        )
        if r:
            rows = [
                {"rank": i + 1, "player": row.get("PLAYER_NAME"), "war": round(float(row.get("WAR_TOTAL")), 1), "raptor": round(float(row.get("RAPTOR_TOTAL") or 0), 1)}
                for i, row in enumerate(r)
            ]
            meta["metric"] = "raptor_war"
            return {"tool": "get_player_rankings", "ok": True, "rows": rows, "meta": meta}
    except Exception:
        pass
    return {"tool": "get_player_rankings", "ok": False, "error": f"No overall impact metric covers {season}. {pkg._rapm_note()}", "meta": meta}
