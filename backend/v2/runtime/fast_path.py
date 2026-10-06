from __future__ import annotations

from v2.contracts import EvidenceEnvelope, Plan, PlanNode, TaskSpec, VerificationReport, VerificationStatus

class FastPathUnverifiable(Exception):
    pass

def is_fast_path_eligible(task: TaskSpec) -> bool:
    if len(task.requirements) != 1:
        return False
    if len(task.calculation_requirements) != 0:
        return False
    if len(task.entities) > 1:
        return False
    requirement = task.requirements[0]
    if len(requirement.capability_options) != 1:
        return False
    return True

def build_fast_plan(task: TaskSpec) -> Plan:
    requirement = task.requirements[0]
    name = requirement.capability_options[0]
    if requirement.capability_argument_sets:
        arguments = dict(next(
            item.arguments for item in requirement.capability_argument_sets
            if item.capability_id == name
        ))
    else:
        arguments = dict(requirement.capability_arguments)
    return Plan(nodes=[PlanNode(
        id="fast",
        description=requirement.description,
        capability_hints=[name],
        covers_requirement_ids=[requirement.id],
        arguments=arguments,
    )])

def check_fast_evidence(evidence: list[EvidenceEnvelope]) -> None:
    from v2.domain.evidence import iter_values
    if not evidence:
        raise FastPathUnverifiable("fast path produced no evidence")
    if not any(True for item in evidence for _ in iter_values(item)):
        raise FastPathUnverifiable("fast path produced no evidence values")

def check_fast_verification(verification: VerificationReport, claim_count: int) -> None:
    if claim_count == 0:
        raise FastPathUnverifiable("fast path produced no claims")
    expected = list(range(claim_count))
    observed = sorted(item.claim_index for item in verification.claim_results)
    if observed != expected:
        raise FastPathUnverifiable("fast path verification skipped a claim")
    if verification.status != VerificationStatus.PASS:
        raise FastPathUnverifiable("fast path could not verify")
    if any(not item.supported or item.uncertain for item in verification.claim_results):
        raise FastPathUnverifiable("fast path could not verify")

