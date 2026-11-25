import re
from typing import Any

from shared.tools._core import (
    _LEAGUE_SCOPE_TOKENS, _PLAYER_ROWS, _historical_team_note,
    _suggest_teams, coerce_player_id, coerce_team_id,
    last_completed_season, score_player_candidates)

_FIELD_KINDS = {
    "season": "season", "seasons": "season_list",
    "start_season": "season", "end_season": "season",
    "through_season": "season",
    "draft_year": "year", "fa_year": "year",
    "player": "player", "player_id": "player", "player_ids": "player_list",
    "player_a": "player", "player_b": "player", "players": "player_list",
    "players_a": "player_list", "players_b": "player_list",
    "teammate": "player", "entity": "entity", "subject": "entity",
    "team": "team", "team_id": "team", "teams": "team_list",
    "team_a": "team", "team_b": "team", "opponent": "team",
    "team_abbrev": "team", "home_abbrev": "team",
    "benchmark_team": "team",
    "table": "table", "tables": "table_list",
    "stat": "stat", "stat_category": "stat",
    "game_id": "game_id",
    "game_date": "date", "date": "date", "start": "date", "end": "date",
    "start_date": "date_iso", "end_date": "date_iso", "since": "date_iso",
}

_SEP = r"[-–—/_.\s]"


class ArgMiss(ValueError):

    def __init__(self, field: str, kind: str, value: object,
                 candidates=(), hint: str = "") -> None:
        self.field = field
        self.kind = kind
        self.value = value
        self.candidates = [str(c) for c in candidates][:5]
        self.hint = hint
        msg = f"unknown {kind} for {field}: {value!r}"
        if self.candidates:
            msg += f" (did you mean {', '.join(self.candidates)}?)"
        if hint:
            msg += f" {hint}"
        super().__init__(msg)

    def payload(self) -> dict[str, Any]:
        out = {"field": self.field, "kind": self.kind,
               "value": self.value}
        if self.candidates:
            out["did_you_mean"] = self.candidates
        if self.hint:
            out["hint"] = self.hint
        return out


def _split_list(value: object) -> list[str] | None:
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if isinstance(value, (list, tuple)):
        return [str(p).strip() for p in value if str(p).strip()]
    return None


def canonical_season(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    low = text.lower()
    for prefix in ("the ", "season ", "nba "):
        if low.startswith(prefix):
            text = text[len(prefix):].strip()
            low = text.lower()
            break
    if low.endswith(" season"):
        text = text[:-7].strip()
    m = re.fullmatch(r"(\d{4})" + _SEP + r"?(\d{2,4})", text)
    if m:
        start = int(m.group(1))
        end_raw = m.group(2)
        end = int(end_raw) % 100
        if len(end_raw) == 4 and end_raw[:2] not in ("19", "20"):
            return None
        if len(end_raw) == 4:
            end = int(end_raw[2:])
        if end == (start + 1) % 100:
            return f"{start}-{end:02d}"
        raise ArgMiss("season", "season", value,
                      candidates=_range_split(start, end_raw),
                      hint=_coverage_hint())
    m = re.fullmatch(r"(\d{2})" + _SEP + r"(\d{2})", text)
    if m:
        start = 2000 + int(m.group(1))
        end = int(m.group(2))
        if end == (start + 1) % 100:
            return f"{start}-{end:02d}"
    if re.fullmatch(r"\d{4}", text):
        return text
    return None


def _range_split(start: int, end_raw: str) -> list[str]:
    end = int(end_raw) % 100
    if len(end_raw) == 4:
        end = int(end_raw[2:])
    years = list(range(start + 1, end + 40))
    return [f"{y}-{y + 1 - (y + 1) // 100 * 100:02d}"
            for y in (start, 2000 + end)][:2] or []


def _coverage_hint() -> str:
    last = last_completed_season() or ""
    return f"coverage ends at {last}" if last else ""


def canonical_year(value: object) -> str | None:
    m = re.fullmatch(r"(\d{4})", str(value or "").strip())
    return m.group(1) if m else None


def canonical_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        return f"{month:02d}/{day:02d}/{year:04d}"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{int(m.group(2)):02d}/{int(m.group(3)):02d}/{m.group(1)}"
    for fmt in ("%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(text, fmt)
            return f"{d.month:02d}/{d.day:02d}/{d.year:04d}"
        except ValueError:
            pass
    return None


def canonical_date_iso(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    us = canonical_date(text)
    if us:
        month, day, year = us.split("/")
        return f"{year}-{month}-{day}"
    return None


def _player_candidates(value: str) -> list[str]:
    try:
        ranked = score_player_candidates(str(value).strip())
        return [r[1].get("full_name", "") for r in ranked[:3]]
    except Exception:
        return []


def _normalize_player(value: object, field: str) -> object:
    raw = str(value or "").strip()
    if not raw or not _PLAYER_ROWS:
        return value
    tail = re.sub(r"^[A-Z]{3}:", "", raw)
    if tail.isdigit():
        try:
            return int(tail)
        except ValueError:
            pass
    try:
        coerce_player_id(tail)
    except ValueError:
        raise ArgMiss(field, "player", value, _player_candidates(raw))
    return tail if tail != raw else value


def _normalize_team(value: object, field: str) -> object:
    raw = str(value or "").strip()
    key = " ".join(raw.lower().split())
    if not key:
        return value
    if key in _LEAGUE_SCOPE_TOKENS:
        raise ArgMiss(field, "team", value, hint=_league_hint())
    try:
        coerce_team_id(raw)
    except ValueError:
        raise ArgMiss(field, "team", value, _suggest_teams(raw),
                      hint=_historical_team_note(raw) or "")
    return value


def _league_hint() -> str:
    return ("for league-wide asks use a leaders tool or sql_exec over the "
            "silver_* tables instead of an empty team")


def _normalize_entity(value: object, field: str) -> object:
    raw = str(value or "").strip()
    if not raw or not _PLAYER_ROWS:
        return value
    for kind in (coerce_player_id, coerce_team_id):
        try:
            kind(raw)
            return value
        except ValueError:
            continue
    raise ArgMiss(field, "entity", value,
                  _player_candidates(raw) + _suggest_teams(raw))


def _declared_tables() -> list[str]:
    try:
        from shared import store
        con = store.connect(read_only=True)
        try:
            return [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        finally:
            con.close()
    except Exception:
        return []


def _normalize_table(value: object, field: str) -> object:
    raw = str(value or "").strip()
    if not raw:
        return value
    low = raw.lower()
    if not low.startswith("silver_"):
        low = f"silver_{low}"
    declared = _declared_tables()
    if not declared:
        return value
    if low in declared:
        return low if raw != low else value
    import difflib
    close = difflib.get_close_matches(low, declared, n=3, cutoff=0.6)
    raise ArgMiss(field, "table", value, close,
                  hint="declared tables are listed by warehouse_schema")


def _normalize_season(value: object, field: str) -> object:
    canon = canonical_season(value)
    if canon is None:
        raise ArgMiss(field, "season", value, hint=_coverage_hint())
    return canon


def _normalize_date_value(kind: str, value: object, field: str) -> object:
    canon = (canonical_date_iso if kind == "date_iso" else canonical_date)(value)
    if canon is None:
        raise ArgMiss(field, "date", value)
    return canon


def _normalize_game_id(value: object, field: str) -> object:
    text = str(value or "").strip()
    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        return digits
    raise ArgMiss(field, "game_id", value,
                  hint="nba_api game ids are 10 digits, e.g. '0022500001'")


def _normalize_one(tool_name: str, field: str, kind: str, value: object) -> object:
    if value is None:
        return value
    if kind in ("season_list", "player_list", "team_list", "table_list"):
        if kind == "season_list" and (
                isinstance(value, int)
                or re.fullmatch(r"\d{1,2}", str(value).strip())):
            return value
        parts = _split_list(value)
        if parts is None:
            return value
        base = kind[:-5]
        out = [_normalize_one(tool_name, field, base, p) for p in parts]
        if isinstance(value, str):
            return ", ".join(str(o) for o in out)
        return out
    if isinstance(value, str) and not value.strip():
        return value
    if kind == "season":
        return _normalize_season(value, field)
    if kind == "year":
        canon = canonical_year(value)
        if canon is None:
            raise ArgMiss(field, "year", value)
        return canon
    if kind == "player":
        return _normalize_player(value, field)
    if kind == "team":
        return _normalize_team(value, field)
    if kind == "entity":
        return _normalize_entity(value, field)
    if kind == "table":
        return _normalize_table(value, field)
    if kind in ("date", "date_iso"):
        return _normalize_date_value(kind, value, field)
    if kind == "game_id":
        return _normalize_game_id(value, field)
    if kind == "stat":
        return value
    return value


def field_kind(tool_name: str, field: str, param_kinds: dict | None = None) -> str | None:
    if param_kinds:
        override = (param_kinds.get(tool_name) or {}).get(field)
        if override:
            return override
    return _FIELD_KINDS.get(field)


_PLAYER_PART_RE = re.compile(r"^player[_-]?(\d+)$", re.I)


def _consolidate_player_parts(out: dict[str, Any]) -> None:
    if str(out.get("players") or "").strip():
        return
    parts = sorted(
        ((int(m.group(1)), key) for key in out if (m := _PLAYER_PART_RE.match(key))),
        key=lambda pair: pair[0],
    )
    names = [str(out[key]).strip() for _, key in parts if str(out.get(key) or "").strip()]
    if len(names) < 2:
        return
    for _, key in parts:
        out.pop(key, None)
    out["players"] = ", ".join(names)


def normalize_call_args(tool_name: str, arguments: dict[str, Any],
                        param_kinds: dict | None = None) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return arguments
    out = dict(arguments)
    _consolidate_player_parts(out)
    for field, value in arguments.items():
        kind = field_kind(tool_name, field, param_kinds)
        if not kind:
            continue
        try:
            out[field] = _normalize_one(tool_name, field, kind, value)
        except ArgMiss:
            raise
        except Exception:
            continue
    return out


def arg_miss_result(tool_name: str, miss: ArgMiss) -> dict[str, Any]:
    return {"tool": tool_name, "ok": False, "rows": [], "columns": [],
            "error": str(miss), "arg_miss": miss.payload()}
