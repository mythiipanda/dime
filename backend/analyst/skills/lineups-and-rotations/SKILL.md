---
name: lineups-and-rotations
description: Analyze 5-man lineup net ratings with sample-size caveats, possession-weighted aggregation, 2-man WOWY matrices, non-star survival minutes, and playoff rotation tightening.
---

# Lineups, WOWY & Rotation Analytics Playbook

Use this playbook for 5-man lineup evaluation, two-player With-Or-Without-You (WOWY) synergy splits, bench survival analysis, and playoff rotation tightening.

## 1. Sample-Size Caveats on 5-Man Lineups

Raw 5-man unit net ratings are dominated by shooting luck (especially opponent 3P% variance) at small minute or possession counts:
- **Minimum qualification floors**: Treat 5-man lineups under `100` minutes (~200 possessions) as exploratory noise; require `>= 200` minutes (or `>= 400` possessions) for strong regular-season conclusions, and report exact minutes/possessions alongside every lineup rating.
- **Possession-weighted aggregation**: Never take an unweighted mean of lineup net ratings across units. Weight offensive, defensive, and net ratings by possessions:
  $$\text{NetRtg}_{\text{agg}} = 100 \times \left(\frac{\sum \text{PTS}_{\text{for}}}{\sum \text{Poss}_{\text{off}}} - \frac{\sum \text{PTS}_{\text{against}}}{\sum \text{Poss}_{\text{def}}}\right)$$
- **Opponent 3P% luck check**: When a lineup posts an extreme DRTG, check opponent 3P% and rim frequency allowed before attributing it solely to scheme or personnel.

## 2. 2-Man WOWY Matrix Construction

When evaluating fit between two focal players $A$ and $B$, construct the full $2 \times 2$ partition of team possessions:

| State | Meaning | Key Question |
|---|---|---|
| **$A \text{ ON}, B \text{ ON}$** | Shared minutes | Do their usage profiles and spacing amplify each other? |
| **$A \text{ ON}, B \text{ OFF}$** | $A$ leads solo / staggered | Can $A$ sustain offensive creation without $B$'s gravity? |
| **$A \text{ OFF}, B \text{ ON}$** | $B$ leads solo / staggered | **Non-star survival check**: does the offense collapse or survive? |
| **$A \text{ OFF}, B \text{ OFF}$** | Deep bench / garbage time | Baseline noise filter; check score-margin leverage. |

Use `get_wowy` or `get_on_off`, or query stint/possession tables in `run_python` to compute possession-weighted Net Rating, ORTG, DRTG, TS%, and Pace across all four quadrants.

## 3. Non-Star Survival Minutes & Staggering

- Evaluate how a team performs in the **star-off** and **second-star-stagger** segments (`A ON, B OFF` and `A OFF, B ON`) excluding garbage time.
- Identify which role players bridge offensive creation (assists per 100, rim pressure) and defensive floor (DRTG, defensive rebounding %) when the primary initiator sits.

## 4. Playoff Rotation Tightening

Regular-season depth often masks playoff vulnerabilities:
- Top rotations compress from 9–10 players in the regular season to **7–8 core players** in competitive playoff series, with star minutes rising from ~34–36 MPG to ~39–43 MPG.
- Compare regular-season vs playoff lineup concentration (top-3 lineup share of total minutes, starter vs bench minute split) using `get_lineup_stats`, `get_stint_timeline`, and `get_rotation_check`.
- Present 5-man lineup comparisons in a `table` artifact (including `MIN`, `POSS`, `ORTG`, `DRTG`, `NET_RTG`) and 2-man WOWY splits in a `compare` or `table` artifact.
