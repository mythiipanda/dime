# Intake Admission Review

Independently review the proposed TaskSpec against the exact request and bounded context.
Return one IntakeAdmissionReview object.

The runtime supplies the immutable review target and the complete expected-subject manifest. Copy both exactly. Do not add, remove, rename, or substitute subjects. For an admit, bind every expected subject exactly once to a verbatim request or context span, with exact character offsets and the supplied zero-based bounded-context turn index. For a block, use a typed finding for a mismatched proposed subject or a source-bound unresolved reference when the source does not establish the referent. Never repair the TaskSpec. Never use confidence to waive a mismatch.
