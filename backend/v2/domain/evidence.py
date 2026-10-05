from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import math
from typing import Any

from v2.contracts import (
    EvidenceEnvelope,
    TaskSpec,
    canonical_entity_id,
    canonical_entity_ref,
    format_window,
    window_of_arguments,
)


@dataclass(frozen=True)
class EvidenceValue:
    evidence_id: str
    path: str
    value: Any


def iter_values(evidence: EvidenceEnvelope) -> Iterator[EvidenceValue]:
    def walk(value: Any, path: str) -> Iterator[EvidenceValue]:
        if isinstance(value, Mapping):
            for key, child in value.items():
                yield from walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f"{path}[{index}]")
        else:
            yield EvidenceValue(evidence.evidence_id, path, value)

    yield from walk(evidence.rows, "rows")


def decimal_value(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Decimal) and not value.is_finite():
        return None
    if isinstance(value, (date, datetime)):
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if text.endswith("%") or text[-1:].upper() in {"K", "M", "B"}:
        text = text[:-1]
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


class EvidenceIndex:
    def __init__(self, envelopes: Iterable[EvidenceEnvelope]) -> None:
        items = [
            EvidenceEnvelope.model_validate(item.model_dump())
            for item in envelopes
        ]
        ids = [item.evidence_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence ids must be unique")
        self._items = {item.evidence_id: item for item in items}
        self._validate_lineage()

    def _validate_lineage(self) -> None:
        for item in self._items.values():
            missing = set(item.lineage) - self._items.keys()
            if missing:
                raise ValueError(
                    f"unknown evidence lineage for {item.evidence_id}: {sorted(missing)}"
                )
            if item.evidence_id in item.lineage:
                raise ValueError(f"evidence {item.evidence_id} cannot cite itself")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(evidence_id: str) -> None:
            if evidence_id in visiting:
                raise ValueError("evidence lineage must be acyclic")
            if evidence_id in visited:
                return
            visiting.add(evidence_id)
            for parent in self._items[evidence_id].lineage:
                visit(parent)
            visiting.remove(evidence_id)
            visited.add(evidence_id)

        for evidence_id in self._items:
            visit(evidence_id)

    def get(self, evidence_id: str) -> EvidenceEnvelope | None:
        return self._items.get(evidence_id)

    def require(self, evidence_ids: Iterable[str]) -> list[EvidenceEnvelope]:
        ids = list(evidence_ids)
        missing = sorted(set(ids) - self._items.keys())
        if missing:
            raise KeyError(f"unknown evidence ids: {missing}")
        return [self._items[evidence_id] for evidence_id in ids]

    def ancestors(self, evidence_id: str) -> set[str]:
        if evidence_id not in self._items:
            raise KeyError(evidence_id)
        found: set[str] = set()
        stack = list(self._items[evidence_id].lineage)
        while stack:
            parent = stack.pop()
            if parent in found:
                continue
            found.add(parent)
            stack.extend(self._items[parent].lineage)
        return found

    def values(self, evidence_ids: Iterable[str]) -> Iterator[EvidenceValue]:
        for item in self.require(evidence_ids):
            yield from iter_values(item)

@dataclass(frozen=True)
class SourceIntegrityIssue:
    code: str
    message: str


def source_integrity_issues(
    evidence: EvidenceEnvelope,
    *,
    required_season: str | None = None,
    expected_teams: Mapping[str, str] | None = None,
    required_window: tuple[date | None, date | None] | None = None,
) -> list[SourceIntegrityIssue]:
    evidence = EvidenceEnvelope.model_validate(evidence.model_dump())
    issues: list[SourceIntegrityIssue] = []
    if required_season and evidence.season is None:
        issues.append(SourceIntegrityIssue(
            "season_missing",
            f"season-scoped evidence does not declare required season {required_season}"))
    elif required_season and evidence.season != required_season:
        issues.append(SourceIntegrityIssue(
            "season_mismatch",
            f"evidence season {evidence.season} does not match {required_season}"))
    if required_window is not None:
        asked_start, asked_end = required_window
        if asked_start is not None or asked_end is not None:
            served = (evidence.window_start, evidence.window_end)
            if served == (None, None):
                issues.append(SourceIntegrityIssue(
                    "window_missing",
                    f"evidence covers the full season but "
                    f"{format_window(asked_start, asked_end)} is required"))
            elif served != (asked_start, asked_end):
                issues.append(SourceIntegrityIssue(
                    "window_mismatch",
                    f"evidence covers {format_window(*served)} but "
                    f"{format_window(asked_start, asked_end)} is required"))
    expected = {name.casefold(): team.upper()
                for name, team in (expected_teams or {}).items()}
    rows = evidence.rows if isinstance(evidence.rows, list) else [evidence.rows]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("PLAYER_NAME") or row.get("player") or "").strip()
        team = str(row.get("TEAM") or row.get("team") or "").strip().upper()
        wanted = expected.get(name.casefold())
        if name and team and wanted and team != wanted:
            issues.append(SourceIntegrityIssue(
                "team_conflict",
                f"{name} is {team} in evidence but {wanted} in season context"))
    return issues

@dataclass(frozen=True)
class GuardDenial:
    capability: str
    check: str
    message: str


NON_EMPTY_ROWS_REQUIRED = frozenset({"sql_exec"})

_SEASON_LIKE_KEYS = frozenset({"season", "through_season"})

_AS_OF_KEYS = ("as_of", "salary_date", "production_date", "fetched_at")

_ENTITY_ARGUMENT_TYPES = {
    "player": "player",
    "player_id": "player",
    "team": "team",
    "team_id": "team",
}

_ROW_ENTITY_KEYS = {
    "player": "player",
    "player_id": "player",
    "team": "team",
    "team_id": "team",
}


def _is_season_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split("-")
    return (
        len(parts) == 2
        and len(parts[0]) == 4
        and len(parts[1]) == 2
        and all(part.isdigit() for part in parts)
        and int(parts[1]) == (int(parts[0]) + 1) % 100
    )


def _call_seasons(arguments: Mapping[str, Any]) -> set[str]:
    found: set[str] = set()
    for value in arguments.values():
        if _is_season_text(str(value).strip() if value is not None else ""):
            found.add(str(value).strip())
    for key in _SEASON_LIKE_KEYS:
        value = arguments.get(key)
        if value is not None and _is_season_text(str(value).strip()):
            found.add(str(value).strip())
    return found


def _parse_call_as_of(arguments: Mapping[str, Any]) -> date | None:
    for key in _AS_OF_KEYS:
        value = arguments.get(key)
        if not value:
            continue
        try:
            return date.fromisoformat(str(value).split("T", 1)[0])
        except ValueError:
            continue
    return None


def _call_entities(arguments: Mapping[str, Any]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for key, entity_type in _ENTITY_ARGUMENT_TYPES.items():
        value = arguments.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        found.add((entity_type, canonical_entity_id(entity_type, text)))
    return found


def _task_entities(task: TaskSpec) -> set[tuple[str, str]]:
    return {canonical_entity_ref(entity) for entity in task.entities}


def _row_seasons(rows: Any) -> set[str]:
    items = rows if isinstance(rows, list) else [rows]
    found: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key, value in item.items():
            if str(key).casefold() == "season" and _is_season_text(
                str(value).strip() if value is not None else ""
            ):
                found.add(str(value).strip())
    return found


def _row_entities(rows: Any) -> set[tuple[str, str]]:
    items = rows if isinstance(rows, list) else [rows]
    found: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key, value in item.items():
            entity_type = _ROW_ENTITY_KEYS.get(str(key).casefold())
            if entity_type is None or value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            found.add((entity_type, canonical_entity_id(entity_type, text)))
    return found


def _envelope_entities(envelope: EvidenceEnvelope) -> set[tuple[str, str]]:
    found = {canonical_entity_ref(entity) for entity in envelope.entities}
    return found | _row_entities(envelope.rows)


def _rows_empty(rows: Any) -> bool:
    if isinstance(rows, list):
        return len(rows) == 0
    if isinstance(rows, Mapping):
        return len(rows) == 0
    return False


def pre_call_denials(
    task: TaskSpec,
    capability_id: str,
    arguments: Mapping[str, Any],
    *,
    task_season_scoped: bool = True,
) -> list[GuardDenial]:
    denials: list[GuardDenial] = []
    required_season = task.season.value if task.season else None
    if required_season is not None and task_season_scoped:
        for asked in sorted(_call_seasons(arguments)):
            if asked != required_season:
                denials.append(GuardDenial(
                    capability=capability_id,
                    check="season_mismatch",
                    message=(
                        f"{capability_id} pre-call season_mismatch: "
                        f"call asks season {asked} but task requires {required_season}"
                    ),
                ))
                break
    asked_window = (task.window_start, task.window_end)
    if asked_window != (None, None):
        served = window_of_arguments(arguments, required_season)
        if served != (None, None) and served != asked_window:
            denials.append(GuardDenial(
                capability=capability_id,
                check="window_mismatch",
                message=(
                    f"{capability_id} pre-call window_mismatch: "
                    f"call covers {format_window(*served)} but task requires "
                    f"{format_window(*asked_window)}"
                ),
            ))
    if task.as_of is not None:
        call_as_of = _parse_call_as_of(arguments)
        if call_as_of is not None and call_as_of > task.as_of:
            denials.append(GuardDenial(
                capability=capability_id,
                check="as_of_mismatch",
                message=(
                    f"{capability_id} pre-call as_of_mismatch: "
                    f"call as_of {call_as_of.isoformat()} is after task as_of "
                    f"{task.as_of.isoformat()}"
                ),
            ))
    if task.entities:
        wanted = _task_entities(task)
        named = _call_entities(arguments)
        if named and wanted and named.isdisjoint(wanted):
            denials.append(GuardDenial(
                capability=capability_id,
                check="entity_mismatch",
                message=(
                    f"{capability_id} pre-call entity_mismatch: "
                    f"call entities {sorted(named)} do not intersect task entities "
                    f"{sorted(wanted)}"
                ),
            ))
    return denials


def post_result_denials(
    task: TaskSpec,
    envelope: EvidenceEnvelope,
) -> list[GuardDenial]:
    capability_id = envelope.capability
    denials: list[GuardDenial] = []
    required_season = task.season.value if task.season else None
    if required_season is not None and envelope.task_season_scoped:
        if envelope.season is None:
            denials.append(GuardDenial(
                capability=capability_id,
                check="season_mismatch",
                message=(
                    f"{capability_id} post-result season_mismatch: "
                    f"result declares no season but task requires {required_season}"
                ),
            ))
        elif envelope.season != required_season:
            denials.append(GuardDenial(
                capability=capability_id,
                check="season_mismatch",
                message=(
                    f"{capability_id} post-result season_mismatch: "
                    f"result season {envelope.season} does not match task season "
                    f"{required_season}"
                ),
            ))
        for row_season in sorted(_row_seasons(envelope.rows)):
            if row_season != required_season:
                denials.append(GuardDenial(
                    capability=capability_id,
                    check="row_season_mismatch",
                    message=(
                        f"{capability_id} post-result row_season_mismatch: "
                        f"row season {row_season} does not match task season "
                        f"{required_season}"
                    ),
                ))
                break
    asked_window = (task.window_start, task.window_end)
    if asked_window != (None, None):
        served = (envelope.window_start, envelope.window_end)
        if served == (None, None):
            denials.append(GuardDenial(
                capability=capability_id,
                check="window_mismatch",
                message=(
                    f"{capability_id} post-result window_mismatch: "
                    f"result covers the full season but task requires "
                    f"{format_window(*asked_window)}"
                ),
            ))
        elif served != asked_window:
            denials.append(GuardDenial(
                capability=capability_id,
                check="window_mismatch",
                message=(
                    f"{capability_id} post-result window_mismatch: "
                    f"result covers {format_window(*served)} but task requires "
                    f"{format_window(*asked_window)}"
                ),
            ))
    if task.as_of is not None and envelope.as_of is not None:
        if envelope.as_of > task.as_of:
            denials.append(GuardDenial(
                capability=capability_id,
                check="as_of_mismatch",
                message=(
                    f"{capability_id} post-result as_of_mismatch: "
                    f"result as_of {envelope.as_of.isoformat()} is after task as_of "
                    f"{task.as_of.isoformat()}"
                ),
            ))
    if task.entities:
        wanted = _task_entities(task)
        served_entities = _envelope_entities(envelope)
        if served_entities and wanted and served_entities.isdisjoint(wanted):
            denials.append(GuardDenial(
                capability=capability_id,
                check="entity_mismatch",
                message=(
                    f"{capability_id} post-result entity_mismatch: "
                    f"result entities {sorted(served_entities)} do not intersect "
                    f"task entities {sorted(wanted)}"
                ),
            ))
    if _rows_empty(envelope.rows) and capability_id in NON_EMPTY_ROWS_REQUIRED:
        denials.append(GuardDenial(
            capability=capability_id,
            check="empty_rows_forbidden",
            message=(
                f"{capability_id} post-result empty_rows_forbidden: "
                f"empty result set is not an allowed success for {capability_id}"
            ),
        ))
    return denials


class EvidenceAdmissionError(ValueError):
    def __init__(self, issues: list[SourceIntegrityIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def admit_evidence(
    evidence: EvidenceEnvelope,
    *,
    required_season: str | None = None,
    expected_teams: Mapping[str, str] | None = None,
    required_window: tuple[date | None, date | None] | None = None,
) -> EvidenceEnvelope:
    issues = source_integrity_issues(
        evidence, required_season=required_season,
        expected_teams=expected_teams, required_window=required_window)
    if issues:
        raise EvidenceAdmissionError(issues)
    return evidence
