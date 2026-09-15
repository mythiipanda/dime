# Answer repair

## Objective
Repair one model-authored DraftReport using the verifier's exact defects and the admitted evidence. Keep the answer natural and direct. This is the only repair pass.

## Input
- TaskSpec.
- The rejected DraftReport.
- VerificationReport with unsupported claims, conflicts, missing branches, and repair instructions.
- Admitted EvidenceEnvelopes. These are the only factual sources allowed.

## Output
One JSON object matching DraftReport and Claim, and nothing else:
- sections: presentation headings only;
- claims: rewritten model-authored Claim objects;
- gaps: specific limits that remain.

Each Claim contains:
- text: the model-authored claim prose;
- kind: observed, derived, projection, or judgment;
- evidence_ids: admitted sources supporting the claim;
- calculation_id: required for a derived claim;
- confidence: required for a projection claim.

## Invariants
- Do not add a fact, number, date, entity, season, rank, or unit absent from admitted evidence.
- Remove unsupported claims or rewrite them to match cited evidence.
- Preserve evidence_ids on every observed or derived claim.
- Keep derived claims tied to their existing calculation_id.
- Name source conflicts and missing authority specifically in gaps.
- Never replace an evidence conflict with a generic apology or claim that all data is missing.

## Stop condition
Return after one valid DraftReport. Do not output final-answer prose outside its fields.
