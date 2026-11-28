---
name: verify-cba-legality
description: "Verify Dime's CBA trade-legality salary matching, traded-player-exception allocation, and hard-cap consequences when editing backend/shared/tools/cap_rules.py, backend/shared/tools/league/cba_cap.py, backend/shared/tools/league/trade_legality.py, or backend/tests/test_verify_cba_legality.py."
---

# Verify CBA legality

Use this skill before trusting or merging a change to Dime's CBA salary-matching,
traded-player-exception (TPE), or hard-cap decision logic.

## What is verified

Property: for every generated team-side input, `matching_ok` is true exactly when
each incoming player salary can be assigned to one non-combined salary-matching or
active TPE capacity, the least-restrictive matching election is reported with the
correct operative `match_rule`, every applicable hard-cap trigger is represented
in `hard_cap`, and a hard-cap issue appears exactly when post-trade payroll is
strictly above the triggered apron. Standard simultaneous matching covers 100% of
outgoing salary plus the applicable cushion: $250,000 at or below the first apron
and $0 above it. Cap-room absorption is elected before that simultaneous band,
expanded matching is required only after the standard band is exceeded, and
aggregated standard matching is a second-apron trigger rather than an expanded
or first-apron trigger.

Harm: a break can tell an analyst that an illegal trade is legal, reject a legal
trade, or hide a first/second-apron hard cap that changes the team's subsequent
roster options.

The harness tests the real Python functions. It does not test a copied hand model.
The assignment oracle is an independent exhaustive enumerator used only as the
test oracle; the code under test is Dime's implementation.

## Run

From the repository root:

```sh
python -m pytest backend/tests/test_verify_cba_legality.py -q
```

A normal run is deterministic, uses seed `20261127`, and takes a few seconds. A
failure prints the complete unshrunk input case in the assertion message. For a
broader local sample, set `VERIFY_CBA_CASES` to a larger integer before the same
pytest command; the default is `600` generated cases per randomized suite.

No Hypothesis or other dependency is required. Hypothesis is not already a dev
dependency, `backend/requirements.txt` is installed into the runtime Docker image,
and the repository has no separate Python dev-requirements file. The harness uses
stdlib seeded generation instead of adding a runtime or CI-only dependency.

## Coverage record

Sync commit: `29f5d793ae27068b3f7397b25a65480ae85f96c8`

Covered files and functions at that commit:

| File | Directly or indirectly covered functions |
| --- | --- |
| `backend/shared/tools/league/trade_legality.py` | `_placement_fits`, `_expanded_matching_use`, `_tpe_usage`, `_public_tpe`, `_evaluate_team` |
| `backend/shared/tools/league/cba_cap.py` | `_outgoing_needed` |
| `backend/shared/tools/cap_rules.py` | `allowed_incoming`, `used_expanded_matching`, `matching_election`, `operative_match_rule`, `apron_state`, `hard_cap_consequences` |

The covered input domain is nonnegative integer salaries, TPE amounts, capacities,
cap room, payrolls, active current-year/prior-year TPE rows, cash-out presence,
outgoing-player aggregation, and the first/second-apron lines encoded in `CAP`.
Generated integration inputs satisfy the internal `_evaluate_team` shape produced
by `_team_side`: incoming totals equal the sum of incoming row salaries, outgoing
totals are nonnegative, zero-outgoing sides have no outgoing player names, and no
sign-and-trade/BYC input is present.

The exhaustive core checks all 23,360 combinations of up to three salaries in
`{0,1,2}`, one to three bins with capacities in `{0,1,2,3}`, and every
required-bin mask. Randomized checks extend that to as many as five salaries,
four bins, larger small-integer capacities, optional strict matching limits,
direct expanded-matching detection, exact 2026-27 matching-band arithmetic and
rule identity at the $8,846,000 and $35,384,000 scaled-band boundaries, a fixed
least-restrictive matching-election vector matrix, matching inverse/monotonicity
cases, all 64 hard-cap trigger boolean combinations at six apron-boundary
payrolls, deterministic propagated `match_rule` vectors, fixed first-apron
exact/$1-over expanded-matching cushion vectors, fixed zero-outgoing `$1`,
`$250,000`, and `$250,001` no-capacity vectors, positive-minimum versus
zero-salary outgoing-slot vectors, cap-room and declared-TPE absorption vectors,
and 600 seeded `_evaluate_team` team-side cases including sub-`$1M` incoming
salaries across zero-outgoing cap-room, declared-TPE, and
no-available-structure paths.

## Read a failure

Start with the printed input case, then classify it before changing anything:

1. Real implementation bug: the input is inside the covered domain above and the
   real function's answer contradicts the property. Report the counterexample in
   the code's terms (`salaries`, `capacities`, `required_bins`, `pay_before`,
   `out_total`, `in_rows`, `team_tpes`, `hard_cap`, `payroll_after`). Do not
   weaken the property to make it pass and do not fix product code unless the
   user asked for a fix.
2. Modeling error: the input violates the stated `_evaluate_team` input shape,
   uses inactive/expired/future TPE rows, includes sign-and-trade or BYC state,
   or depends on warehouse/name-resolution behavior outside this harness. Fix
   the generator or oracle, then rerun.
3. Intended rules change: the implementation and harness disagree because the
   CBA constants or rule semantics deliberately changed. Update the independent
   expectation in `backend/tests/test_verify_cba_legality.py`, prove the revised
   harness can still fail on a scratch break, and only then move the sync commit.

A mismatch in `_placement_fits` usually concerns non-combination or
required-TPE-bin semantics. A mismatch in `hard_cap` usually concerns trigger
completeness.
A mismatch in public `tpe_details[].capacity` usually concerns the `$250,000`
TPE cushion or the post-trade first-apron reduction.

## Scope left out

This harness does not cover warehouse access, DuckDB salary-column resolution,
player-name matching, real roster construction, pick ownership, Stepien or
frozen-pick rules, cash JSON parsing, expired/future TPE parsing and validation,
sign-and-trade receiver detection, base-year compensation, no-trade clauses, trade
kickers, poison-pill contracts, roster minimums, annual cash limits, or whether
the encoded constants correctly represent a future CBA season. It verifies the
stated pure decision procedure and its `_evaluate_team` wiring, not the whole
`get_trade_legality` tool and not live answer quality.

## Keep the verification in step

Before relying on the harness after pulling new work, compare the covered files
with the sync commit:

```sh
git diff 29f5d793ae27068b3f7397b25a65480ae85f96c8 -- backend/shared/tools/cap_rules.py backend/shared/tools/league/cba_cap.py backend/shared/tools/league/trade_legality.py
```

If the diff is empty, the coverage record is current. If it is not empty, inspect
whether the input contract, constants, trigger meanings, or allocation semantics
changed. Update the harness when intended semantics changed, run it cleanly, and
move the sync commit forward only after confirming that the verification describes
the covered code at that newer commit. Never advance the commit merely because
time passed or the files were touched.

When changing this harness, prove it is still able to fail on a scratch variant
of the real code, then revert the scratch variant and rerun the clean check.
Useful scratches include flipping a scaled-band boundary comparison, removing the
standard or TPE cushion, disabling cap-room absorption, flipping a capacity
comparison, bypassing strict assignment absorption, or dropping one hard-cap
trigger.
