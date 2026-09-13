# Verify v1: canon guard spec (Sep 12, 2026)

Upgrade verify from v0 telemetry to deterministic enforcement, closing
the F61/F62 residual class: compose ships "that prior value was not
included in this evidence" while the thread ledger holds the value
(QA retest, 5:07 PM deploy). Root cause: absence claims are checked
against THIS TURN's payloads only, never the ledger.

## Current state (v0, live since v70/v74)

- `_verify_draft_numerals`: numeral-provenance telemetry (logs, no
  enforcement).
- False-absence guard: strips "missing/unavailable" sentences about
  entities literally present in this turn's payloads.
- Known-gap taxonomy pins: zero-tool named-gap answers for unowned
  classes.
- F63-T3 ledger fallback: when fresh evidence FAILS, analytics answers
  from ledger facts. The remaining gap is the inverse: evidence
  EXISTS, but the draft denies the ledger.

## v1 checks (deterministic, no second LLM call on the hot path)

1. **Absence-claim canon guard.** A sentence claiming data is
   missing/not included/unavailable may ship only when one of:
   - a known-gap taxonomy entry matches the question;
   - a tool returned an explicit empty result with a coverage note;
   - the entity/metric appears in neither this turn's payloads NOR the
     thread ledger.
   Otherwise: strip the claim; if the ledger holds the requested fact,
   append "From earlier in this conversation: <fact>" (F63-T3 pattern,
   generalized into compose).
2. **Ledger consistency.** A draft claim contradicting a ledger fact
   (e.g. "the Spurs were not in the Finals" vs ledger "NBA Finals
   result: NYK 4-1 SAS") fails verification -> ONE bounded re-route to
   the owning lane -> still failing -> honest end naming coverage.
3. **Numeral provenance, enforcement.** Every stat numeral in the
   draft must trace to this turn's payloads or the ledger (v67 design
   law, generalized off pinned lanes). Roll out telemetry-first: one
   benchmark cycle logging would-be strips before enforcing, since
   derived values (averages, deltas) are legitimate.

## Failure handling

One bounded re-route, then an honest dead-end naming what IS covered.
No hangs: checks are string/fact comparisons inside the existing
watchdog budget.

## Acceptance + burn-down tie-in

- New benchmark scenarios: F61 residual chain ("compare that to his
  season average" after a playoff-ppg turn), F62 chain ("that game"
  carry), F64 season-line mislabel. Pack must stay green incl. these;
  canon scenarios must show zero canon-guard false positives.
- Same cycle measures pin burn-down: each pin's phrasing class runs
  the general route; green without the pin = retire the pin.

## Rollout order

1. Canon-guard checks in telemetry mode + new benchmark scenarios.
2. Enforce absence-claim + ledger-consistency checks.
3. Numeral-provenance enforcement (after one clean telemetry cycle).
