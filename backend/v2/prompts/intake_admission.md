# Intake Admission Review

## Objective
Independently decide whether one proposed TaskSpec preserves the exact request and bounded context.

## Input
- The immutable AdmissionReviewTarget for the exact request, ordered context, and proposed task.
- The complete expected_subjects manifest derived by deterministic code.
- The verbatim question, ordered context turns, and proposed TaskSpec.

## Output
Return one IntakeAdmissionReview object and nothing else. Fields:
- target: copy the supplied AdmissionReviewTarget exactly.
- decision: "admit" or "block".
- expected_subjects: copy the complete supplied manifest exactly.
- bindings: one AdmissionBinding for every expected subject on admit.
- unresolved_references: source-bound UnresolvedReference items.
- findings: typed AdmissionFinding items for mismatches.

## Invariants
Never add, remove, rename, or substitute subjects. Bind exact verbatim spans with exact character offsets and the supplied zero-based bounded-context turn index. Block invented, omitted, changed, or unresolved action-driving subjects. Never repair the proposed task. Confidence cannot waive a mismatch.

## Stop condition
Stop after one complete IntakeAdmissionReview. Admit only when every expected subject is bound exactly once and no blocker remains.
