---
name: visual-artifacts
description: Guidelines for selecting, structuring, and grounding Dime multimodal visual artifacts (scatter, shot_chart, compare, table, chart).
---

# Dime Visual Artifacts & Multimodal Output Guide

Dime empowers analysts to generate rich, interactive visual artifacts directly rendered in the user interface. This guide establishes selection criteria, schemas, and evidence grounding standards.

## 1. Artifact Selection Matrix

| Query Intent / Data Shape | Optimal Artifact | Key Features & Attributes |
|---|---|---|
| **Two Continuous Variables** (e.g., TS% vs USG%, ORAPM vs DRAPM) | `scatter` | Quadrant divisions via `xMid` & `yMid`, point labels, `highlight` flag for focal players, CSV export. |
| **Court Location & Shooting Profiles** | `shot_chart` | Court zones with attempt counts (`att`) and shooting percentages (`pct`). |
| **Head-to-Head Showdowns** (2 players or 2 teams) | `compare` | Visual bars comparing normalized metrics between entity `a` and entity `b`. |
| **Rankings, Rosters, Ledgers, Multi-Metric Lists** | `table` | Sortable columns with typed numeric formatting, source citation headers, CSV export. |
| **Time-Series, Trajectories, Multi-Game Trends** | `chart` | Line/bar series over ordered games, months, or seasons with `unit`, `xLabels`, and semantic `tone`. |

---

## 2. Artifact Schema Specifications

### `scatter`
```typescript
{
  kind: "scatter",
  title: "True Shooting % vs Usage Rate (Min. 1000 Minutes)",
  xLabel: "Usage Rate (USG%)",
  yLabel: "True Shooting (TS%)",
  xMid: 20.0,
  yMid: 57.5,
  points: [
    { label: "Nikola Jokic", x: 29.5, y: 66.8, highlight: true },
    { label: "Shai Gilgeous-Alexander", x: 32.1, y: 64.2, highlight: true },
    { label: "League Average", x: 20.0, y: 57.5 }
  ],
  footnote: "Source: silver_boxscores. Highlight indicates All-NBA first team candidates."
}
```

### `compare`
```typescript
{
  kind: "compare",
  title: "Head-to-Head: Anthony Edwards vs Devin Booker (2025-26)",
  aName: "Anthony Edwards",
  bName: "Devin Booker",
  rows: [
    { label: "Points Per Game", a: 27.8, b: 26.4 },
    { label: "True Shooting %", a: 59.2, b: 61.1 },
    { label: "RAPM", a: 3.4, b: 2.8 },
    { label: "Usage Rate %", a: 31.4, b: 29.0 }
  ]
}
```

### `table`
```typescript
{
  kind: "table",
  title: "Top 5 Defensive RAPM Leaders (2025-26)",
  columns: [
    { key: "rank", label: "Rank", numeric: true },
    { key: "player", label: "Player" },
    { key: "team", label: "Team" },
    { key: "drapm", label: "DRAPM", numeric: true },
    { key: "possessions", label: "Possessions", numeric: true }
  ],
  rows: [
    { rank: 1, player: "Victor Wembanyama", team: "SAS", drapm: 4.82, possessions: 3450 },
    { rank: 2, player: "Rudy Gobert", team: "MIN", drapm: 3.91, possessions: 3820 }
  ]
}
```

### `chart`
```typescript
{
  kind: "chart",
  title: "Scoring Progression Across 5-Game Rolling Windows (2025-26)",
  unit: "PPG",
  xLabels: ["G1-5", "G6-10", "G11-15", "G16-20", "G21-25"],
  series: [
    { name: "Rolling PPG", values: [31.2, 34.5, 36.8, 32.0, 35.4], tone: "accent" },
    { name: "Season Baseline", values: [33.9, 33.9, 33.9, 33.9, 33.9] }
  ],
  footnote: "Source: silver_boxscores. Semantic tones: accent (primary), good (positive), warn (caution)."
}
```

### `shot_chart`
```typescript
{
  kind: "shot_chart",
  title: "Shai Gilgeous-Alexander Spatial Shot Diet (2025-26)",
  zones: [
    { x: 0, y: 0, att: 380, pct: 68.4 },
    { x: 0, y: 10, att: 195, pct: 49.2 },
    { x: -14, y: 14, att: 120, pct: 46.5 },
    { x: 14, y: 14, att: 110, pct: 45.8 },
    { x: -22, y: 5, att: 45, pct: 41.2 },
    { x: 22, y: 5, att: 40, pct: 39.5 },
    { x: 0, y: 25, att: 210, pct: 37.8 }
  ],
  footnote: "Source: silver_shotchart. Field goal percentages vs volume."
}
```

---

## 3. Evidence Grounding & Source Anchors

Every quantitative claim and artifact must be anchored in queried evidence within `submit_answer`:

```typescript
{
  text: "Victor Wembanyama leads the NBA in Defensive RAPM (+4.82) over 3,450 defensive possessions...",
  anchors: [
    { ref: "ref_rapm_query", row: 0, columns: ["player_name", "drapm", "possessions"] }
  ],
  artifacts: [ ... ]
}
```
This guarantees verifiable integrity and eliminates ungrounded hallucination.
