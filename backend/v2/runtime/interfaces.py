from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from v2.contracts import (
    ConversationTurn,
    DraftReport,
    EvidenceEnvelope,
    Plan,
    PlanNode,
    TaskSpec,
    VerificationReport,
)


class Intake(Protocol):
    async def understand(
        self, request: str, context: Sequence[ConversationTurn] = ()
    ) -> TaskSpec: ...


class Planner(Protocol):
    async def plan(self, task: TaskSpec) -> Plan: ...


class Capability(Protocol):
    name: str
    task_season_scoped: bool

    def validate_arguments(self, node: PlanNode) -> None: ...

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
