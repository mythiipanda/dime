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

## Warehouse evidence found on 2026-11-28

`silver_transactions.detail` is currently the only reliable current-state
two-way marker found. The match must use detail text, not only `txn_type`:

- `Signing`: `Dallas Mavericks signed guard Walter Clayton Jr. to a Two-Way Contract.`
- `Signing` can also use `re-signed` in the detail text.
- `ContractConverted`: `Phoenix Suns converted the contract of forward Drew Timme to a Two-Way Contract.`
- Conversion back to a standard contract is phrased `to an NBA Contract.`

The 2026-27 probe found 29 rows whose detail contained `to a Two-Way Contract.`:
19 `Signing` rows and 10 `ContractConverted` rows.

Static contract rows are not sufficient. Clayton has two `silver_contracts`
rows for Memphis (`TWO_WAY=False`, including the 2026-27 row at $4,190,520),
while the current transaction evidence says Dallas signed him to a two-way
contract. Other probes showed the same pattern in both directions: current
two-way players can remain standard rows, and historical `TWO_WAY=True` rows do
not necessarily describe the current contract state.

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

The evaluator should be able to rely on `ROW_KIND='two_way'` or
`CONTRACT_TYPE='two_way'` once seeding is correct. Transaction reconstruction is
only a compatibility fallback for incompletely annotated warehouses.

## Transaction state machine needed in the seeder

Process transactions chronologically per player, carrying state across season
boundaries until the contract state changes. Do not depend only on rows whose
`_season` equals the salary season; continuing two-way contracts often have no
new transaction row in the later season.

Use case-insensitive detail parsing:

- detail containing `to a two-way contract` starts or continues active two-way
  state for the transaction team, for both `Signing` and `ContractConverted`;
- `ContractConverted` detail containing `to an nba contract` ends active
  two-way state and starts standard-contract treatment;
- any later non-two-way signing ends active two-way state;
- a waive of the active two-way team ends active two-way state;
- preserve every waive event, even when the waived contract was not itself a
  two-way contract, because it is needed to connect later dead-money rows.

Resolve transaction team slugs through the canonical team mapping, including
nicknames such as `sixers` and `blazers`.

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

The later Dallas two-way signing does not erase the Memphis obligation. It only
means the subsequent Dallas compensation is excluded while it remains two-way.
Any set-off must be calculated from the CBA formula using actual subsequent
compensation; do not zero the Memphis row merely because a new contract exists.

## Dead-money data the seeder must preserve

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

If those fields are unavailable, mark the amount unknown or use a clearly named
approximation. Do not silently treat aggregate remaining protection as exact
current-season dead salary: that field can span multiple seasons and can include
or exclude option years depending on source semantics.

## Current evaluator compatibility behavior and limits

The evaluator-side fix in the accompanying change:

- honors explicit `ROW_KIND='two_way'` and `CONTRACT_TYPE='two_way'`;
- reconstructs active two-way state from transaction details and the
  `silver_contracts.TWO_WAY` fallback;
- excludes active two-way rows from Team Salary and the roster-player list;
- recognizes conversion back `to an NBA Contract` as standard-contract treatment;
- separates the Clayton pattern when a player was waived by the salary-row team
  before signing a two-way contract elsewhere.

The dead-money inference is deliberately narrow. It infers the current salary as
Memphis-style dead money only when the warehouse shows a preceding waive by that
row team, the row has no positive future-season salary, and `GUARANTEED` covers
at least the full current salary. It does not fabricate partial-protection,
multi-year, buyout, stretch or set-off allocations that the warehouse cannot
currently represent. Those cases remain undercounted until the seeder writes
explicit dead-money rows with the fields above.

Continuing two-way players can still be missed when all of the following are
true: there is no current-season transaction detail, `silver_contracts.TWO_WAY`
is false or stale, and the salary row lacks explicit two-way annotation. That is
a warehouse coverage limitation, not a CBA ambiguity. The seeder-side annotation
is required to close it.

## Acceptance checks

Minimum seeder regression cases:

1. Clayton: Dallas payroll excludes the two-way arrangement; Dallas standard
   roster count excludes him; Memphis roster count excludes him; Memphis dead
   money carries the protected terminated standard-contract amount.
2. Active two-way signing: salary row is excluded from payroll and roster count.
3. Two-way conversion `to an NBA Contract`: subsequent standard salary returns
   to payroll and roster count.
4. Two-way waived with partial protection: dead amount equals the calculated
   protected/earned amount, not automatically zero or full base salary.
5. Waived standard contract followed by a two-way contract elsewhere: original
   team keeps dead money, new team's two-way salary is excluded.
6. Continuing two-way contract with no same-season transaction row remains
   excluded through carried-forward or explicitly seeded annotation.
