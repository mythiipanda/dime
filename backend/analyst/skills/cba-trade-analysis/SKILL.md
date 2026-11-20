---
name: cba-trade-analysis
description: Evaluate NBA trade feasibility, salary matching brackets, first and second luxury tax apron restrictions, and roster construction rules under the 2023 CBA.
---

# 2023 CBA Trade & Cap Analysis Playbook

This playbook outlines the structural trade rules, luxury tax apron thresholds, salary matching math, and draft pick restrictions enacted under the 2023 NBA Collective Bargaining Agreement (CBA).

## 0. Mechanism Selection (decide before computing)

Every legality question starts with one branch — pick the mechanism before any math:

1. **Tier each side first.** Compute each team's payroll from `silver_salaries` (`SUM(SALARY)` per `TEAM` for the relevant `_season`) and place it in the tier ladder (Under Cap / Over Cap Non-Tax / Taxpayer / First Apron / Second Apron) using the thresholds stated in the question. Evaluate **both** sides of a proposed trade independently — a deal legal for one side can be illegal for the other.
2. **Under-cap teams absorb into cap space, not matching bands.** If the team finishes the trade at or under the salary cap, it may take back more salary than it sends out — the ceiling is `outgoing + cap_room` (room = cap − payroll). Do not apply the percentage bands to a team with room; conversely do not claim "cap space" for an over-cap team — it uses the matching rules instead. Absorption trades (sending a player to a team with open room for minimal salary back) are legal whenever the receiving side stays under the cap after.
3. **Apron and taxpayer teams use salary matching, never cap room.** First Apron teams may take back at most 100% of outgoing; Second Apron teams additionally cannot aggregate multiple salaries for one larger contract. The bands below apply to non-apron over-cap teams.

## 1. Cap & Apron Structure

The 2023 CBA establishes progressive financial thresholds that impose both monetary tax penalties and severe roster construction restrictions:

- **Salary Cap**: Baseline team payroll threshold.
- **Luxury Tax Level**: Approximately 121.5% of the Salary Cap.
- **First Apron**: Approximately $7M above the Luxury Tax Level.
- **Second Apron**: Approximately $17.5M above the Luxury Tax Level.

### Hard Cap Triggers
A team becomes hard-capped at the **First Apron** if it:
1. Uses the Non-Taxpayer Mid-Level Exception (NT-MLE).
2. Uses the Bi-Annual Exception (BAE).
3. Acquires a player via sign-and-trade.

A team becomes hard-capped at the **Second Apron** if it:
1. Uses the Taxpayer Mid-Level Exception (TP-MLE).

---

## 2. Salary Matching Bands in Trades

When teams are above the salary cap, outgoing salary dictates the maximum allowable incoming salary:

### Non-Taxpayer Teams
- **Outgoing $\le \$7.5\text{M}$**: Allowed incoming is $200\% \text{ of outgoing} + \$250,000$.
- **Outgoing $\$7.5\text{M} - \$29.0\text{M}$**: Allowed incoming is $\text{outgoing} + \$7,500,000$.
- **Outgoing $> \$29.0\text{M}$**: Allowed incoming is $125\% \text{ of outgoing} + \$250,000$.

### First Apron Teams
- **Strict $100\%$ Matching**: A First Apron team cannot take back more salary than it sends out ($100\%$ match max).
- **No Traded Player Exceptions (TPE)** generated in prior seasons may be used to take on more salary than sent out.

### Second Apron Teams (Operational Deadlock)
Teams operating at or above the Second Apron face the most punitive roster restrictions in NBA history:
1. **No Aggregation**: Cannot combine two or more player contracts to trade for a single player making a higher salary.
2. **No Outgoing Cash**: Cannot include cash considerations in any transaction.
3. **No Trade Exceptions**: Cannot use TPEs generated from previous single-player transactions.
4. **Frozen First-Round Picks**:
   - The team's first-round draft pick 7 years in the future is immediately **frozen** and cannot be traded.
   - If a team finishes the season in the Second Apron in 2 of the subsequent 4 years, that frozen pick is automatically demoted to the end of the first round (pick #30 overall), regardless of regular season record.
5. **Buyout Market Restriction**: Cannot sign a player waived in-season whose pre-waiver salary exceeded the Non-Taxpayer Mid-Level Exception.

---

## 2.5 Solving for Minimum Outgoing Salary

When a question asks for the *smallest* outgoing package that legalizes a target incoming salary, invert the matching bands — work top-down, since each band's range implies its own outgoing floor:

- **100% apron match**: `outgoing ≥ incoming`. The ceiling and floor coincide; any outgoing below incoming fails outright (and a Second Apron team additionally cannot combine contracts to reach it).
- **High band (> $29M outgoing)**: `outgoing ≥ (incoming − $250,000) / 1.25`. Valid only if the solution lands above $29M.
- **Mid band ($7.5M–$29M)**: `outgoing ≥ incoming − $7,500,000`. Valid only if the solution lands inside the band.
- **Low band (≤ $7.5M)**: `outgoing ≥ (incoming − $250,000) / 2`. Valid only if the solution lands at or under $7.5M.

Compute the floor under each band that can contain the answer, then take the smallest valid one — plus the cap-space route: if outgoing can be zero and `incoming ≤ cap_room`, no matching is needed at all. When comparing rule vintages (e.g. historical vs current matching), state which rule set you applied and why the question's stipulated year controls it.

Worked example: to take back $35M as a non-apron over-cap team — high-band floor is $(35.0 − 0.25)/1.25 = $27.8M`, which is *below* $29M so the high band doesn't apply; mid-band floor is $35.0 − 7.5 = $27.5M`, valid inside the band → minimum outgoing is **$27.5M**.

---

## 3. Contract Extensions & Valuations

- **Designated Veteran Player Extension (Supermax / DVPE)**:
  - 8-9 seasons of service with original team or acquired on rookie scale.
  - Requires All-NBA selection (most recent season or 2 of prior 3), MVP (prior 3 seasons), or DPOY (prior season or 2 of prior 3).
  - Starts at $35\%$ of the salary cap with $8\%$ annual raises.
- **Standard Veteran Extensions**:
  - Up to $140\%$ of the previous year's salary or $140\%$ of the estimated average player salary, whichever is greater.

---

## 4. Analytical Deliverables & Artifacts

- **Trade Check Summaries**: Use `compare` artifacts to contrast incoming and outgoing player profiles, salaries, and net ratings.
- **Roster Cap Ledger**: Use `table` artifacts displaying player salaries, luxury tax tiers, and team apron room/deficit.
