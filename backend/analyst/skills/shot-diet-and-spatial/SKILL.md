---
name: shot-diet-and-spatial
description: Analyze player and team spatial shot charts, shooting zone distributions, expected value per shot, and rim pressure dynamics.
---

# Shot Diet & Spatial Analytics Playbook

This playbook establishes methodology for decomposing basketball scoring efficiency into court location zones, shot selection profiles, and expected value models.

## 1. Court Zones & Expected Value (EV)

Basketball court geography is segmented into five canonical shooting zones:

| Zone | Distance / Boundaries | Typical League FG% | Expected Value (EV) | Analytical Implication |
|---|---|---|---|---|
| **Restricted Area (RA)** | 0 to 4 feet | 64% - 68% | 1.28 - 1.36 | Highest EV zone; indicator of rim pressure and offensive creation. |
| **Paint (Non-RA)** | 4 to 14 feet | 40% - 44% | 0.80 - 0.88 | Floaters, push shots, and short hooks; inefficient unless accompanied by high FT rate. |
| **Mid-Range** | 14 feet to 3PT arc | 40% - 43% | 0.80 - 0.86 | Lower raw EV; valuable against drop coverage or late in shot clocks if taken at >46%. |
| **Corner Three** | Baseline to break (22 ft) | 37% - 40% | 1.11 - 1.20 | Shortest three-pointer; critical for spacing and drive-and-kick offenses. |
| **Above-the-Break Three** | 23.75 ft beyond arc | 34% - 36% | 1.02 - 1.08 | Primary volume perimeter shot; separates elite off-the-dribble shooters. |

### Mathematical Definitions
$$\text{Expected Value (EV)} = 2 \times \text{FG\%} \quad (\text{for 2-point attempts})$$
$$\text{Expected Value (EV)} = 3 \times \text{3P\%} \quad (\text{for 3-point attempts})$$
$$\text{Effective Field Goal Percentage (eFG\%)} = \frac{\text{FGM} + 0.5 \times \text{3PM}}{\text{FGA}}$$
$$\text{True Shooting Percentage (TS\%)} = \frac{\text{PTS}}{2 \times (\text{FGA} + 0.44 \times \text{FTA})}$$

---

## 2. Shot Diet Diagnostics

Evaluate a team or player's offensive health using three structural ratios:

1. **Rim Frequency**: $\frac{\text{FGA}_{\text{RA}}}{\text{FGA}_{\text{Total}}}$
   - Elite rim pressure: $> 35\%$.
   - Perimeter-bound offense: $< 25\%$.
2. **Three-Point Attempt Rate (3PAr)**: $\frac{\text{3PA}}{\text{FGA}_{\text{Total}}}$
   - Modern heavy-spacing offense: $> 42\%$.
   - Traditional offense: $< 32\%$.
3. **Mid-Range Frequency**: $\frac{\text{FGA}_{\text{Mid}}}{\text{FGA}_{\text{Total}}}$
   - Analytical optimization target: $< 15\%$, unless featuring high-efficiency pull-up specialists.

---

## 3. Warehouse Tools

| Tool | Answers | Reach for it when |
|---|---|---|
| `get_shot_zones` / `get_team_shot_zones` | Zone-level volume and efficiency shares for one player or a team, vs league baselines. | Any shot-diet question — the zone shares below come from these, not hand-written SQL. |
| `get_shot_compare` | Two players' zone-by-zone diet side by side. | "Compare X and Y's shot selection" — cells flag missing data instead of inventing zeros. |
| `get_zone_deltas` | One player's zone FG% vs pooled league FG% in percentage points. | "Where is X above/below average" — efficiency deltas, not volume. |
| `get_phase_shot_splits` | Zone diet, eFG, and shot-family splits (catch-and-shoot / pull-up / rim) with playoff-minus-regular deltas. | "How does their diet change in the playoffs" — the RS-vs-playoff drift is already computed. |
| `search_shots` | Shot-level rows or grouped aggregates by player, team, zone, period, clock. | Clutch/late-clock or filter-driven questions the zone aggregates don't cover. |
| `get_tracking_profile` / `get_playtype_profile` | Tracking aggregates (drives, touches, speed) and Synergy play-type frequency/PPP/percentile. | The "how" behind a zone profile — rim pressure from drives, creation type from playtypes. |
| `get_shot_chart` | Shot-chart artifact data for `submit_answer`. | When the answer needs the visual, not just the table. |

## 4. Visual Artifact Construction

Produce `shot_chart` artifacts for spatial analysis in `submit_answer`. Always express `pct` on a `0-100` percentage-point scale (e.g. `68.0`, not `0.68`):

```javascript
{
  kind: "shot_chart",
  title: "Player 2025-26 Shot Zone Efficiency vs League Average",
  zones: [
    { x: 0, y: 0, att: 320, pct: 68.0 },
    { x: 0, y: 8, att: 110, pct: 44.0 },
    { x: 0, y: 16, att: 85, pct: 42.0 },
    { x: -22, y: 4, att: 75, pct: 41.0 },
    { x: 22, y: 4, att: 80, pct: 39.0 },
    { x: 0, y: 25, att: 290, pct: 36.0 }
  ]
}
```
