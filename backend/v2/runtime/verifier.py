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
)
from v2.domain.calculations import Calculation, validate_calculation
from v2.domain.evidence import EvidenceIndex, decimal_value, iter_values

_NUMBER = re.compile(
    # Hyphenated lexical labels such as "3-point" and "5-man" name a
    # metric or lineup shape; their digits are not asserted measurements.
    # Date/season alternatives remain first so 2025-26 is still one token.
    r"(?<![A-Za-z0-9])(?:\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|[-+]?\$?\d[\d,]*(?:\.\d+)?(?:%|[KMB])?)(?![A-Za-z0-9]|-[A-Za-z])",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SEASON = re.compile(r"\b\d{4}-\d{2}\b(?!-\d{2})")
_RANK = re.compile(r"(?:#\s*(\d+)|\b(\d+)(?:st|nd|rd|th)\b)", re.IGNORECASE)
_LIST_LABEL = re.compile(r"(?m)^\s*(\d+)\.\s")
_SEMANTIC_KEYS = {
    "status", "claim_results", "missing_branches", "contradictions",
    "repair_instructions",
}

class SemanticVerifier(Protocol):
    async def verify(self, task: TaskSpec, draft: DraftReport,
                     evidence: Sequence[EvidenceEnvelope]) -> VerificationReport: ...


def _canon_number(raw: Any) -> set[Decimal]:
    value = decimal_value(raw)
    if value is None:
        return set()
    values = {value}
    text = str(raw).strip()
    if text.endswith("%"):
        values.add(value / 100)
    elif text[-1:].upper() in {"K", "M", "B"}:
        compact = decimal_value(text[:-1])
        if compact is not None:
            values.add(compact * {"K": 1_000, "M": 1_000_000,
                                  "B": 1_000_000_000}[text[-1].upper()])
    elif abs(value) <= 1:
        values.add(value * 100)
    return values


def _number_tokens(text: str) -> list[str]:
    label_numbers = {match.start(1) for match in _LIST_LABEL.finditer(text)}
    return [match.group(0) for match in _NUMBER.finditer(text)
            if match.start() not in label_numbers]


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
        for item in iter_values(envelope):
            values.update(_canon_number(item.value))
            if isinstance(item.value, str):
                for token in _number_tokens(item.value):
                    values.update(_canon_number(token))
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
    try:
        from app.tools._core import coerce_team_id
        from app.tools.player import coerce_player_id
        resolver = {"team": coerce_team_id, "player": coerce_player_id}.get(entity.type)
        if resolver is not None:
            for candidate in (entity.id, entity.display_name):
                try:
                    return (entity.type, str(resolver(candidate)))
                except (TypeError, ValueError):
                    continue
    except ImportError:
        pass
    normalized = " ".join(
        entity.id.casefold().replace("-", " ").replace("_", " ").split())
    return (entity.type, normalized)


def _entity_reasons(task: TaskSpec, claim: Claim,
                    envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    text = claim.text.casefold()
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
        if entity.display_name.casefold() not in text and entity.id.casefold() not in text:
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
    """Bind claim numerals to named-entity rows across cited evidence.

    A claim may legitimately cite several population envelopes for different
    metrics on the same entity. Test against the union of matching entity rows,
    never against an unrelated adjacent row and never require every envelope to
    repeat every cited metric.
    """
    text = " ".join(claim.text.casefold().split())
    identity_keys = {
        "team", "team_name", "team_abbreviation", "abbrev",
        "player", "player_name", "full_name", "name",
    }
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
    if not matched_envelopes:
        return []
    row_numbers = _numeric_values(matched_envelopes) | (calculation_values or set())
    unsupported = []
    for raw in _number_tokens(claim.text):
        if _DATE.fullmatch(raw) or _SEASON.fullmatch(raw) or raw == "100":
            continue
        if not (_canon_number(raw) & row_numbers):
            unsupported.append(raw)
    if unsupported:
        return [
            "claim numerals do not match the named entity rows: "
            + ", ".join(unsupported)
        ]
    return []


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
    return reasons


def _metric_unit_reasons(claim: Claim,
                         envelopes: Sequence[EvidenceEnvelope]) -> list[str]:
    reasons: list[str] = []
    text = claim.text.casefold()
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
            metric_words = metric.casefold().replace("_", " ")
            if len(metric_words) < 3 or metric_words not in text:
                continue
            unit_name = unit.casefold()
            percent_shown = "%" in claim.text or "percent" in text
            if unit_name in {"percent", "percent_0_100", "fraction_0_1"}:
                if not percent_shown:
                    reasons.append(f"metric {metric} is stated without a percent unit")
            elif unit_name == "points_per_100_possessions":
                if not re.search(r"points?\s+per\s+100\s+possessions?", text):
                    reasons.append(
                        f"metric {metric} is stated without its declared unit {unit}")
            elif unit_name == "count":
                # Count is dimensionless. Natural metric nouns such as wins,
                # losses, games, and points already carry the measure; forcing
                # the literal word "count" creates broken answer prose.
                continue
            elif unit_name.replace("_", " ") not in text:
                reasons.append(f"metric {metric} is stated without its declared unit {unit}")
    return reasons


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
    """A best-record claim must publish the complete W-L record.

    Win percentage and wins alone can identify the row, but omitting losses
    makes the answer incomplete and can hide a mismatched denominator. This
    check is schema-driven and applies to any standings-like row carrying both
    wins and losses.
    """
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
    if not any(
        (_canon_number(wins) & _canon_number(raw_wins))
        and (_canon_number(losses) & _canon_number(raw_losses))
        for wins, losses in matching_rows
        for raw_wins, raw_losses in re.findall(r"(\d+)\s*[-–]\s*(\d+)", claim.text)
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
    """Require declared calculations for comparisons assembled across envelopes."""
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
            if _DATE.fullmatch(raw) or _SEASON.fullmatch(raw):
                continue
            if (raw == "100" and "points_per_100_possessions" in {
                    unit.casefold() for envelope in cited
                    for unit in envelope.units.values()}
                    and re.search(r"points?\s+per\s+100\s+possessions?",
                                  claim.text, re.IGNORECASE)):
                continue
            if not (_canon_number(raw) & supported_numbers):
                reasons.append(f"uncited numeral {raw}")

        for value in _claim_dates_supported(claim, cited):
            reasons.append(f"uncited date {value}")
        for value in _claim_seasons_supported(claim, cited):
            reasons.append(f"uncited season {value}")
        reasons.extend(_entity_reasons(task, claim, cited))
        reasons.extend(_row_entity_value_reasons(
            claim, cited, calculation_values))
        reasons.extend(_scope_reasons(task, cited))
        reasons.extend(_mixed_source_reasons(claim, cited))
        reasons.extend(_cross_evidence_calculation_reasons(claim, cited))
        reasons.extend(_metric_unit_reasons(claim, cited))
        reasons.extend(_qualification_coverage_reasons(claim, cited))
        reasons.extend(_record_completeness_reasons(claim, cited))

        unique_reasons = list(dict.fromkeys(reasons))
        results.append(ClaimResult(
            claim_index=claim_index,
            supported=not unique_reasons,
            reasons=unique_reasons,
        ))

    failed = [result for result in results if not result.supported]
    claim_tokens = {
        token for claim in draft.claims for token in _number_tokens(claim.text)
    }
    unclaimed_tokens = [
        token for section in draft.sections for token in _number_tokens(section)
        if token not in claim_tokens
    ]
    report_repairs = []
    # A record deliverable backed by standings is incomplete unless the final
    # report prints wins and losses together. Checking across the report (not
    # only inside a single superlative claim) catches the common split shape:
    # "best record" followed by wins and win percentage but no losses.
    record_task = bool(re.search(r"\brecord\b", " ".join(
        (task.goal, task.deliverable, *task.subquestions)), re.IGNORECASE))
    standings_rows = [
        row for envelope in evidence if envelope.capability == "standings"
        and isinstance(envelope.rows, list)
        for row in envelope.rows if isinstance(row, Mapping)
    ]
    if record_task and standings_rows:
        has_complete_record = any(re.search(
            r"\b\d+\s*[-–]\s*\d+\b", claim.text)
            for claim in draft.claims)
        if not has_complete_record:
            report_repairs.append(
                "State the best team's complete wins-losses record in W-L form.")
    # Requested metrics that exist in admitted evidence are deliverable
    # requirements, not optional detail. Keep this as metric vocabulary rather
    # than query/entity cases, and compare against the exact admitted value.
    task_text = " ".join((task.goal, task.deliverable, *task.subquestions)).casefold()
    requested_metrics = {
        "TS_PCT": ("true shooting", "shooting efficiency", "efficiency"),
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
            report_repairs.append(
                f"State the requested {label} metric from admitted evidence.")
    if unclaimed_tokens:
        report_repairs.append(
            "Move factual section values into claims with evidence: "
            + ", ".join(dict.fromkeys(unclaimed_tokens))
        )
    repairs = [
        f"Repair claim {result.claim_index}: {'; '.join(result.reasons)}"
        for result in failed
    ]
    repairs.extend(report_repairs[:max(0, 128 - len(repairs))])
    return VerificationReport(
        status=(VerificationStatus.REPAIR if repairs else VerificationStatus.PASS),
        claim_results=results,
        repair_instructions=repairs,
    )


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
