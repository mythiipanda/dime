"""Presentation of typed runtime results for the standalone runtime CLI."""
from __future__ import annotations
import json
import logging
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

def _output_line(result, status) -> str:
    binding = status.binding
    if binding.requirement_kind == "calculation":
        calculation = next(item for item in result.draft.calculations
                           if item.calculation_id == binding.calculation_id)
        value = str(calculation.result)
        unit = calculation.unit or "unitless"
        subject = ""
    else:
        raw = binding.value
        value = ("true" if raw.value else "false") if raw.kind == "boolean" else str(raw.value)
        unit = (binding.unit.value if binding.unit.kind == "declared" else "unitless")
        subject = (f" [{binding.subject_entity_type}:{binding.subject_entity_id}]"
                   if binding.subject_entity_id is not None else "")
    return f"{status.output_id}{subject} = {value} ({unit})"

LIVE_SOURCE_NAMES = {
    "nba_api": "the NBA's live feed",
    "basketball_reference": "Basketball Reference",
    "espn": "ESPN",
}

LIVE_SOURCE_LINES = {
    "live_only": ("These figures came from {sources}{when}, not from the figures "
                  "I had saved, so they can differ from numbers you saw earlier."),
    "mixed": ("Some of these figures were refreshed from {sources}{when}; the "
              "rest came from the figures I had saved."),
}

UNTRACED_SUFFIX = " could not be traced to the source data."

def _live_source_line(result) -> str | None:
    sources: set[str] = set()
    from_saved_figures = False
    as_of = None
    for envelope in result.execution.evidence:
        identity = envelope.source_identity
        if identity is None:
            continue
        if identity.kind == "live":
            sources.add(identity.source)
        else:
            from_saved_figures = True
            if identity.kind == "composite":
                sources.update(identity.live_sources)
        if envelope.as_of is not None and (as_of is None or envelope.as_of > as_of):
            as_of = envelope.as_of
    if not sources:
        return None
    names = [name for source, name in LIVE_SOURCE_NAMES.items() if source in sources]
    names += sorted(sources - LIVE_SOURCE_NAMES.keys())
    story = "mixed" if from_saved_figures else "live_only"
    return LIVE_SOURCE_LINES[story].format(
        sources=", ".join(names), when=f" on {as_of}" if as_of else "")

def _claim_prose(result) -> list[str]:
    from v2.runtime.models import withheld_claim_indices

    withheld = withheld_claim_indices(result.gaps)
    claims = [item for item in result.verified_claims
              if item.claim_index not in withheld]
    if not claims:
        return []
    internal = _internal_identifier_rx(result)
    lines: list[str] = []
    for item in claims:
        prose = _publishable_claim_prose(result, item, internal)
        if prose is None:
            lines.extend(_label_lines(result, item.claim.output_bindings))
            sources = sorted(_claim_source_labels(result, item))
            if sources:
                lines.append(f"Source: {', '.join(sources)}.")
        else:
            lines.append(prose)
    return list(dict.fromkeys(lines))

_SCRUB_REFERRAL = "the data"
_SCRUB_COVERAGE_LIMIT = 0.6
_PROSE_NUMBER_RX = re.compile(
    r"(?<![\w.])[-+]?(?:(?:\d{1,3}(?:,\d{3})+)|\d+)"
    r"(?:\.\d+)?(?:[eE][+-]?\d+)?%?(?![\w]|\.\d)")
_WAREHOUSE_SOURCE_RX = re.compile(
    r"^v1:([a-z][a-z0-9_]*):warehouse:([a-z][a-z0-9_]*)$")

_PROSE_SCRUB_RULES: tuple[
    tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    (re.compile(
        r"\[[a-z_]{2,20}:\s*(?=[A-Za-z0-9_.\-]*\d)[A-Za-z0-9_.\-]{1,64}\]",
        re.IGNORECASE), ""),
    (re.compile(
        r"\b(?:player|team|game|league)\s+id\s*[:=#]?\s*"
        r"[A-Za-z0-9_.\-]{1,64}\b",
        re.IGNORECASE), ""),
    (re.compile(
        r"\b(?:evidence|evidence_id|node|node_id|claim|claim_index|"
        r"requirement|requirement_id|calculation|calculation_id|capability|"
        r"selector|row_selector|subject_selector|resolve|row-scan|"
        r"web_search|web_fetch)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9_.:\-]{1,96}[\"']?"), _SCRUB_REFERRAL),
    (re.compile(
        r"\b(?:player|player_id|team|team_id|entity|entity_id|subject|"
        r"subject_id|output|output_id|domain)\b"
        r"\s*=\s*[\"']?[A-Za-z0-9_.:\-]{1,96}[\"']?"), _SCRUB_REFERRAL),
    (re.compile(
        r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\s*:\s*[A-Za-z0-9_.\-]{1,96}\b",
        re.IGNORECASE), _SCRUB_REFERRAL),
    (re.compile(
        r"\b[a-z][a-z0-9_]{1,20}\s*:\s*"
        r"(?=[A-Za-z0-9_.\-]*(?:[_\-.][A-Za-z0-9_.\-]*|[0-9]{3,}))"
        r"[A-Za-z0-9_.\-]{1,96}\b"), _SCRUB_REFERRAL),
    (re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", re.IGNORECASE),
     _SCRUB_REFERRAL),
    (re.compile(
        r"\b(?:rows?|lines?|columns?|cells?|season_line|matches|meta|values)\b"
        r"(?:\s*\[\s*\d*\s*\]|\s*\[\s*\]|\.[A-Za-z_][A-Za-z0-9_]*)+",
        re.IGNORECASE), _SCRUB_REFERRAL),
)

_PROSE_TIDY_RULES: tuple[tuple["re.Pattern[str]", str], ...] = (
    (re.compile(r"\bfrom\s+the data\b", re.IGNORECASE), ""),
    (re.compile(r"\bthe data(?:\s*[,;]\s*the data)+\b", re.IGNORECASE), ""),
    (re.compile(r"[(\[{]\s*the data\s*[)\]}]", re.IGNORECASE), ""),
    (re.compile(r"\(\s*\)"), ""),
    (re.compile(r"\bthe the\b", re.IGNORECASE), "the"),
    (re.compile(r" +([.,;:!?])"), r"\1"),
    (re.compile(r"[ \t]{2,}"), " "),
)

_PROSE_EDGE_RX = re.compile(r"^[\s,;:.\-]+|[\s,;:\-]+$")

_IDENTIFIER_SHAPE_RX = re.compile(r"[_\-.:\d]")
_BINDING_INTERNAL_FIELDS = (
    "evidence_id", "node_id", "selector", "row_selector", "subject_selector",
    "subject_entity_id", "requirement_id", "calculation_id", "domain")

def _internal_identifiers(result) -> set[str]:
    identifiers = {envelope.evidence_id for envelope in result.execution.evidence}
    identifiers |= {envelope.capability for envelope in result.execution.evidence}
    identifiers |= {node.id for node in result.execution.plan.nodes}
    for item in result.verified_claims:
        identifiers |= set(item.claim.evidence_ids)
        if item.claim.calculation_id is not None:
            identifiers.add(item.claim.calculation_id)
        for binding in item.claim.output_bindings:
            identifiers |= {
                getattr(binding, field) for field in _BINDING_INTERNAL_FIELDS
                if getattr(binding, field, None) is not None}
    return {value for value in identifiers if _IDENTIFIER_SHAPE_RX.search(value)}

def _internal_identifier_rx(result) -> "re.Pattern[str] | None":
    identifiers = sorted(_internal_identifiers(result), key=len, reverse=True)
    if not identifiers:
        return None
    return re.compile("|".join(
        rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])"
        for value in identifiers))

def _decimal_literal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").removesuffix("%"))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None

def _calculation_input_numbers(calculation, evidence) -> set[Decimal]:
    from v2.domain.evidence import iter_values

    values: set[Decimal] = set()
    for input_ in calculation.inputs:
        envelope = evidence.get(input_.evidence_id)
        if envelope is None:
            continue
        for item in iter_values(envelope):
            if item.path != input_.path:
                continue
            number = _decimal_literal(item.value)
            if number is not None:
                values.add(number)
    return values


def _claim_numbers(result, verified_claim) -> set[Decimal]:
    from v2.contracts import EvidenceOutputBinding

    calculations = {
        item.calculation_id: item
        for item in getattr(getattr(result, "draft", None), "calculations", [])
    }
    evidence = {
        item.evidence_id: item
        for item in getattr(getattr(result, "execution", None), "evidence", []) or []
    }
    values: set[Decimal] = set()
    for status in getattr(result, "output_statuses", []) or []:
        if (status.status != "complete"
                or status.claim_index != verified_claim.claim_index
                or status.binding is None):
            continue
        binding = status.binding
        if isinstance(binding, EvidenceOutputBinding):
            if binding.value.kind not in {"integer", "float", "decimal"}:
                continue
            raw = binding.value.value
        else:
            calculation = calculations.get(binding.calculation_id)
            if (calculation is None
                    or calculation.requirement_id != binding.requirement_id
                    or verified_claim.claim.calculation_id != binding.calculation_id):
                continue
            raw = calculation.result
            values |= _calculation_input_numbers(calculation, evidence)
        number = _decimal_literal(raw)
        if number is not None:
            values.add(number)
    return values

def _warehouse_source_table(source: str, capability_id: str) -> str | None:
    from v2.adapters import CAPABILITIES

    match = _WAREHOUSE_SOURCE_RX.fullmatch(source)
    capability = CAPABILITIES.get(capability_id)
    if (match is None or capability is None
            or match.group(1) != capability.tool_name):
        return None
    return match.group(2).casefold()

def _claim_source_labels(result, verified_claim) -> set[str]:
    from v2.contracts import EvidenceOutputBinding

    bound_evidence_ids = {
        binding.evidence_id
        for binding in verified_claim.claim.output_bindings
        if isinstance(binding, EvidenceOutputBinding)
    }
    if not bound_evidence_ids:
        return set()
    evidence = {
        item.evidence_id: item
        for item in getattr(getattr(result, "execution", None), "evidence", []) or []
    }
    labels: set[str] = set()
    for source in verified_claim.sources:
        if source.evidence_id not in bound_evidence_ids:
            continue
        envelope = evidence.get(source.evidence_id)
        if (envelope is None or source.source != envelope.source
                or source.capability != envelope.capability):
            continue
        identity = getattr(envelope, "source_identity", None)
        if getattr(identity, "kind", None) != "warehouse":
            continue
        table = _warehouse_source_table(source.source, source.capability)
        if table is not None:
            labels.add(table)
    return labels

def _claim_numbers_are_admitted(
        result, verified_claim, internal: re.Pattern[str] | None) -> bool:
    text = verified_claim.claim.text
    if internal is not None:
        text = internal.sub("", text)
    season = getattr(getattr(result, "task", None), "season", None)
    season_value = getattr(season, "value", season)
    if isinstance(season_value, str) and season_value:
        text = re.sub(
            rf"(?<!\d){re.escape(season_value)}(?!\d)", "", text)
    allowed = _claim_numbers(result, verified_claim)
    return all(
        (number := _decimal_literal(match.group(0))) is not None
        and number in allowed
        for match in _PROSE_NUMBER_RX.finditer(text))

def _publishable_claim_prose(
        result, verified_claim, internal: re.Pattern[str] | None) -> str | None:
    has_complete_binding = any(
        status.status == "complete"
        and status.claim_index == verified_claim.claim_index
        for status in getattr(result, "output_statuses", []) or [])
    if (has_complete_binding
            and not _claim_numbers_are_admitted(result, verified_claim, internal)):
        return None
    prose = _publishable_prose(verified_claim.claim.text, internal)
    if prose is None:
        return None
    sources = sorted(_claim_source_labels(result, verified_claim))
    if sources:
        prose += f" Source: {', '.join(sources)}."
    return prose

def _publishable_prose(
        text: str, internal: re.Pattern[str] | None) -> str | None:
    original = text
    covered = 0
    for pattern, replacement in _PROSE_SCRUB_RULES:
        covered += sum(len(match.group(0))
                       for match in pattern.finditer(text))
        text = pattern.sub(replacement, text)
    for pattern, replacement in _PROSE_TIDY_RULES:
        text = pattern.sub(replacement, text)
    text = _PROSE_EDGE_RX.sub("", text)
    if text[:1].islower():
        text = text[:1].upper() + text[1:]
    if not text or covered >= _SCRUB_COVERAGE_LIMIT * len(original):
        return None
    if internal is not None and internal.search(text):
        return None
    return text

def _label_lines(result, bindings) -> list[str]:
    keys = {(binding.requirement_kind, binding.requirement_id,
             binding.output_id) for binding in bindings}
    return [_output_line(result, status) for status in result.output_statuses
            if status.status == "complete"
            and (status.requirement_kind, status.requirement_id,
                 status.output_id) in keys]

def _binding_output_ids(bindings) -> set[str]:
    covered: set[str] = set()
    for binding in bindings or []:
        output_id = getattr(binding, "output_id", None)
        if isinstance(output_id, str) and output_id:
            covered.add(output_id)
    return covered

def _prose_covered_output_ids(result) -> set[str]:
    from v2.runtime.models import withheld_claim_indices
    verified = list(getattr(result, "verified_claims", None) or [])
    if not verified:
        return set()
    try:
        withheld = withheld_claim_indices(getattr(result, "gaps", None) or [])
    except Exception:
        withheld = set()
    try:
        internal = _internal_identifier_rx(result)
    except Exception:
        internal = None
    draft_claims = list(
        getattr(getattr(result, "draft", None), "claims", None) or [])
    covered: set[str] = set()
    for item in verified:
        index = getattr(item, "claim_index", None)
        if index in withheld:
            continue
        claim = getattr(item, "claim", None)
        text = getattr(claim, "text", None)
        if not isinstance(text, str) or not text:
            continue
        try:
            prose = _publishable_claim_prose(result, item, internal)
        except Exception:
            continue
        if prose is None:
            continue
        covered |= _binding_output_ids(getattr(claim, "output_bindings", None))
        covered |= _binding_output_ids(getattr(item, "output_bindings", None))
        if isinstance(index, int) and 0 <= index < len(draft_claims):
            covered |= _binding_output_ids(
                getattr(draft_claims[index], "output_bindings", None))
    return covered

def _gap_kinds(result) -> list[str]:
    kinds = []
    for gap in result.gaps:
        if gap.kind.value not in kinds:
            kinds.append(gap.kind.value)
    try:
        from v2.runtime.loop import JUDGE_UNAVAILABLE_BRANCHES as _judge_branches
    except Exception:
        _judge_branches = frozenset()
    if any(getattr(gap, "message", None) in _judge_branches
           for gap in result.gaps) and "judge_unavailable" not in kinds:
        kinds.append("judge_unavailable")
    return kinds

_GAP_MESSAGES = {
    "source_conflict": "Available sources conflict for some requested outputs.",
    "unsupported_claim": "Some requested outputs were not supported.",
    "execution_failure": "Some requested data was unavailable.",
    "provider_error": "The model provider is unavailable.",
    "synthesis_incomplete": "Some requested outputs could not be published.",
    "judge_unavailable": "I couldn't double-check this answer, so treat the details with extra care.",
}

def _gap_lines(result, kinds, all_complete, fully_covered, unverified_output_ids) -> list[str]:
    lines: list[str] = []
    for kind in kinds:
        if kind == "missing_evidence" and all_complete:
            continue
        if kind in ("missing_evidence", "synthesis_incomplete") and fully_covered:
            continue
        if kind == "missing_evidence":
            if unverified_output_ids:
                lines.append(
                    "Some requested outputs could not be verified: "
                    + ", ".join(unverified_output_ids) + ".")
            else:
                lines.extend(
                    gap.message for gap in result.gaps
                    if gap.kind.value == "missing_evidence")
            continue
        lines.append(_GAP_MESSAGES[kind])
    return lines

def _answer_text(result) -> str:
    published = {
        item.output_id for item in result.output_statuses
        if item.status == "complete"
    }
    stated = _prose_covered_output_ids(result)
    lines = _claim_prose(result) or list(dict.fromkeys(
        _output_line(result, item) for item in result.output_statuses
        if item.status == "complete"))
    source_line = _live_source_line(result)
    if source_line is not None:
        lines.append(source_line)
    kinds = _gap_kinds(result)
    all_complete = bool(result.output_statuses) and all(
        item.status == "complete" for item in result.output_statuses)
    requested_ids = {item.output_id for item in result.output_statuses}
    fully_covered = bool(result.output_statuses) and requested_ids <= (published | stated)
    unverified_output_ids = [
        item.output_id for item in result.output_statuses
        if item.status != "complete" and item.output_id not in published
        and item.output_id not in stated]
    lines += _gap_lines(result, kinds, all_complete, fully_covered, unverified_output_ids)
    lines += list(dict.fromkeys(
        f"{item.output_id} could not be verified ({item.status})."
        for item in result.output_statuses
        if item.status != "complete" and item.output_id not in published
        and item.output_id not in stated))
    return "\n".join(lines) or "I could not verify a publishable answer from the available data."

def _output_display_name(output_id: str, definitions=None) -> str:
    definition = (definitions or {}).get(output_id)
    if definition:
        head = definition.split(":", 1)[0].strip()
        if head and len(head) <= 64:
            return head
    humanized = output_id.replace("_", " ").strip()
    if humanized and humanized == humanized.lower():
        return humanized.upper()
    return humanized or output_id


def _evidence_envelope(result, evidence_id: str | None):
    try:
        for item in result.execution.evidence:
            if getattr(item, "evidence_id", None) == evidence_id:
                return item
    except Exception:
        return None
    return None


def _envelope_definitions(result, evidence_id: str) -> dict:
    envelope = _evidence_envelope(result, evidence_id)
    if envelope is None:
        return {}
    return dict(getattr(envelope, "metric_definitions", None) or {})


def _subject_display_name(binding, envelope) -> str:
    subject_type = getattr(binding, "subject_entity_type", None)
    subject_id = getattr(binding, "subject_entity_id", None)
    if envelope is None or subject_type is None or subject_id is None:
        return ""
    try:
        entities = getattr(envelope, "entities", None) or []
    except Exception:
        return ""
    for entity in entities:
        if (getattr(entity, "type", None) == subject_type
                and str(getattr(entity, "id", "")) == str(subject_id)):
            return str(getattr(entity, "display_name", None) or "").strip()
    return ""


def _public_gaps(result) -> list[dict]:
    return [{"kind": gap.kind.value, "blocks": list(gap.blocks)}
            for gap in result.gaps]

def _status_subject(task) -> tuple[str, str]:
    entities = getattr(task, "entities", None) or []
    names: list[str] = []
    for entity in list(entities)[:2]:
        name = str(getattr(entity, "display_name", None)
                   or getattr(entity, "id", "") or "").strip()
        if name:
            names.append(name)
    season_obj = getattr(task, "season", None)
    season = getattr(season_obj, "value", season_obj)
    season = str(season).strip() if isinstance(season, str) and str(season).strip() else ""
    if names:
        base = " and ".join(names)
        return (base[:80], season)
    phrases: list[str] = []
    for req in getattr(task, "requirements", None) or []:
        desc = str(getattr(req, "description", "") or "").strip()
        if desc:
            phrases.append(" ".join(desc.split()[:5]))
    topic = phrases[0] if phrases else ""
    if not topic:
        goal = str(getattr(task, "goal", "") or "")
        stop = {"who", "what", "which", "when", "where", "how", "led", "lead",
                "leads", "league", "the", "a", "an", "in", "for", "of", "is",
                "are", "was", "were", "top", "list", "show", "give", "tell",
                "me", "please", "find", "get", "name"}
        words = [w.strip("?.,;:!") for w in goal.split()]
        kept = [w for w in words if w and w.lower() not in stop]
        topic = " ".join((kept or words)[:5]).strip()
    if not topic:
        topic = "the numbers"
    return (topic[:80], season)

def _status_lines(task) -> list[str]:
    if task is None:
        return []
    base_raw, season_raw = _status_subject(task)
    base = base_raw.strip()
    season = season_raw.strip()
    lines: list[str] = []
    if base:
        if season and season not in base:
            subject = f"{base} for {season}"[:80].strip()
        else:
            subject = base[:80].strip()
        lines.append(f"Checking {subject}…")
        if season and season not in base:
            lines.append(f"Comparing {base} across {season}…")
        else:
            lines.append(f"Comparing {base}…")
    lines.append("Verifying every number…")
    deduped: list[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped[:3]

def _public_output_status(result, status) -> dict:
    item = {"requirement_kind": status.requirement_kind,
            "requirement_id": status.requirement_id,
            "output_id": status.output_id, "status": status.status}
    if status.status == "complete":
        binding = status.binding
        if binding.requirement_kind == "calculation":
            calculation = next(x for x in result.draft.calculations
                               if x.calculation_id == binding.calculation_id)
            item.update(value=str(calculation.result),
                        unit=calculation.unit or "unitless",
                        display_name=_output_display_name(status.output_id))
        else:
            item.update(value=("true" if binding.value.kind == "boolean" and binding.value.value
                               else "false" if binding.value.kind == "boolean"
                               else str(binding.value.value)),
                        unit=(binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                        subject_type=binding.subject_entity_type,
                        subject_id=binding.subject_entity_id,
                        subject_display_name=_subject_display_name(
                            binding, _evidence_envelope(
                                result, binding.evidence_id)),
                        display_name=_output_display_name(
                            status.output_id,
                            _envelope_definitions(result, binding.evidence_id)))
    return item

def _citation_provenance(envelope) -> dict:
    identity = envelope.source_identity
    if identity is None:
        origin, live_sources, warehouse_id = "undeclared", [], None
    elif identity.kind == "live":
        origin, live_sources, warehouse_id = "live", [identity.source], None
    elif identity.kind == "composite":
        origin, live_sources = "mixed", list(identity.live_sources)
        warehouse_id = identity.warehouse_id
    else:
        origin, live_sources, warehouse_id = "warehouse", [], identity.warehouse_id
    return {"capability": envelope.capability,
            "origin": origin,
            "warehouse_id": warehouse_id,
            "season": envelope.season,
            "as_of": envelope.as_of.isoformat() if envelope.as_of else None,
            "live_sources": live_sources}

def _citation_entry(grouped, nodes, claim_index, source, envelope, node_id):
    key = (claim_index, source.evidence_id, node_id or "")
    existing = grouped.get(key)
    if existing is not None:
        return existing
    node = nodes.get(node_id) if node_id is not None else None
    existing = {
        "claim_index": claim_index,
        "evidence_id": source.evidence_id,
        "node_id": node_id,
        "source": source.source,
        "table": _warehouse_source_table(source.source, source.capability),
        "observed_at": (source.observed_at.isoformat()
                        if source.observed_at is not None else None),
        "vintages": dict(source.vintages),
        "provenance": _citation_provenance(envelope),
        "window_start": (envelope.window_start.isoformat()
                         if envelope.window_start is not None else None),
        "window_end": (envelope.window_end.isoformat()
                       if envelope.window_end is not None else None),
        "entities": [item.model_dump(mode="json")
                     for item in envelope.entities],
        "executed_arguments": (
            dict(envelope.execution_arguments)
            if envelope.execution_arguments is not None else None),
        "planned_arguments": dict(node.arguments) if node is not None else None,
        "outputs": [],
        "calculations": [],
    }
    grouped[key] = existing
    return existing

def _citation_source(sources, evidence, evidence_id):
    source = sources.get(evidence_id)
    envelope = evidence.get(evidence_id)
    if (source is None or envelope is None
            or source.source != envelope.source
            or source.capability != envelope.capability):
        return None
    return source, envelope

def _evidence_citation(grouped, nodes, evidence, sources, claim_index, binding):
    pair = _citation_source(sources, evidence, binding.evidence_id)
    if pair is None:
        return
    source, envelope = pair
    entry = _citation_entry(
        grouped, nodes, claim_index, source, envelope, binding.node_id)
    entry["outputs"].append(binding.model_dump(mode="json"))

def _calculation_citations(grouped, nodes, evidence_nodes, evidence, sources,
                           calculations, claim_index, binding):
    calculation = calculations.get(binding.calculation_id)
    if calculation is None:
        return
    operands = []
    for input_ in calculation.inputs:
        pair = _citation_source(sources, evidence, input_.evidence_id)
        if pair is None:
            return
        operands.append((input_, *pair))
    for input_, source, envelope in operands:
        entry = _citation_entry(
            grouped, nodes, claim_index, source, envelope,
            evidence_nodes.get(input_.evidence_id))
        record = {
            "calculation_id": calculation.calculation_id,
            "output_id": binding.output_id,
            "requirement_id": binding.requirement_id,
            "operation": calculation.operation,
            "result": str(calculation.result),
            "unit": calculation.unit,
            "input_path": input_.path,
            "inputs": [{"evidence_id": operand.evidence_id,
                        "path": operand.path}
                       for operand in calculation.inputs],
        }
        if record not in entry["calculations"]:
            entry["calculations"].append(record)

def _public_citations(result) -> list[dict]:
    from v2.contracts import CalculationOutputBinding, EvidenceOutputBinding
    from v2.runtime.models import withheld_claim_indices

    evidence = {item.evidence_id: item for item in result.execution.evidence}
    evidence_nodes = {
        envelope.evidence_id: node_id
        for node_id, envelope in result.execution.evidence_by_node.items()
    }
    nodes = {node.id: node for node in result.execution.plan.nodes}
    withheld = withheld_claim_indices(getattr(result, "gaps", None) or [])
    internal = _internal_identifier_rx(result)
    calculations = {
        item.calculation_id: item
        for item in getattr(getattr(result, "draft", None), "calculations", []) or []
    }
    grouped: dict[tuple[int, str, str], dict] = {}

    for claim in getattr(result, "verified_claims", None) or []:
        if claim.claim_index in withheld:
            continue
        if _publishable_claim_prose(result, claim, internal) is None:
            continue
        sources = {item.evidence_id: item for item in claim.sources}
        for binding in claim.output_bindings:
            if isinstance(binding, EvidenceOutputBinding):
                _evidence_citation(
                    grouped, nodes, evidence, sources, claim.claim_index, binding)
            elif isinstance(binding, CalculationOutputBinding):
                _calculation_citations(
                    grouped, nodes, evidence_nodes, evidence, sources,
                    calculations, claim.claim_index, binding)
    return [grouped[key] for key in sorted(
        grouped, key=lambda item: (item[0], item[1], item[2]))]

def _published_bindings(result) -> list:
    from v2.runtime.models import withheld_claim_indices

    verified = list(getattr(result, "verified_claims", None) or [])
    bindings: dict[tuple, object] = {}
    if verified:
        withheld = withheld_claim_indices(getattr(result, "gaps", None) or [])
        internal = _internal_identifier_rx(result)
        for item in verified:
            if item.claim_index in withheld:
                continue
            if _publishable_claim_prose(result, item, internal) is None:
                continue
            for binding in item.claim.output_bindings:
                bindings[(binding.requirement_kind, binding.requirement_id,
                          binding.output_id)] = binding
    for status in result.output_statuses:
        if status.status == "complete" and status.binding is not None:
            bindings.setdefault(
                (status.requirement_kind, status.requirement_id,
                 status.output_id), status.binding)
    return list(bindings.values())

def _traced_value(envelope, binding) -> tuple[Any, str | None]:
    from v2.runtime.models import (
        AmbiguousSelector, ResolvedSelector, _declared_value_matches,
        resolve_evidence_binding, resolve_subject_row,
    )
    from v2.contracts import canonical_entity_id

    subject_row = None
    if binding.subject_entity_id is not None:
        subject_row = resolve_subject_row(envelope, binding, canonical_entity_id(
            binding.subject_entity_type, binding.subject_entity_id))
        if subject_row is None:
            return None, "its subject selector names no row the envelope holds"
    resolution = resolve_evidence_binding(envelope, binding, subject_row)
    if isinstance(resolution, AmbiguousSelector):
        return None, "its selector names several values"
    if not isinstance(resolution, ResolvedSelector) or resolution.value is None:
        return None, "its selector resolves to nothing"
    if not _declared_value_matches(binding.value, resolution.value):
        raise ValueError("publication evidence changed after admission")
    return resolution.value, None

def _calculation_evidence_rows(binding, calculation, evidence) -> list[dict]:
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex, iter_values

    checked = Calculation.model_validate({
        "calculation_id": calculation.calculation_id,
        "operation": calculation.operation,
        "inputs": [item.model_dump() for item in calculation.inputs],
        "result": calculation.result, "unit": calculation.unit,
        "subject_input": calculation.subject_input})
    if validate_calculation(checked, EvidenceIndex(evidence.values())) is not None:
        raise ValueError("publication calculation no longer recomputes")
    rows = []
    for input_ in calculation.inputs:
        envelope = evidence.get(input_.evidence_id)
        selected = ([item.value for item in iter_values(envelope)
                     if item.path == input_.path] if envelope else [])
        if len(selected) != 1:
            raise ValueError("publication calculation input must resolve exactly once")
        rows.append({"output_id": binding.output_id,
                     "display_name": _output_display_name(binding.output_id),
                     "input_value": str(selected[0]),
                     "provenance": _citation_provenance(envelope)})
    return rows

def _public_evidence(result) -> tuple[list[dict], list[str]]:
    evidence = {item.evidence_id: item for item in result.execution.evidence}
    calculations = {item.calculation_id: item for item in result.draft.calculations}
    rows: dict[str, dict] = {}
    dropped: list[str] = []
    logger = logging.getLogger(__name__)

    def publish(row: dict) -> None:
        rows.setdefault(json.dumps(row, sort_keys=True), row)

    for binding in _published_bindings(result):
        if binding.requirement_kind != "calculation":
            envelope = evidence.get(binding.evidence_id)
            if envelope is None:
                raise ValueError("publication evidence is missing")
            value, reason = _traced_value(envelope, binding)
            if reason is not None:
                dropped.append(binding.output_id)
                logger.warning("publication could not trace %s: %s",
                               binding.output_id, reason)
                continue
            publish({"output_id": binding.output_id,
                     "display_name": _output_display_name(
                         binding.output_id, envelope.metric_definitions),
                     "subject_type": binding.subject_entity_type,
                     "subject_id": binding.subject_entity_id,
                     "subject_display_name": _subject_display_name(
                         binding, envelope),
                     "value": str(value),
                     "unit": (binding.unit.value if binding.unit.kind == "declared"
                              else "unitless"),
                     "provenance": _citation_provenance(envelope)})
            continue
        calculation = calculations.get(binding.calculation_id)
        if calculation is None:
            raise ValueError("publication calculation is missing")
        for row in _calculation_evidence_rows(binding, calculation, evidence):
            publish(row)
    cited = {row["output_id"] for row in rows.values()}
    untraced = list(dict.fromkeys(
        _output_display_name(output_id) + UNTRACED_SUFFIX
        for output_id in (
            *dropped,
            *(status.output_id for status in result.output_statuses
              if status.output_id not in cited))))
    return list(rows.values()), untraced

def _artifact_number(raw: object) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(float(raw)) else None
    text = str(raw or "").strip().replace(",", "")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _published_index(rows: list[dict]) -> dict[tuple[str, str], float]:
    index: dict[tuple[str, str], float] = {}
    for row in rows:
        output_id = str(row.get("output_id") or "")
        subject = str(row.get("subject_display_name") or "")
        if not output_id:
            continue
        value = _artifact_number(row.get("value"))
        if value is not None:
            index.setdefault((output_id, subject), value)
    return index


def _resolve_artifacts(
        intents: list, rows: list[dict]) -> list[dict]:
    index = _published_index(rows)
    resolved: list[dict] = []
    for intent in intents:
        series = []
        for entry in intent.series:
            values = []
            for point in entry.points:
                value = index.get((point.output_id, entry.name))
                if value is not None:
                    values.append(value)
            if values:
                series.append({"name": entry.name, "values": values})
        if not series:
            continue
        artifact: dict = {
            "kind": intent.kind.value,
            "title": intent.title,
            "series": series,
        }
        if intent.footnote:
            artifact["footnote"] = intent.footnote
        resolved.append(artifact)
    return resolved


def present_result(result):
    rows, unverified = _public_evidence(result)
    return {"text": _answer_text(result), "carry": {
        "verification": result.verification.status.value,
        "verified_claims": len(result.verified_claims),
        "gaps": _public_gaps(result),
        "output_statuses": [_public_output_status(result, status) for status in result.output_statuses],
        "citations": _public_citations(result)},
        "tables": rows, "unverified_numbers": unverified}
