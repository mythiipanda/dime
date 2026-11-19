---
name: visual-artifacts
description: Select grounded generative answer components from Dime's bounded catalog (player_card, scatter, shot_chart, compare, table, chart, memo).
---

# Dime Visual Artifacts & Multimodal Output Guide

Dime empowers analysts to generate rich, interactive visual artifacts directly rendered in the user interface. This guide establishes selection criteria, schemas, and evidence grounding standards.

## 1. Artifact Selection Matrix

| Query Intent / Data Shape | Optimal Artifact | Key Features & Attributes |
|---|---|---|
| **One Player at a Glance** | `player_card` | Select identity and up to six metrics from a single actual source row. The host supplies values and declared units; no invented statistics, team names or portraits. |
| **Two Continuous Variables** (e.g., TS% vs USG%, ORAPM vs DRAPM) | `scatter` | Quadrant divisions via `xMid` & `yMid`, point labels, `highlight` flag for focal players, CSV export. |
| **Court Location & Shooting Profiles** | `shot_chart` | Court zones with attempt counts (`att`) and shooting percentages (`pct`). |
| **Head-to-Head Showdowns** (2 players or 2 teams) | `compare` | Visual bars comparing normalized metrics between entity `a` and entity `b`. |
| **Rankings, Rosters, Ledgers, Multi-Metric Lists** | `table` | Sortable columns with typed numeric formatting, source citation headers, CSV export. |
| **Time-Series, Trajectories, Multi-Game Trends** | `chart` | Line/bar series over ordered games, months, or seasons with `unit`, `xLabels`, and semantic `tone`. |
| **Executive Briefings, GM/Owner Deliverables, Multi-Section Reports** | `memo` | Titled document with headed `sections`, per-section citation `anchors`, and markdown export. |

---

## 2. Artifact Schema Specifications

### `player_card`

Use for a compact player overview, not a ranking or a replacement for the prose.
Query a row with a player name and numeric statistics first. Select fields; never
copy values into this artifact. All fields refer to the same `ref` and `row` so
identity cannot accidentally be joined to a different player's statistics.
The host rejects missing/error sources, missing columns, nonnumeric metrics and
model-supplied values or units. Null stays missing; zero stays zero. Units come
only from the source's `declared_column_semantics` or `units`; absent units are
shown as undeclared. Use source column names as labels when their meaning is
uncertain. A numeric string must be queried/cast as a number before selecting it.

```typescript
{
  kind: "player_card",
  title: "Player snapshot",
  ref: "actual-ref-from-query",
  row: 0,
  nameColumn: "player_name",
  teamColumn: "team_name",
  metrics: [
    { column: "points_per_game", label: "Points per game" },
    { column: "games", label: "Games played" }
  ]
}
```

`teamColumn` is optional. Only use it if the source row contains that text field.
Never output JSX, HTML, CSS, executable scripts, component imports or arbitrary
OpenUI programs. Dime's allowlisted components render in the existing answer
stream; choose only the components that make this question clearer, not every
component on every answer. Existing chart/table artifacts still require explicit
grounding in the prose: unlike player-card values, they are not source-resolved.

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

### `memo`
```typescript
{
  kind: "memo",
  title: "2026-27 Cap & Roster Strategy — Orlando Magic",
  subtitle: "Owner briefing",
  sections: [
    {
      heading: "Cap position",
      body: "Orlando sits $3.2M under the first apron with a locked multi-year core...",
      anchors: [{ ref: "actual-ref-from-query", row: 0, columns: ["team", "payroll"] }]
    },
    { heading: "Trade options", body: "The flexible path is aggregating mid-tier salary..." }
  ],
  footnote: "Sources: silver_salaries, silver_rapm."
}
```

Use `memo` when the deliverable is a document — an executive memo, owner
briefing, scenario playbook or strategy report — not a single visual. Each
`sections[].body` is markdown-style prose. `anchors` on a section cite source
rows exactly like block anchors and are validated the same way; cite the rows a
section's claims rest on. `subtitle` and `footnote` are optional. A memo renders
as a document card that downloads as Markdown or PDF; keep it to one memo per answer.

---

## 3. Evidence Grounding & Source Anchors

Every quantitative claim and artifact must be anchored in queried evidence within `submit_answer`:

```typescript
{
  text: "Victor Wembanyama leads the NBA in Defensive RAPM (+4.82) over 3,450 defensive possessions...",
  anchors: [
    { ref: "ref_rapm_query", row: 0, columns: ["player_name", "drapm", "possessions"] }
  ],
}
```
Pass `artifacts` beside `blocks` in `submit_answer({ blocks: [...], artifacts: [...] })`,
not inside a prose block. Selectors validate traceability to actual rows/columns;
they do not prove the prose, metric label, scope or basketball conclusion correct.
