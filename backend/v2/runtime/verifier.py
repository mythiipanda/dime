from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol

from pydantic import ValidationError

from v2.contracts import (
    Claim,
    ClaimKind,
    ClaimResult,
    DraftReport,
    EvidenceEnvelope,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
    format_window,
)
from v2.domain.calculations import Calculation, validate_calculation
from v2.domain.evidence import EvidenceIndex, decimal_value, iter_values

_NUMBER = re.compile(

    r"(?<![A-Za-z0-9])(?:\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|[-+]?\$?\d[\d,]*(?:\.\d+)?(?:%|[KMB])?)(?![A-Za-z0-9]|-[A-Za-z])",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SEASON = re.compile(r"\b\d{4}-\d{2}\b(?!-\d{2})")
_RANK = re.compile(r"(?:#\s*(\d+)|\b(\d+)(?:st|nd|rd|th)\b)", re.IGNORECASE)
_DIRECTION_MIN_WORDS = re.compile(r"\b(?:best|lowest|fewest)\b", re.IGNORECASE)
_DIRECTION_MAX_WORDS = re.compile(r"\b(?:best|highest|most)\b", re.IGNORECASE)
_LIST_LABEL = re.compile(r"(?m)^\s*(\d+)\.\s")
_SEMANTIC_KEYS = {
    "status", "claim_results", "missing_branches", "contradictions",
    "repair_instructions",
}
_PERCENT_LIKE_UNITS = frozenset({"percent", "percent_0_100", "fraction_0_1"})
_FRACTION_LIKE_UNITS = frozenset({"percent", "fraction_0_1"})
_WORD = re.compile(r"[A-Za-z0-9]+")
COMPETITION_ENTITY_TYPES = frozenset({"league"})

class SemanticVerifier(Protocol):
    async def verify(self, task: Any, draft: Any,
                     evidence: Sequence[Any] | Mapping[str, Any]) -> VerificationReport: ...

def _canon_number(raw: Any, unit: str | None = None) -> set[Decimal]:
    value = decimal_value(raw)
    if value is None:
        return set()
    values = {value}
    text = str(raw).strip()
    if text[-1:].upper() in {"K", "M", "B"}:
        compact = decimal_value(text[:-1])
        if compact is not None:
            values.add(compact * {"K": 1_000, "M": 1_000_000,
                                  "B": 1_000_000_000}[text[-1].upper()])
    elif abs(value) <= 1 and (unit is None or unit.casefold() in _FRACTION_LIKE_UNITS):
        values.add(value * 100)
    return values

def _matches_calculation_display(raw: str, values: set[Decimal]) -> bool:
    parsed = decimal_value(raw)
    if parsed is None or not values:
        return False

    places = max(0, len(raw.rstrip("%").replace(",", "").split(".", 1)[1])
                 if "." in raw.rstrip("%").replace(",", "") else 0)
    tolerance = Decimal(5).scaleb(-(places + 1))
    for exact in values:
        if ((parsed > 0) != (exact > 0) or (parsed < 0) != (exact < 0)):
            continue
        if abs(parsed - exact) <= tolerance:
            return True
    return False

def _number_tokens(text: str) -> list[str]:
    label_numbers = {match.start(1) for match in _LIST_LABEL.finditer(text)}
    return [match.group(0) for match in _NUMBER.finditer(text)
            if match.start() not in label_numbers]

def _words(text: str) -> list[str]:
    return [word.casefold() for word in _WORD.findall(text)]

def _states_name(words: Sequence[str], name: str) -> bool:
    run = _words(str(name))
    if not run or len(run) > len(words):
        return False
    span = len(run)
    return any(words[start:start + span] == run
               for start in range(len(words) - span + 1))

def _text_values(envelopes: Iterable[EvidenceEnvelope]) -> set[str]:
    values: set[str] = set()
    for envelope in envelopes:
        if envelope.season:
            values.add(envelope.season)
        values.update(value.casefold() for value in envelope.vintages.values())
        if envelope.as_of:
            values.add(envelope.as_of.isoformat())
        for entity in envelope.entities:
            values.update((entity.id.casefold(), entity.display_name.casefold()))
        for item in iter_values(envelope):
            if item.value is not None:
                values.add(str(item.value).strip().casefold())
    return values

def _numeric_values(envelopes: Iterable[EvidenceEnvelope]) -> set[Decimal]:
    values: set[Decimal] = set()
    for envelope in envelopes:
        unit_map = {str(key).casefold(): str(item) for key, item in envelope.units.items()}
        for item in iter_values(envelope):
            unit = None
            for segment in reversed(item.path.split(".")):
                name = segment.split("[", 1)[0].casefold()
                if name in unit_map:
                    unit = unit_map[name]
                    break
            values.update(_canon_number(item.value, unit))
            if isinstance(item.value, str):
                for token in _number_tokens(item.value):
                    values.update(_canon_number(token, unit))
    return values

def _claim_dates_supported(claim: Claim,
                           envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    supported = _text_values(envelopes)
    return [value for value in _DATE.findall(claim.text)
            if value.casefold() not in supported]

def _claim_seasons_supported(claim: Claim,
                             envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    supported = _text_values(envelopes)
    return [value for value in _SEASON.findall(claim.text)
            if value.casefold() not in supported]

def _canonical_entity(entity) -> tuple[str, str]:
    from v2.contracts import canonical_entity_ref
    return canonical_entity_ref(entity)

def _entity_reasons(task: TaskSpec, claim: Claim,
                    envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    words = _words(claim.text)
    evidence_entities = {
        (entity.type, entity.id.casefold(), entity.display_name.casefold())
        for envelope in envelopes for entity in envelope.entities
    }
    row_values = _text_values(envelopes)
    reasons: list[str] = []
    task_entities = {_canonical_entity(entity) for entity in task.entities}
    cited_entities = {
        _canonical_entity(entity)
        for envelope in envelopes for entity in envelope.entities
    }
    shared_types = ({kind for kind, _identity in task_entities}
                    & {kind for kind, _identity in cited_entities})
    if any(
        not ({item for item in task_entities if item[0] == kind}
             & {item for item in cited_entities if item[0] == kind})
        for kind in shared_types
    ):
        reasons.append("cited evidence entities do not match the task entities")
    for entity in task.entities:
        if entity.type in COMPETITION_ENTITY_TYPES:
            continue
        if not (_states_name(words, entity.display_name)
                or _states_name(words, entity.id)):
            continue
        exact = (entity.type, entity.id.casefold(), entity.display_name.casefold())
        canonical = _canonical_entity(entity)
        if (exact not in evidence_entities
                and canonical not in cited_entities
                and not {entity.id.casefold(), entity.display_name.casefold()} & row_values):
            reasons.append(f"entity {entity.display_name} is not supported by cited evidence")
    return reasons

def _row_entity_value_reasons(
    claim: Claim, envelopes: Sequence[EvidenceEnvelope],
    calculation_values: set[Decimal] | None = None,
) -> list[str]:
    text = " ".join(claim.text.casefold().split())
    identity_keys = {
        "team", "team_name", "team_abbreviation", "abbrev",
        "player", "player_name", "full_name", "name",
    }
    matched_envelopes = _matched_row_envelopes(envelopes, text, identity_keys)
    if not matched_envelopes:
        return []
    row_numbers = _numeric_values(matched_envelopes) | (calculation_values or set())
    unsupported = []
    rank_numbers = {
        value for match in _RANK.finditer(claim.text)
        for value in match.groups() if value is not None
    }
    for raw in _number_tokens(claim.text):
        if (_DATE.fullmatch(raw) or _SEASON.fullmatch(raw) or raw == "100"
                or raw in rank_numbers):
            continue
        if not (_canon_number(raw) & row_numbers):
            unsupported.append(raw)
    if unsupported:
        return [
            "claim numerals do not match the named entity rows: "
            + ", ".join(unsupported)
        ]
    return []

def _matched_row_envelopes(
    envelopes: Sequence[EvidenceEnvelope], text: str, identity_keys: set[str],
) -> list:
    matched_envelopes = []
    for envelope in envelopes:
        if not isinstance(envelope.rows, list) or len(envelope.rows) < 2:
            continue
        rows = [row for row in envelope.rows if isinstance(row, Mapping)]
        matched = []
        for row in rows:
            identities = [
                str(value).strip().casefold()
                for key, value in row.items()
                if key.casefold() in identity_keys and value is not None
            ]
            if any(value and value in text for value in identities):
                matched.append(row)
        if matched:
            matched_envelopes.append(envelope.model_copy(update={"rows": matched}))
    return matched_envelopes

def _direction_reasons(
    claim: Claim, envelopes: Sequence[EvidenceEnvelope],
) -> list[str]:
    claimed: set[Decimal] = set()
    for raw in _number_tokens(claim.text):
        if _DATE.fullmatch(raw) or _SEASON.fullmatch(raw):
            continue
        claimed.update(_canon_number(raw))
    if not claimed:
        return []
    reasons: list[str] = []
    for envelope in envelopes:
        reason = _direction_reason(claim, claimed, envelope)
        if reason is not None:
            reasons.append(reason)
    return reasons

def _direction_reason(claim: Claim, claimed: set[Decimal],
                      envelope: EvidenceEnvelope) -> str | None:
    from shared.tools.rating_metrics import TEAM_RATING_METRICS

    metric = envelope.metric_definitions.get("__requested_metric__")
    entry = TEAM_RATING_METRICS.get(metric)
    if not entry:
        return None
    direction = entry.get("direction")
    if direction == "asc":
        if not _DIRECTION_MIN_WORDS.search(claim.text):
            return None
    elif direction == "desc":
        if not _DIRECTION_MAX_WORDS.search(claim.text):
            return None
    else:
        return None
    rows = envelope.rows
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return None
    values = [decimal_value(row.get(metric)) for row in rows
              if isinstance(row, Mapping)]
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    extreme = min(values) if direction == "asc" else max(values)
    if extreme in claimed:
        return None
    bound = "minimum" if direction == "asc" else "maximum"
    return (
        f"best {entry.get('label', metric)} claim must state the {bound} "
        f"{entry.get('label', metric)} on the board"
    )

def _scope_reasons(task: TaskSpec,
                   envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    reasons: list[str] = []
    if task.season:
        seasons = {
            envelope.season for envelope in envelopes
            if envelope.season and envelope.task_season_scoped
        }
        if seasons and task.season.value not in seasons:
            reasons.append(
                f"cited evidence season {sorted(seasons)} does not match task season "
                f"{task.season.value}"
            )
    if task.as_of:
        for envelope in envelopes:
            if envelope.as_of and envelope.as_of > task.as_of:
                reasons.append(
                    f"evidence {envelope.evidence_id} is after task as-of "
                    f"{task.as_of.isoformat()}"
                )
    if task.window_start is not None or task.window_end is not None:
        asked = (task.window_start, task.window_end)
        for envelope in envelopes:
            served = (envelope.window_start, envelope.window_end)
            if served == (None, None):
                reasons.append(
                    f"evidence {envelope.evidence_id} covers the full season "
                    f"but the task asks for {format_window(*asked)}"
                )
            elif served != asked:
                reasons.append(
                    f"evidence {envelope.evidence_id} covers "
                    f"{format_window(*served)} but the task asks for "
                    f"{format_window(*asked)}"
                )
    return reasons

def _metric_unit_reasons(claim: Claim,
                         envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    reasons: list[str] = []
    text = claim.text.casefold()
    words = _words(claim.text)
    for envelope in envelopes:
        row_keys = {
            segment.split("[", 1)[0].casefold()
            for item in iter_values(envelope)
            for segment in item.path.split(".")
        }
        declared = {key.casefold() for key in envelope.metric_definitions}
        unknown_units = set(key.casefold() for key in envelope.units) - row_keys - declared
        if unknown_units:
            reasons.append(
                f"evidence {envelope.evidence_id} declares units for unknown metrics: "
                f"{sorted(unknown_units)}"
            )
        for metric, unit in envelope.units.items():
            reason = _metric_unit_reason(claim, text, words, envelope, metric, unit)
            if reason is not None:
                reasons.append(reason)
    return reasons

def _metric_unit_reason(claim: Claim, text: str, words: Sequence[str],
                        envelope: EvidenceEnvelope, metric: str,
                        unit: str) -> str | None:
    if not _states_name(words, metric):
        return None
    unit_name = unit.casefold()
    percent_shown = "%" in claim.text or "percent" in text
    if unit_name in _PERCENT_LIKE_UNITS:
        if not percent_shown:
            return f"metric {metric} is stated without a percent unit"
        return None
    if unit_name == "count":
        return None
    if unit_name == "points_per_100_possessions":
        if re.search(r"points?\s+per\s+100\s+possessions?", text):
            return None
        same_unit_values: set[Decimal] = set()
        for other, other_unit in envelope.units.items():
            if other_unit.casefold() == unit_name:
                same_unit_values.update(
                    _column_canon_values(envelope, other))
        rank_numbers = {
            value for match in _RANK.finditer(claim.text)
            for value in match.groups() if value is not None
        }
        unbound = [
            raw for raw in _number_tokens(claim.text)
            if not (_DATE.fullmatch(raw)
                    or _SEASON.fullmatch(raw)
                    or raw in rank_numbers)
            and not (_canon_number(raw) & same_unit_values)
        ]
        if unbound:
            return f"metric {metric} is stated without its declared unit {unit}"
        return None
    if unit_name.replace("_", " ") not in text:
        return f"metric {metric} is stated without its declared unit {unit}"
    return None

def _column_canon_values(envelope: EvidenceEnvelope, metric: str) -> set[Decimal]:
    unit_map = {str(key).casefold(): str(item)
                for key, item in envelope.units.items()}
    values: set[Decimal] = set()
    for item in iter_values(envelope):
        last = str(item.path).rsplit(".", 1)[-1].split("[", 1)[0]
        if last.casefold() != metric.casefold():
            continue
        unit = None
        for segment in reversed(str(item.path).split(".")):
            name = segment.split("[", 1)[0].casefold()
            if name in unit_map:
                unit = unit_map[name]
                break
        values.update(_canon_number(item.value, unit))
        if isinstance(item.value, str):
            for token in _number_tokens(item.value):
                values.update(_canon_number(token, unit))
    return values

def _metric_identity_reasons(
    claim: Claim,
    envelopes: Sequence[EvidenceEnvelope],
    supported_numbers: set[Decimal],
    calculation_values: set[Decimal] | None = None,
    allowed_numbers: set[Decimal] | None = None,
) -> list[str]:
    requested = sorted({
        str(envelope.metric_definitions.get("__requested_metric__")).upper()
        for envelope in envelopes
        if envelope.metric_definitions.get("__requested_metric__")
    })
    if not requested:
        return []
    reasons: list[str] = []
    columns = {
        metric: {envelope.evidence_id: _column_canon_values(envelope, metric)
                 for envelope in envelopes}
        for metric in requested
    }
    for metric in requested:
        reasons.extend(_metric_carrier_reasons(metric, columns[metric], envelopes))
    bound: set[Decimal] = set()
    for metric in requested:
        for values in columns[metric].values():
            bound.update(values)
    grounded = set(calculation_values or set()) | set(allowed_numbers or set())
    for envelope in envelopes:
        for qualifier in (envelope.qualification, envelope.coverage):
            if qualifier:
                for token in _number_tokens(qualifier):
                    grounded.update(_canon_number(token))
    rank_numbers = {
        value for match in _RANK.finditer(claim.text)
        for value in match.groups() if value is not None
    }
    for raw in _number_tokens(claim.text):
        reason = _metric_identity_numeral_reason(
            raw, claim, envelopes, requested, rank_numbers,
            bound, supported_numbers, grounded, calculation_values)
        if reason is not None:
            reasons.append(reason)
    return reasons

def _metric_carrier_reasons(metric, columns_by_envelope, envelopes) -> list[str]:
    carriers = {evidence_id for evidence_id, values in columns_by_envelope.items()
                if values}
    if not carriers:
        return [f"claim about {metric} cites no evidence carrying a {metric} column"]
    reasons = []
    for envelope in envelopes:
        if envelope.evidence_id not in carriers:
            reasons.append(
                f"cited {envelope.capability} evidence {envelope.evidence_id} "
                f"carries no {metric} column"
            )
    return reasons

def _metric_identity_numeral_reason(raw, claim, envelopes, requested,
                                    rank_numbers, bound, supported_numbers,
                                    grounded, calculation_values) -> str | None:
    if _DATE.fullmatch(raw) or _SEASON.fullmatch(raw):
        return None
    if (raw == "100" and "points_per_100_possessions" in {
            unit.casefold() for envelope in envelopes
            for unit in envelope.units.values()}
            and re.search(r"points?\s+per\s+100\s+possessions?",
                          claim.text, re.IGNORECASE)):
        return None
    if raw in rank_numbers:
        return None
    canon = _canon_number(raw)
    if canon & bound:
        return None
    if not (canon & supported_numbers):
        return None
    if canon & grounded:
        return None
    if (claim.kind == ClaimKind.DERIVED and claim.calculation_id
            and _matches_calculation_display(raw, calculation_values or set())):
        return None
    return (
        f"numeral {raw} does not match a {', '.join(requested)} column "
        f"value in cited evidence"
    )

def _mixed_source_reasons(claim: Claim,
                          envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    source_classes = {envelope.source.split(":", 1)[0].casefold()
                      for envelope in envelopes}
    if len(source_classes) < 2:
        return []
    text = claim.text.casefold()
    labels_sources = ("source" in text or "warehouse" in text
                      or "fallback" in text or "according to" in text)
    if labels_sources:
        return []
    return ["mixed-source claim does not label differing provenance"]

def _record_completeness_reasons(
    claim: Claim, envelopes: Sequence[EvidenceEnvelope],
) -> list[str]:
    text = claim.text.casefold()
    if not re.search(r"\b(?:best|top|leading|leader|highest)\b.*\brecord\b", text):
        return []
    matching_rows = []
    for envelope in envelopes:
        if not isinstance(envelope.rows, list):
            continue
        for row in envelope.rows:
            if not isinstance(row, Mapping):
                continue
            normalized = {str(key).casefold(): value for key, value in row.items()}
            wins = normalized.get("wins", normalized.get("w"))
            losses = normalized.get("losses", normalized.get("l"))
            if wins is None or losses is None:
                continue
            identities = [
                str(value).strip().casefold()
                for key, value in normalized.items()
                if key in {"team", "team_name", "abbrev", "team_abbreviation"}
                and value is not None
            ]
            if not identities or any(identity in text for identity in identities):
                matching_rows.append((wins, losses))
    if not matching_rows:
        return []
    numeric_pairs = re.findall(r"(\d+)\s*[-–]\s*(\d+)", claim.text)
    lexical_pairs = re.findall(
        r"(\d+)\s+wins?\b.{0,32}?\b(\d+)\s+loss(?:es)?\b",
        claim.text, re.IGNORECASE,
    )
    if not any(
        (_canon_number(wins) & _canon_number(raw_wins))
        and (_canon_number(losses) & _canon_number(raw_losses))
        for wins, losses in matching_rows
        for raw_wins, raw_losses in (*numeric_pairs, *lexical_pairs)
    ):
        return ["best-record claim must state the complete wins-losses record"]
    return []

def _qualification_coverage_reasons(claim: Claim,
                                    envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    if not _RANK.search(claim.text) and not re.search(
        r"\b(?:rank(?:ed|s)?|leader|leads|highest|lowest|best|worst)\b",
        claim.text, re.IGNORECASE,
    ):
        return []
    reasons: list[str] = []
    if not any(envelope.qualification for envelope in envelopes):
        reasons.append("rank claim lacks qualification evidence")
    if not any(envelope.coverage for envelope in envelopes):
        reasons.append("rank claim lacks coverage evidence")
    claimed_ranks = {
        Decimal(value) for match in _RANK.finditer(claim.text)
        for value in match.groups() if value is not None
    }
    explicit_rank = any(
        any(item.path.rsplit(".", 1)[-1].casefold().endswith("rank")
            and (not claimed_ranks or decimal_value(item.value) in claimed_ranks)
            for item in iter_values(envelope))
        for envelope in envelopes
    )
    if not claim.calculation_id and not explicit_rank:
        reasons.append("rank claim lacks a recomputable rank calculation")
    return reasons

def _cross_evidence_calculation_reasons(
    claim: Claim, envelopes: Sequence[EvidenceEnvelope],
) -> list[str]:
    if claim.calculation_id or len(envelopes) < 2:
        return []
    text = claim.text.casefold()
    compares = re.search(
        r"\b(?:from .{0,80} to|declin(?:e|ed)|drop(?:ped)?|fell|rose|increase[ds]?|"
        r"decrease[ds]?|difference|gap|change[ds]?)\b",
        text,
    )
    universal = re.search(r"\b(?:all|every|each|none)\b", text)
    if compares or universal:
        return ["cross-evidence comparison lacks a declared calculation"]
    return []

def _calculation_reasons(claim: Claim, calculations: Mapping[str, Calculation],
                         evidence: EvidenceIndex) -> tuple[list[str], set[Decimal]]:
    if not claim.calculation_id:
        return [], set()
    calculation = calculations.get(claim.calculation_id)
    if calculation is None:
        return [f"unknown calculation id {claim.calculation_id}"], set()
    input_ids = {input_.evidence_id for input_ in calculation.inputs}
    allowed_lineage = set(claim.evidence_ids)
    for evidence_id in claim.evidence_ids:
        if evidence.get(evidence_id) is not None:
            allowed_lineage.update(evidence.ancestors(evidence_id))
    reasons: list[str] = []
    if not input_ids <= allowed_lineage:
        reasons.append(
            f"calculation {calculation.calculation_id} uses uncited evidence: "
            f"{sorted(input_ids - allowed_lineage)}"
        )
    try:
        error = validate_calculation(calculation, evidence)
    except (KeyError, ValueError) as exc:
        error = str(exc)
    if error:
        reasons.append(error)
    return reasons, {calculation.result}

def _zero_gate_player_rows(
    envelopes: Sequence[EvidenceEnvelope], names: set[str],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for envelope in envelopes:
        data = envelope.rows
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, Mapping):
                continue
            identities = {
                str(value).strip().casefold()
                for key, value in row.items()
                if key.casefold() in _ZERO_SCORING_IDENTITY_KEYS
                and value is not None
            }
            if identities & names:
                rows.append(row)
    return rows

def _zero_gate_genuine_proof(rows: Sequence[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    active = False
    totals: list[Decimal | None] = []
    for row in rows:
        normalized = {str(key).casefold(): value for key, value in row.items()}
        for key in ("gp", "g", "games", "min", "mpg", "minutes"):
            if key in normalized:
                activity = decimal_value(normalized[key])
                if activity is not None and activity > 0:
                    active = True
        for key in ("pts", "points", "total_points"):
            if key in normalized:
                totals.append(decimal_value(normalized[key]))
    if not active or not totals:
        return False
    if any(total is None for total in totals):
        return False
    return all(total == 0 for total in totals if total is not None)

def _zero_scoring_gate_reasons(
    task: TaskSpec, claim: Claim,
    envelopes: Sequence[EvidenceEnvelope],
) -> list[str]:
    if not _ZERO_SCORING_RX.search(claim.text):
        return []
    if _ZERO_SCORING_DIFFERENCE_RX.search(claim.text):
        return []
    text = " ".join(claim.text.casefold().split())
    subjects: dict[tuple[str, str, str], str] = {}
    candidates = list(task.entities)
    candidates.extend(
        entity for envelope in envelopes for entity in envelope.entities)
    for entity in candidates:
        if entity.type != "player":
            continue
        key = (entity.type, str(entity.id).casefold(),
               str(entity.display_name).casefold())
        names = {part for part in key[1:] if part}
        if names and any(name in text for name in names):
            subjects.setdefault(key, entity.display_name)
    if not subjects:
        return []
    season = task.season.value if task.season else None
    when = f" in {season}" if season else ""
    reasons: list[str] = []
    for key, display in subjects.items():
        rows = _zero_gate_player_rows(envelopes, {part for part in key[1:] if part})
        if _zero_gate_genuine_proof(rows):
            continue
        if rows:
            detail = (f"cited evidence carries no explicit scoring totals "
                      f"for {display}; an average without totals cannot "
                      f"prove a scoreless line")
        else:
            detail = (f"cited evidence carries no scoring rows "
                      f"for {display}")
        reasons.append(
            f"Zero-guard: {display} is stated at 0.0 PPG{when}, but "
            f"{detail}; refusing to publish a missing-data zero")
    return reasons

def verify_mechanical(
    task: TaskSpec,
    draft: DraftReport,
    evidence: Sequence[EvidenceEnvelope],
    calculations: Sequence[Calculation] = (),
    allowed_constants: Iterable[int | float | Decimal | str] = (),
) -> VerificationReport:
    task = TaskSpec.model_validate(task.model_dump())
    draft = DraftReport.model_validate(draft.model_dump())
    evidence = [EvidenceEnvelope.model_validate(item.model_dump()) for item in evidence]
    calculations = [Calculation.model_validate(item.model_dump()) for item in calculations]
    try:
        index = EvidenceIndex(evidence)
    except ValueError as exc:
        return VerificationReport(
            status=VerificationStatus.REPAIR,
            claim_results=[ClaimResult(
                claim_index=i, supported=False,
                reasons=[f"invalid evidence set: {exc}"],
            ) for i in range(len(draft.claims))],
            repair_instructions=["Correct the evidence lineage before synthesis."],
        )

    calculation_map = {item.calculation_id: item for item in calculations}
    duplicate_calculations = len(calculation_map) != len(calculations)
    allowed_numbers = {
        number for value in allowed_constants for number in _canon_number(value)
    }
    results: list[ClaimResult] = []

    for claim_index, claim in enumerate(draft.claims):
        results.append(_claim_result(
            task, claim, claim_index, index, calculation_map, duplicate_calculations,
            allowed_numbers,
        ))

    failed = [result for result in results if not result.supported]
    claim_tokens = {
        token for claim in draft.claims for token in _number_tokens(claim.text)
    }
    unclaimed_tokens = [
        token for section in draft.sections for token in _number_tokens(section)
        if token not in claim_tokens
    ]
    report_repairs = _report_section_repairs(task, draft, evidence, unclaimed_tokens)
    repairs = [
        f"Repair claim {result.claim_index}: {'; '.join(result.reasons)}"
        for result in failed
    ]
    repairs.extend(report_repairs[:max(0, 128 - len(repairs))])
    repairs.extend(_termination_gate_repairs(
        task, draft, evidence)[:max(0, 128 - len(repairs))])
    repairs = list(dict.fromkeys(repairs))
    return VerificationReport(
        status=(VerificationStatus.REPAIR if repairs else VerificationStatus.PASS),
        claim_results=results,
        repair_instructions=repairs,
    )

def _claim_result(task, claim, claim_index, index, calculation_map,
                  duplicate_calculations, allowed_numbers) -> ClaimResult:
    reasons: list[str] = []
    try:
        cited = index.require(claim.evidence_ids)
    except KeyError as exc:
        cited = []
        reasons.append(str(exc))

    if claim.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED) and not cited:
        reasons.append("factual claim has no resolvable evidence")
    if claim.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED) and any(
        not any(True for _ in iter_values(envelope)) for envelope in cited
    ):
        reasons.append("factual claim cites evidence with no values")
    if claim.kind in (ClaimKind.OBSERVED, ClaimKind.DERIVED) and any(
        "source identity not declared by tool" in envelope.warnings
        for envelope in cited
    ):
        reasons.append("factual claim cites evidence without declared source identity")
    if duplicate_calculations:
        reasons.append("calculation ids must be unique")

    calculation_reasons, calculation_values = _calculation_reasons(
        claim, calculation_map, index
    )
    reasons.extend(calculation_reasons)
    supported_numbers = _numeric_values(cited) | calculation_values | allowed_numbers
    for envelope in cited:
        for qualifier in (envelope.qualification, envelope.coverage):
            if qualifier:
                for token in _number_tokens(qualifier):
                    supported_numbers.update(_canon_number(token))
    for raw in _number_tokens(claim.text):
        reason = _uncited_numeral_reason(
            raw, claim, cited, supported_numbers, calculation_values)
        if reason is not None:
            reasons.append(reason)

    for value in _claim_dates_supported(claim, cited):
        reasons.append(f"uncited date {value}")
    for value in _claim_seasons_supported(claim, cited):
        reasons.append(f"uncited season {value}")
    reasons.extend(_entity_reasons(task, claim, cited))
    reasons.extend(_row_entity_value_reasons(
        claim, cited, calculation_values))
    reasons.extend(_direction_reasons(claim, cited))
    reasons.extend(_scope_reasons(task, cited))
    reasons.extend(_mixed_source_reasons(claim, cited))
    reasons.extend(_cross_evidence_calculation_reasons(claim, cited))
    reasons.extend(_metric_unit_reasons(claim, cited))
    reasons.extend(_metric_identity_reasons(
        claim, cited, supported_numbers, calculation_values, allowed_numbers))
    reasons.extend(_qualification_coverage_reasons(claim, cited))
    reasons.extend(_record_completeness_reasons(claim, cited))
    reasons.extend(_zero_scoring_gate_reasons(task, claim, cited))

    unique_reasons = list(dict.fromkeys(reasons))
    return ClaimResult(
        claim_index=claim_index,
        supported=not unique_reasons,
        reasons=unique_reasons,
    )

def _uncited_numeral_reason(raw, claim, cited, supported_numbers,
                            calculation_values) -> str | None:
    if _DATE.fullmatch(raw) or _SEASON.fullmatch(raw):
        return None
    if (raw == "100" and "points_per_100_possessions" in {
            unit.casefold() for envelope in cited
            for unit in envelope.units.values()}
            and re.search(r"points?\s+per\s+100\s+possessions?",
                          claim.text, re.IGNORECASE)):
        return None
    if not (_canon_number(raw) & supported_numbers
            or (claim.kind == ClaimKind.DERIVED
                and claim.calculation_id
                and _matches_calculation_display(raw, calculation_values))):
        return f"uncited numeral {raw}"
    return None

def _report_section_repairs(task, draft, evidence, unclaimed_tokens) -> list[str]:
    report_repairs = []
    if _record_task_missing_record(task, draft, evidence):
        report_repairs.append(
            "State the best team's complete wins-losses record in W-L form.")
    report_repairs.extend(_missing_requested_metric_repairs(task, draft, evidence))
    if unclaimed_tokens:
        report_repairs.append(
            "Move factual section values into claims with evidence: "
            + ", ".join(dict.fromkeys(unclaimed_tokens))
        )
    return report_repairs

def _record_task_missing_record(task, draft, evidence) -> bool:
    record_task = bool(re.search(r"\brecord\b", " ".join(
        (task.goal, task.deliverable, *task.subquestions)), re.IGNORECASE))
    standings_rows = [
        row for envelope in evidence if envelope.capability == "standings"
        and isinstance(envelope.rows, list)
        for row in envelope.rows if isinstance(row, Mapping)
    ]
    if not record_task or not standings_rows:
        return False
    has_complete_record = any(
        re.search(r"\b\d+\s*[-–]\s*\d+\b", claim.text)
        or re.search(
            r"\b\d+\s+wins?\b.{0,32}?\b\d+\s+loss(?:es)?\b",
            claim.text, re.IGNORECASE,
        )
        for claim in draft.claims)
    return not has_complete_record

def _missing_requested_metric_repairs(task, draft, evidence) -> list[str]:
    repairs = []
    task_text = " ".join((task.goal, task.deliverable, *task.subquestions)).casefold()
    requested_metrics = {
        "TS_PCT": ("true shooting", "shooting efficiency", "efficiency"),
        "FG3_PCT": ("three-point", "three point", "shooting split", "shooting percentage"),
    }
    for metric, aliases in requested_metrics.items():
        if not any(alias in task_text for alias in aliases):
            continue
        values = []
        for envelope in evidence:
            for item in iter_values(envelope):
                path = str(getattr(item, "path", "")).upper()
                if path.rsplit(".", 1)[-1] == metric and item.value is not None:
                    values.append(item.value)
        if not values:
            continue
        claimed = _numeric_values([])
        for claim in draft.claims:
            for token in _number_tokens(claim.text):
                claimed.update(_canon_number(token))
        if not any(_canon_number(value) & claimed for value in values):
            label = metric.replace("_PCT", "").replace("_", " ").lower()
            repairs.append(
                f"State the requested {label} metric from admitted evidence.")
    return repairs

def _gate_tables(evidence: Sequence[EvidenceEnvelope]) -> list[dict]:
    tables: list[dict] = []
    for envelope in evidence:
        rows = envelope.rows
        if isinstance(rows, dict):
            rows = [rows]
        elif not isinstance(rows, list):
            rows = []
        meta = ({"qualification": envelope.qualification}
                if envelope.qualification else {})
        tables.append({
            "title": envelope.capability,
            "rows": rows,
            "meta": meta,
        })
    return tables

def _termination_gate_repairs(task: TaskSpec, draft: DraftReport,
                              evidence: Sequence[EvidenceEnvelope]) -> list[str]:
    tables = _gate_tables(evidence)
    gate_repairs: list[str] = []
    question_kind = task.subject_entity_type
    if question_kind in ("player", "team"):
        question = " ".join((task.goal, task.deliverable, *task.subquestions))
        for table in tables:
            if not verify_table_kind(question, table,
                                     question_kind=question_kind):
                gate_repairs.append(
                    f"Drop or replace the {table.get('title') or 'data'} table: "
                    f"it does not match the question's {question_kind} level.")
    answer_text = " ".join((*draft.sections,
                            *(claim.text for claim in draft.claims)))
    for violation in verify_minutes_qual(answer_text, tables):
        gate_repairs.append(
            "Minutes-qualify or drop this rate-stat claim: " + violation)
    return list(dict.fromkeys(gate_repairs))

def validate_semantic_report(value: str | bytes | Mapping[str, Any] |
                             VerificationReport) -> VerificationReport:
    if isinstance(value, VerificationReport):
        return value
    if isinstance(value, (str, bytes)):
        parsed = json.loads(value)
    else:
        parsed = dict(value)
    if not isinstance(parsed, dict):
        raise ValueError("semantic verifier must return one VerificationReport object")
    extra = set(parsed) - _SEMANTIC_KEYS
    if extra:
        raise ValueError(f"semantic verifier returned forbidden fields: {sorted(extra)}")
    try:
        return VerificationReport.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("invalid VerificationReport") from exc

def merge_verification_reports(mechanical: VerificationReport,
                               semantic: VerificationReport) -> VerificationReport:
    statuses = {mechanical.status, semantic.status}
    if VerificationStatus.REPAIR in statuses:
        status = VerificationStatus.REPAIR
    elif VerificationStatus.PARTIAL in statuses:
        status = VerificationStatus.PARTIAL
    else:
        status = VerificationStatus.PASS
    by_claim = {result.claim_index: result for result in mechanical.claim_results}
    for result in semantic.claim_results:
        current = by_claim.get(result.claim_index)
        if current is None:
            by_claim[result.claim_index] = result
        else:
            by_claim[result.claim_index] = ClaimResult(
                claim_index=result.claim_index,
                supported=current.supported and result.supported,
                reasons=list(dict.fromkeys(current.reasons + result.reasons)),
                evidence_spans=list(dict.fromkeys(
                    current.evidence_spans + result.evidence_spans))[:32],
                uncertain=current.uncertain or result.uncertain,
            )
    return VerificationReport(
        status=status,
        claim_results=[by_claim[index] for index in sorted(by_claim)],
        missing_branches=list(dict.fromkeys(
            mechanical.missing_branches + semantic.missing_branches
        )),
        contradictions=list(dict.fromkeys(
            mechanical.contradictions + semantic.contradictions
        )),
        repair_instructions=list(dict.fromkeys(
            mechanical.repair_instructions + semantic.repair_instructions
        )),
    )

_GATE_TEAM_TABLE_RX = re.compile(
    r"team splits|team totals|standings|four factors|matchup splits",
    re.IGNORECASE,
)

_MINUTES_RATE_CLAIM_RX = re.compile(
    r"\d+\.?\d*\s*(?:SPG|BPG|PPG|RPG|APG|TS ?%|3P ?%|FG ?%|eFG ?%)"
    r"|\d+\.?\d*\s*%\s*(?:TS|3P|FG|eFG)\b",
    re.IGNORECASE,
)

_MINUTES_LEAD_RX = re.compile(
    r"leads?( the)? league in \w+",
    re.IGNORECASE,
)

_MINUTES_QUAL_RX = re.compile(
    r"\bminutes?\b|\bmin\b|\bmpg\b",
    re.IGNORECASE,
)

_UNIT_SPLIT_RX = re.compile(r"((?<=[.!?])\s+|\n+)")

_ZERO_SCORING_RX = re.compile(
    r"(?<![\d.])0(?:\.0+)?\s*(?:PPG|points?\s+per\s+game)\b",
    re.IGNORECASE)
_ZERO_SCORING_DIFFERENCE_RX = re.compile(
    r"\b(?:difference|margin|gap|delta|lead(?:s|ing)?|trail(?:s|ing)?|"
    r"versus|compared?)\b|\bvs\.?\b|\bby\s+how\s+much\b",
    re.IGNORECASE)
_ZERO_SCORING_IDENTITY_KEYS = frozenset({
    "team", "team_name", "team_abbreviation", "abbrev",
    "player", "player_name", "full_name", "name",
})

def _iter_units(text: str):
    parts = _UNIT_SPLIT_RX.split(text or "")
    for i in range(0, len(parts), 2):
        yield parts[i], (parts[i + 1] if i + 1 < len(parts) else "")

def _gate_question_kind(question: str,
                       detect=None) -> str:
    try:
        found_p, found_t = detect(question or "") if detect else ([], [])
    except Exception:
        found_p, found_t = [], []
    if found_p and not found_t:
        return "player"
    if found_t and not found_p:
        return "team"
    if found_p and found_t:
        return "mixed"
    return "other"

def _gate_table_level(table: dict) -> str:
    rows = table.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        keys = {str(k).upper() for k in rows[0].keys()}
        if "PLAYER" in keys or "PLAYER_NAME" in keys:
            return "player"
        if "TEAM" in keys:
            return "team"
    if _GATE_TEAM_TABLE_RX.search(str(table.get("title") or "")):
        return "team"
    return "unknown"

def verify_table_kind(question: str, table: dict,
                      question_kind: str | None = None) -> bool:
    kind = question_kind if question_kind in ("player", "team") \
        else _gate_question_kind(question)
    if kind not in ("player", "team"):
        return True
    try:
        level = _gate_table_level(table)
    except Exception:
        return True
    if level not in ("player", "team"):
        return True
    return kind == level

def verify_minutes_qual(answer_text: str, tables: list) -> list[str]:
    try:
        _answer_has_qual = bool(_MINUTES_QUAL_RX.search(answer_text or ""))
    except Exception:
        _answer_has_qual = False
    _table_has_qual = _tables_have_minutes_qual(tables)
    if _answer_has_qual or _table_has_qual:
        return []
    violations: list[str] = []
    try:
        units = list(_iter_units(answer_text or ""))
    except Exception:
        return []
    for _sent, _ in units:
        _s = (_sent or "").strip()
        if not _s:
            continue
        if (_MINUTES_RATE_CLAIM_RX.search(_s)
                or _MINUTES_LEAD_RX.search(_s)):
            if not _MINUTES_QUAL_RX.search(_s):
                violations.append(_s)
    return violations

def _tables_have_minutes_qual(tables) -> bool:
    try:
        for _t in (tables or []):
            try:
                if not isinstance(_t, dict):
                    continue
                _meta = _t.get("meta")
                if (isinstance(_meta, dict)
                        and _MINUTES_QUAL_RX.search(str(_meta.get("qualification") or ""))):
                    return True
                _rows = _t.get("rows")
                if isinstance(_rows, list):
                    for _r in _rows:
                        try:
                            if isinstance(_r, dict) and any(
                                str(_k).strip().upper() in ("MIN", "MPG", "MINUTES")
                                for _k in _r.keys()
                            ):
                                return True
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception:
        return False
    return False
