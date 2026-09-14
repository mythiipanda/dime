from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from v2.contracts import (
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    TaskSpec,
    VerificationReport,
)


class Intake(Protocol):
    async def understand(self, request: str) -> TaskSpec: ...


class Planner(Protocol):
    async def plan(self, task: TaskSpec) -> Plan: ...


class Capability(Protocol):
    name: str

    async def execute(
        self,
        node: PlanNode,
        task: TaskSpec,
        evidence: Sequence[EvidenceEnvelope],
    ) -> EvidenceEnvelope: ...


class Synthesizer(Protocol):
    async def synthesize(
        self, task: TaskSpec, evidence: Sequence[EvidenceEnvelope]
    ) -> DraftReport: ...


class Verifier(Protocol):
    async def verify(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
    ) -> VerificationReport: ...


class Repairer(Protocol):
    async def repair(
        self,
        task: TaskSpec,
        draft: DraftReport,
        evidence: Mapping[str, EvidenceEnvelope],
        verification: VerificationReport,
    ) -> DraftReport: ...
