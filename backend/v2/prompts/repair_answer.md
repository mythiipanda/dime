# Answer repair

## Objective
Repair one DraftReport using the verifier's exact defects and the admitted evidence. This is the only repair pass.

## Input
- Selected skill instructions, when intake matched a skill. Follow them inside the contracts below.
- TaskSpec.
- The rejected DraftReport.
- VerificationReport with unsupported claims, conflicts, missing branches, and repair instructions.
- Admitted EvidenceEnvelopes. These are the only factual sources allowed.

## Output
One JSON object matching DraftReport and Claim, and nothing else:
- sections: presentation headings only;
- claims: rewritten Claim objects;
- calculations: declared arithmetic objects preserved for derived claims;
- blocked_calculation_requirement_ids: requested calculations still blocked by missing evidence;
- artifacts: preserved unchanged from the draft you were given. Never add, remove, or edit one here; an artifact whose points you stopped publishing simply stops rendering.
- gaps: specific limits that remain.

Each Claim contains:
- text: the claim prose;
- kind: observed, derived, projection, or judgment;
- evidence_ids: admitted sources supporting the claim;
- calculation_id: required for a derived claim;
- confidence: required for a projection claim;
- output_bindings: claim-local typed output proposals. Preserve valid existing proposals when the repaired claim still states that exact output; otherwise remove or replace them with exact requirement/output, evidence selector/value/subject/unit/domain, or calculation identity proposals for deterministic admission.
- Binding path format (mechanical, must match exactly): evidence rows live under `rows`. A row value uses selector "rows[i].COLUMN", row_selector "rows[i]", subject_selector "rows[i].ID_COLUMN" where ID_COLUMN is the identity key for the subject type, subject_entity_id the exact identity value from that column, and node_id the exact plan node id that produced the evidence. Never use filter expressions, display names, or bare column names as selectors.
- artifact_id: preserved from the draft you were given, or absent. Never invent one.

## Invariants
- Never add a fact, number, date, entity, season, rank, or unit absent from admitted evidence.
- Rewrite every rejected claim when its cited admitted evidence can support a corrected version. Remove it only when no admitted evidence can satisfy that branch.
- Preserve one claim for every previously represented subquestion; never turn a correctable branch into an omission.
- Preserve evidence_ids on every observed or derived claim.
- Preserve every calculation requirement as either a declared calculation or a blocked_calculation_requirement_id with a specific gap.
- Keep derived claims tied to their existing calculation_id and preserve the matching calculation declaration unchanged. Never invent a calculation id without a declaration.
- Name source conflicts and missing authority specifically in gaps.
- Never replace an evidence conflict with a generic apology or a claim that all data is missing.
- Preserve every claim the verification report marks supported exactly as written, including its entity spelling and evidence ids. Repair only rejected claims.

## Stop condition
Return after one valid DraftReport. No final-answer prose outside its fields.
