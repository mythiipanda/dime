# Two-way contract warehouse annotation specification

## Rule baseline

A player under a two-way contract is not one of the team's 15 standard-contract
roster players. A team may carry up to three two-way players in addition to the
standard roster. While the contract remains a two-way contract, its salary is
excluded from Team Salary, and therefore from the salary-cap, luxury-tax and
apron calculations in Dime's evaluator.

That exclusion ends when the contract is converted to a standard NBA contract.
It does not retroactively erase dead salary created by a different, previously
terminated standard contract.

Dead salary is a separate question from two-way status. When any contract is
terminated, the waiving team remains responsible for protected compensation,
subject to the contract's protection language, amounts already earned, the
universal January 10 cutdown rule, any buyout, any stretch election, and the
prior team's right of set-off from subsequent professional-basketball
compensation. Two-way contracts are usually minimally protected, but protection
is contractual. Do not infer that a two-way salary is either fully guaranteed or
fully non-guaranteed from the base salary alone.

For set-off, subsequent compensation is not limited to a standard NBA contract.
Compensation earned under a two-way contract can be relevant. The calculation
subtracts the applicable minimum salary before halving the remainder, so many
small two-way salaries produce no positive set-off amount, but that is a result
of the calculation rather than a blanket exemption.

## Implementation ownership

Warehouse writes remain cloud-owned. This specification is the contract those
seeders implement; evaluator code must keep working against older warehouses
that lack the newer columns or annotations.

| Component | Owner | Responsibility |
| --- | --- | --- |
| `silver_transactions` | `backend/scripts/seed_transactions.py` movement-feed path | Fetch the NBA player-movement feed, preserve transaction ordering evidence, partition rows into the existing `_season` units, and dedupe exact transaction identities. |
| `silver_salaries` | `backend/scripts/seed_salaries.py` | Own salary-row shape, contract-year columns, row identity, carry-forward rows, `ROW_KIND`, and eventually explicit `two_way`/`dead_money` annotations. |
| `silver_contracts` | `backend/scripts/seed_recent_market.py` contract transform | Own the static contract fallback fields, including `TWO_WAY` and `TERMINATED`. These fields are evidence, not final current-state authority. |
| Cap evaluator | `backend/shared/tools/league/cba_two_way.py` plus its callers | Compatibility reconstruction for incompletely annotated warehouses. It must not require columns that an older warehouse does not have. |

No existing seeder currently owns the full protected-compensation calculation.
That input is unavailable in the warehouse; see the dead-money limits below.
Do not pretend that adding transaction rows alone proves exact dead salary.

## `silver_transactions` output contract

The movement-feed seeder writes these data columns, followed by the normal
warehouse metadata columns `_source`, `_season`, `_fetched_at`, and `_entity`:

| Column | Polars type as written | Meaning |
| --- | --- | --- |
| `txn_date` | `String` | First ten characters (`YYYY-MM-DD`) of `TRANSACTION_DATE`. |
| `txn_type` | `String` | Source `Transaction_Type`, such as `Signing`, `Waive`, `Trade`, `ContractConverted`, or `AwardOnWaivers`. |
| `player` | `String` | Source `PLAYER_SLUG`. It is a slug, not display-name text. |
| `player_id` | `Float64` | Source `PLAYER_ID`. Values are integral in the feed but are currently stored in the feed-native floating representation for compatibility with existing warehouses. |
| `team` | `String` | Source `TEAM_SLUG`. |
| `team_id` | `Float64` | Source `TEAM_ID`, with the same integral-value/floating-storage caveat as `player_id`. |
| `detail` | `String` | Full source `TRANSACTION_DESCRIPTION`. |
| `group_sort` | `String` | Source `GroupSort`, preserved verbatim. For signing, waive, conversion, and waiver-claim rows its trailing integer is the feed's same-date ordering evidence. |
| `additional_sort` | `Float64` | Source `Additional_Sort`, preserved verbatim. It is zero for non-trade rows in the observed feed and nonzero trade metadata for trade rows. |

The seeder has no separate stable transaction ID. Row identity for dedupe is
the tuple `(txn_date, txn_type, player, player_id, team, team_id, detail)`.
Exact duplicates on that identity are collapsed, keeping the first feed row.
Distinct rows sharing a date, type, player, and team are still possible when
`detail` differs; they must not be collapsed merely because they look unusual.

Replacement ownership is at the existing `(_season, _entity)` unit. That is a
storage replacement key, not transaction identity and not the cap league-year
mapping.

## Season labels versus cap league years

The movement seeder's existing `_season` partition uses the historical October
cutover: a transaction dated in July through September of year `Y` is stored in
the unit ending in year `Y` (for example, August 2026 is `_season='2025-26'`).
This partition is retained for warehouse-write ownership and resume behavior.

For cap reconstruction, `_season` must not be interpreted as the league year.
The evaluator derives league year from `txn_date`: July 1 of year `Y` through
June 30 of year `Y+1` is league year `Y-(Y+1)`. Thus July-September 2026
belongs to 2026-27 even when the storage row says `_season='2025-26'`.

The evaluator's compatibility reconstruction uses a bounded three-league-year
window: the salary league year plus the two preceding league years. A two-way
contract can run for one or two seasons, so the previous league year is needed
for continuing two-way contracts. The additional preceding year captures a
waiver immediately before an early-July formation, such as a June standard-contract
waiver followed by a July two-way signing. Older rows are outside the
plausibly active formation window and are not used for this reconstruction.
Reconstructed active two-way state may cover the formation league year and the
following league year at most; it must not exclude standard salary in a third
league year unless explicit current annotation says the row is two-way. The
window is a compatibility bound, not a claim that old dead money expires;
exact multi-year dead money requires explicit dead-money rows.

## Same-date transaction ordering

`txn_date` alone is not a total order. The real feed contains same-date
sign/waive pairs, including Duane Washington Jr. on 2023-07-24 and Didi
Louzada on 2022-10-17.

When `group_sort` and `additional_sort` are present, reconstruction orders
rows by:

1. `txn_date`;
2. the trailing integer in `group_sort`, ascending;
3. `additional_sort`, ascending;
4. deterministic text fallbacks (`txn_type`, canonical team, player, detail).

Older warehouses do not have these columns. The evaluator must therefore omit
missing keys rather than fail. With both keys absent or tied, the deterministic
fallback orders non-claim rows by case-insensitive `txn_type` and places waiver
claims after non-claim rows on the same date, then uses canonical team, player,
and detail. A same-date waive can therefore be paired with its claim regardless
of scan order, while sign/waive ordering remains deterministic. That fallback is
not evidence of the true time of day. Ordering sensitive cases other than the
waive/claim causal pair remain approximate until a reseeded warehouse carries
`group_sort` and `additional_sort`.

## Transaction state machine needed in the seeder and evaluator fallback

Process transactions chronologically per player, carrying state across season
boundaries until the contract state changes. Do not depend only on rows whose
storage `_season` equals the salary season; continuing two-way contracts often
have no new transaction row in the later season.

Use case-insensitive detail parsing:

- detail containing `to a two-way contract` starts or continues active two-way
  state for the transaction team, for both `Signing` and `ContractConverted`;
- `ContractConverted` detail containing `to an nba contract` ends active
  two-way state and starts standard-contract treatment;
- any later non-two-way signing ends active two-way state and starts
  standard-contract treatment;
- a waive of the active two-way team ends active two-way state. After that
  waiver, and before any later standard signing or conversion, the player is on
  no team's standard roster;
- a `Trade` row transfers the current active two-way or standard-contract state
  to the transaction team. In the movement feed, a player row's team is the
  receiving team;
- an `AwardOnWaivers` row claims the most recent unclaimed waive. The claimed
  contract continues with the claiming team, so a known two-way state resumes
  as two-way and a known standard state resumes as standard. A claimed waive is
  not terminated-contract evidence;
- preserve every waive event, even when the waived contract was not itself a
  two-way contract, because it is needed to connect later dead-money rows.

When the waived contract's type is outside reconstruction coverage, an
`AwardOnWaivers` row still blocks terminated-contract inference for that waive,
but the evaluator cannot know which contract type continues. That boundary
requires explicit row annotation rather than a confident reconstruction.

Resolve transaction team slugs through the canonical team mapping, including
nicknames such as `sixers` and `blazers`.

When a two-way formation follows a waiver, record the pair as durable
terminated-contract evidence. That evidence must survive the later end of the
two-way contract. In particular:

- if the two-way contract is subsequently waived, the player is on no standard
  roster and the earlier terminated standard row remains dead-money evidence;
- if the two-way contract is converted, the new standard contract governs rows
  belonging to that contract, but the earlier terminated row must not migrate
  onto the converting team's standard payroll merely because playing evidence
  places the player there.

## Required annotation model

Keep two concepts distinct:

1. `ROW_KIND` describes the row's cap-ledger role. Required values for this work:
   - `roster`: standard-contract salary counting as roster payroll;
   - `two_way`: active two-way compensation excluded from Team Salary and the
     standard-roster count;
   - `dead_money`: terminated-contract obligation counting as dead salary.
2. `CONTRACT_TYPE`, if present, describes the underlying contract type
   (`standard`, `two_way`, or a more specific source type). It is useful
   evidence, but it must not replace `ROW_KIND`, because one player can have a
   terminated standard-contract dead-money row and an active two-way row at the
   same time.

A terminated standard row and an active two-way row coexist as separate rows
whenever the warehouse has enough contract identity:

- the terminated row keeps the original team and contract identity, has
  `ROW_KIND='dead_money'`, and carries protected amounts by season;
- the active row keeps the current team and contract identity, has
  `ROW_KIND='two_way'` and `CONTRACT_TYPE='two_way'`, and is excluded from
  Team Salary and the standard-roster count;
- both rows may share `PLAYER_ID` and normalized player name. Neither player
  identity nor team alone is a contract identity.

The preferred contract-row identity is `(PLAYER_ID, contract identity,
team, first contract season)`. The warehouse currently does not provide a real
source contract ID. Until one exists, seeders may use a clearly documented
synthetic key only if it is stable across reseeds; otherwise contract identity
is unavailable and must be disclosed rather than invented. This is why exact
coexistence cannot be reconstructed for every legacy row.

Explicit `ROW_KIND` is authoritative for the row's cap-ledger role: `roster`
counts as roster payroll, `two_way` is excluded as two-way compensation, and
`dead_money` counts as dead salary. `CONTRACT_TYPE='two_way'` is exclusion
evidence only when `ROW_KIND` is absent or undeclared. Transaction
reconstruction is only a compatibility fallback for those incompletely
annotated rows; it must not override an explicit row kind.

## Clayton end state

Observed facts:

- Memphis waived Walter Clayton Jr. on 2026-10-19.
- Dallas signed him to a two-way contract on 2026-10-21.
- The surviving `silver_salaries` row is `PLAYER_NAME='Walter Clayton'`,
  `TEAM='MEM'`, `PLAYER_ID=1642383`, `SALARY_2026_27=$4,190,520`,
  `GUARANTEED=$4,190,520`, `ROW_KIND` currently roster or absent depending on
  warehouse vintage.
- `silver_player_season` has him with Dallas in 2026-27. That is factual playing
  evidence, not authority for standard-roster cap treatment.

Correct cap-ledger end state:

1. No Memphis roster row for Clayton.
2. No Dallas standard-roster row for Clayton.
3. A Dallas `ROW_KIND='two_way'` row may exist for contract inventory, with the
   actual prorated two-way compensation if known. Its salary must not be included
   in Team Salary or the 15-man roster count.
4. A Memphis `ROW_KIND='dead_money'` row must represent the protected portion of
   the terminated standard rookie-scale contract. Based on the warehouse row,
   the current-season protected amount is $4,190,520. That amount should remain
   unless the seeder has evidence of a buyout, stretch election, set-off, or a
   different protection allocation. No such evidence is present in the warehouse
   probe.
5. The Memphis dead-money row must not make Clayton a Memphis roster player.
   The Dallas two-way row must not make him a Dallas standard-roster player.
6. If Dallas later waives the two-way contract, Clayton is on no team's standard
   roster and the Memphis dead-money evidence still survives.
7. If Dallas converts the two-way contract, the converted Dallas contract is a
   standard contract, but the terminated Memphis row still must not be counted
   as Dallas standard payroll.

The later Dallas two-way signing does not erase the Memphis obligation. It only
means the subsequent Dallas compensation is excluded while it remains two-way.
Any set-off must be calculated from the CBA formula using actual subsequent
compensation; do not zero the Memphis row merely because a new contract exists.

## Dead-money data the seeder must preserve when available

For each terminated-contract row, preserve enough fields to evaluate dead salary
without guessing:

- original contract type and contract identity;
- waiver/release date and waiving team;
- base salary by season;
- protected amount by season, not only one aggregate `GUARANTEED` value;
- earned amount through release when protection is partial or absent;
- whether termination occurred before or after the universal cutdown guarantee;
- team/player option status and whether the option had been exercised;
- buyout amount, if any;
- stretch election and allocation, if any;
- subsequent compensation and computed set-off, if any;
- source transaction rows used for the inference.

The current warehouse cannot provide true source contract identity, per-season
protection allocations, amounts earned through release, buyout amount, stretch
elections, or subsequent-compensation set-off inputs. Those inputs are
unavailable, not optional conveniences. Until a source supplies them, the
seeder must write an explicit unknown/approximation status rather than a false
exact amount. Do not silently treat aggregate remaining protection as exact
current-season dead salary: that field can span multiple seasons and can include
or exclude option years depending on source semantics.

## Current evaluator compatibility behavior and limits

The evaluator-side compatibility path:

- treats explicit `ROW_KIND` as authoritative and uses `CONTRACT_TYPE='two_way'`
  only when the row kind is absent or undeclared;
- reconstructs active, ended, and converted two-way state from transaction
  details and the `silver_contracts.TWO_WAY` fallback;
- uses the static `silver_contracts.TWO_WAY` fallback only when no transaction
  evidence exists for that player, so the static current-state row cannot rewrite
  the chronology of reconstructed transactions;
- bounds reconstructed active two-way state to the maximum two-league-year term
  unless explicit current annotation exists, and classifies multi-season cap
  surfaces separately for each salary season rather than carrying the base-season
  classification forward;
- treats a missing or malformed formation date as unknown rather than permanently
  active: the row is not excluded on that unknown evidence, and cap surfaces
  disclose the affected player/seasons through `two_way_classification_unknown`
  metadata or projection disclosures. A static fallback row is positive evidence
  only for its own `_season`; later seasons remain unknown;
- transfers reconstructed contract state on `Trade` rows and honors
  `AwardOnWaivers` as continuation with the claiming team when the waived
  contract type is known;
- maps transaction dates to cap league years rather than trusting the storage
  `_season` partition;
- uses `group_sort`/`additional_sort` when present and a documented deterministic
  ordering when absent;
- excludes active two-way rows from Team Salary and the roster-player list in
  payroll, cap-sheet, and cap-projection baselines;
- recognizes conversion back `to an NBA Contract` as standard-contract treatment;
- preserves terminated-contract evidence after a later two-way waiver or
  conversion, except when the underlying waive was claimed;
- recognizes the Clayton pattern when a player was waived by the salary-row team
  before signing a two-way contract elsewhere.

The dead-money inference is deliberately narrow. It infers the current salary as
Memphis-style dead money only when the warehouse shows a preceding unclaimed
waive of a standard or unknown contract by that row team, the row team differs
from the two-way formation team, the row has no positive future-season salary,
and `GUARANTEED` covers at least the full current salary. A waive known to end
a two-way contract does not feed this standard-contract inference. The
different-team requirement avoids treating an indistinguishable same-team
current two-way row as its own terminated standard row; same-team cases need
explicit contract identity and are currently unavailable. An explicit dead-money
row for the same player and team suppresses inference regardless of whether the
amounts agree, including a corrected zero row. A null explicit amount is carried
as `amount_unknown` evidence rather than dropped. When both rows carry player
IDs, identity suppression compares `PLAYER_ID`; normalized-name matching is only
the fallback when either row lacks an ID, avoiding suffix collisions such as
Gary Payton versus Gary Payton II.

When terminated-contract evidence exists but protection is partial, missing, or
cannot be allocated because positive future salary remains, the evaluator emits
a dead-money detail row with null salary, `amount_unknown=true`, and a
protection-unknown basis. Numeric payroll totals do not fabricate that amount,
and dead-money component availability is false for the affected cap-sheet
season. Those cases remain unquantified until the seeder writes explicit
dead-money rows with the fields above.

Continuing two-way players can still be missed when all of the following are
true: the formation is older than the bounded reconstruction window,
`silver_contracts.TWO_WAY` is false or stale, and the salary row lacks explicit
two-way annotation. That is a warehouse coverage limitation, not a CBA
ambiguity. The seeder-side annotation is required to close it.

## Known boundaries not closed by this evaluator revision

- Sequential-stint termination generation refresh is not modeled. The evaluator
  preserves the termination evidence it can causally link, but it does not
  renumber or regenerate termination sequences across multiple sequential
  standard-contract stints.
- One-year midseason two-way term precision remains season-grained. The
  compatibility bound uses league years and does not calculate exact day-count
  expiry for a one-year two-way contract formed midseason.
- The frontend TypeScript contract does not yet render the `amount_unknown`
  dead-money marker as a first-class presentation state. Backend payloads carry
  the honest-unknown evidence; frontend rendering alignment remains a separate
  contract-update task.

## Acceptance checks

Minimum seeder/evaluator regression cases:

1. Clayton: Dallas payroll excludes the two-way arrangement; Dallas standard
   roster count excludes him; Memphis roster count excludes him; Memphis dead
   money carries the protected terminated standard-contract amount.
2. Active two-way signing: salary row is excluded from payroll and roster count.
3. July-September signing for the upcoming league year is included in reconstruction
   even when storage `_season` still names the preceding season.
4. Continuing two-way contract with no same-season transaction row remains
   excluded through carried-forward or explicitly seeded annotation.
5. Preseason conversion `to an NBA Contract` overrides a stale `TWO_WAY=True`
   fallback and subsequent standard salary returns to payroll and roster count.
6. Two-way then waived: the player is on no team's standard roster and durable
   terminated-contract evidence remains on the original team.
7. Clayton then converted: the terminated Memphis row is not Dallas standard
   payroll and Memphis dead money survives.
8. Same-date waive/sign ordering is deterministic without ordering columns and
   uses `group_sort`/`additional_sort` when present.
9. Payroll, cap-sheet, and cap-projection baselines agree on the same fixture.
10. Two-way waived with partial protection: dead amount equals the calculated
    protected/earned amount when the inputs exist; otherwise the amount is
    explicitly unknown/approximate rather than automatically zero or full base
    salary.
11. Waived standard contract followed by a two-way contract elsewhere: original
    team keeps dead money, new team's two-way salary is excluded.
12. Explicit `ROW_KIND='roster'` remains roster payroll even when reconstruction
    finds durable termination evidence for the same player.
13. A two-way formation two or more league years before the salary season does
    not exclude a current standard row without explicit current annotation.
14. Partial protection or positive unallocated future salary produces a null-
    amount `amount_unknown` dead-money detail rather than silent omission.
15. An explicit corrected dead-money row suppresses inferred dead money for the
    same player and team even when the explicit and inferred amounts differ.
16. A traded two-way contract follows the receiving team, a subsequent waive by
    that team ends it, and a waiver claim continues the contract with the
    claiming team rather than creating terminated-contract evidence.
