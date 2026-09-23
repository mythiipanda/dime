# Answer repair

## Objective
Repair one model-authored DraftReport using the verifier's exact defects and the admitted evidence. Keep the answer natural and direct. This is the only repair pass.

## Input
- Selected skill instructions, when intake matched the request to a relevant skill. Follow them inside the task, evidence, and output contracts.
- TaskSpec.
- The rejected DraftReport.
- VerificationReport with unsupported claims, conflicts, missing branches, and repair instructions.
- Admitted EvidenceEnvelopes. These are the only factual sources allowed.

## Output
One JSON object matching DraftReport and Claim, and nothing else:
- sections: presentation headings only;
- claims: rewritten model-authored Claim objects;
- calculations: declared arithmetic objects preserved for derived claims;
- blocked_calculation_requirement_ids: requested calculations still blocked by missing evidence;
- gaps: specific limits that remain.

Each Claim contains:
- text: the model-authored claim prose;
- kind: observed, derived, projection, or judgment;
- evidence_ids: admitted sources supporting the claim;
- calculation_id: required for a derived claim;
- confidence: required for a projection claim;
- output_bindings: claim-local typed output proposals. Preserve valid existing proposals when the repaired claim still states that exact output; otherwise remove or replace them with exact requirement/output, evidence selector/value/subject/unit/domain, or calculation identity proposals for deterministic admission.

## Invariants
- Do not add a fact, number, date, entity, season, rank, or unit absent from admitted evidence.
- Rewrite every rejected claim when its cited admitted evidence can support a corrected version. Remove it only when no admitted evidence can satisfy that answer branch.
- Preserve one claim for every previously represented TaskSpec subquestion; a repair must not turn a correctable branch into an omission.
- Preserve evidence_ids on every observed or derived claim.
- Preserve every calculation requirement as either a declared calculation or a blocked_calculation_requirement_id with a specific gap.
- Keep derived claims tied to their existing calculation_id and preserve the matching calculation declaration unchanged. Never invent a calculation id without a declaration.
- Name source conflicts and missing authority specifically in gaps.
- Never replace an evidence conflict with a generic apology or claim that all data is missing.

## Stop condition
Return after one valid DraftReport. Do not output final-answer prose outside its fields.
- Preserve every claim the verification report marks supported exactly as
  written, including its entity spelling and evidence ids. Repair only rejected
  claims; never rewrite or delete supported claims while fixing another claim.
