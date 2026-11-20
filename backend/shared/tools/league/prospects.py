import re
import unicodedata as _ud
from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg, _warehouse_tables
from .draft_contracts import _norm_draft_year


def _norm(s: object) -> str:
    return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                   if not _ud.combining(c)).lower().strip()


def _height_in(raw: object) -> float | None:
    s = str(raw or "").strip()
    m = re.fullmatch(r"(\d)[-' ](\d+(?:\.\d+)?)[\"’]?", s)
    if m:
        return int(m.group(1)) * 12 + float(m.group(2))
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _board_rows(con, draft_year: str, key: str) -> list[dict[str, Any]]:
    out = []
    for r in con.execute(
            "SELECT \"ORDER\", PLAYER_NAME, PLAYER_SLUG, POSITION, SCHOOL,"
            " TEAM_ABBREVIATION, HEIGHT, WEIGHT_LBS, CLASS_YEAR, AGE,"
            " BOARD, _fetched_at"
            " FROM silver_draft_boards WHERE _season = ?",
            [draft_year]).fetchall():
        row = dict(zip(["ORDER", "PLAYER_NAME", "PLAYER_SLUG", "POSITION",
                        "SCHOOL", "TEAM_ABBREVIATION", "HEIGHT",
                        "WEIGHT_LBS", "CLASS_YEAR", "AGE", "BOARD",
                        "_fetched_at"], r))
        if key in _norm(row["PLAYER_NAME"]):
            out.append(row)
    return out


def _stats_row(con, draft_year: str, key: str) -> dict[str, Any] | None:
    for r in con.execute(
            "SELECT PLAYER_NAME, TEAM, GP, PTS, REB, AST, TS_PCT, USG"
            " FROM silver_prospect_stats WHERE _season = ?",
            [draft_year]).fetchall():
        row = dict(zip(["PLAYER_NAME", "TEAM", "GP", "PTS", "REB", "AST",
                        "TS_PCT", "USG"], r))
        if key in _norm(row["PLAYER_NAME"]):
            return row
    return None


def _slot_comps(con, pick: int, draft_year: str) -> list[dict[str, Any]]:
    if not pick:
        return []
    year = int(draft_year)
    rows = con.execute(
        "SELECT PLAYER_NAME, OVERALL_PICK, TEAM_ABBREVIATION, DRAFT_YEAR"
        " FROM silver_hist_draft"
        " WHERE DRAFT_YEAR BETWEEN ? AND ?"
        " AND OVERALL_PICK BETWEEN ? AND ?"
        " ORDER BY DRAFT_YEAR DESC, OVERALL_PICK LIMIT 8",
        [max(2000, year - 8), year - 1, max(1, pick - 3), pick + 3]).fetchall()
    return [dict(zip(["PLAYER_NAME", "OVERALL_PICK", "TEAM_ABBREVIATION",
                      "DRAFT_YEAR"], r)) for r in rows]


def _combine_comps(con, position: str, height_in: float | None,
                   weight: float | None) -> list[dict[str, Any]]:
    if height_in is None:
        return []
    latest = con.execute(
        "SELECT MAX(_season) FROM silver_combine").fetchone()[0]
    if not latest:
        return []
    primary_pos = str(position or "").split("-")[0][:1]
    rows = con.execute(
        "SELECT PLAYER_NAME, POSITION, HEIGHT_WO_SHOES, WEIGHT,"
        " WINGSPAN, _season FROM silver_combine WHERE _season = ?"
        " AND HEIGHT_WO_SHOES IS NOT NULL",
        [latest]).fetchall()
    scored = []
    for r in rows:
        row = dict(zip(["PLAYER_NAME", "POSITION", "HEIGHT_WO_SHOES",
                        "WEIGHT", "WINGSPAN", "_season"], r))
        try:
            h = float(row["HEIGHT_WO_SHOES"])
        except (TypeError, ValueError):
            continue
        score = abs(h - height_in)
        if weight:
            try:
                score += abs(float(row["WEIGHT"]) - weight) / 50
            except (TypeError, ValueError):
                pass
        if primary_pos and str(row["POSITION"] or "").startswith(primary_pos):
            score -= 0.5
        scored.append((score, row))
    scored.sort(key=lambda t: t[0])
    return [r for _, r in scored[:5]]


@tool(description=(
    "Prospect lookup for the upcoming draft: public big-board/mock "
    "placement, current college production stats, pick-slot comps from "
    "historical drafts, and nearest historical combine measurables. "
    "Player name; draft_year defaults to the current class (2027). "
    "Warehouse only; refresh with seed_prospects.py. International "
    "prospects carry board/physical data without college stats."))
def get_prospect(player: str = "", draft_year: str = "2027",
                 position: str = "") -> dict[str, Any]:
    _pkg()
    name = str(player or "").strip()
    if not name:
        return {"tool": "get_prospect", "ok": False, "error": "player needed"}
    try:
        year = _norm_draft_year(str(draft_year or "2027"))
    except ValueError as exc:
        return {"tool": "get_prospect", "ok": False, "error": str(exc)}
    key = _norm(name)
    try:
        with _owned_connection(None, read_only=True) as con:
            tables = _warehouse_tables(con)
            boards = _board_rows(con, year, key) \
                if "silver_draft_boards" in tables else []
            stats = _stats_row(con, year, key) \
                if "silver_prospect_stats" in tables else []
            if not boards and not stats:
                return {"tool": "get_prospect", "ok": False,
                        "error": (f"{name} not found in {year} prospect data; "
                                  "run seed_prospects.py to load big boards "
                                  "and college stats.")}
            pick = next((b.get("ORDER") for b in boards
                         if b["BOARD"] == "mock_draft"), None)
            slot = _slot_comps(con, int(pick or 0), year) \
                if "silver_hist_draft" in tables else []
            board_row = boards[0] if boards else {}
            h_in = _height_in(board_row.get("HEIGHT"))
            try:
                w_lbs = float(board_row.get("WEIGHT_LBS") or 0) or None
            except (TypeError, ValueError):
                w_lbs = None
            comps = _combine_comps(con, position or str(
                board_row.get("POSITION") or ""), h_in, w_lbs) \
                if "silver_combine" in tables else []
    except FileNotFoundError:
        return {"tool": "get_prospect", "ok": False,
                "error": "warehouse absent; run seed_prospects.py first."}
    international = bool(boards) and not stats
    return {
        "tool": "get_prospect",
        "ok": True,
        "player": (boards[0]["PLAYER_NAME"] if boards
                   else (stats or {}).get("PLAYER_NAME") or name),
        "draft_year": year,
        "boards": boards,
        "college_stats": stats or None,
        "pick_slot_comps": slot,
        "combine_comps": comps,
        "meta": {
            "source": "warehouse",
            "tables": {"boards": "silver_draft_boards",
                       "college_stats": "silver_prospect_stats",
                       "slot_comps": "silver_hist_draft",
                       "combine_comps": "silver_combine"},
            "sources": ["tankathon", "barttorvik", "nba_api"],
            "international_or_non_ncaa": international,
            "stats_available": bool(stats),
        },
    }
