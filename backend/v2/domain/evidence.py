from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from v2.contracts import EvidenceEnvelope


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
    if isinstance(value, (date, datetime)):
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


class EvidenceIndex:
    def __init__(self, envelopes: Iterable[EvidenceEnvelope]) -> None:
        items = list(envelopes)
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
