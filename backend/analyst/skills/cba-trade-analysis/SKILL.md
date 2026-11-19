---
name: cba-trade-analysis
description: Evaluate NBA trade feasibility, salary matching brackets, first and second luxury tax apron restrictions, and roster construction rules under the 2023 CBA.
---

# 2023 CBA Trade & Cap Analysis Playbook

This playbook outlines the structural trade rules, luxury tax apron thresholds, salary matching math, and draft pick restrictions enacted under the 2023 NBA Collective Bargaining Agreement (CBA).

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
