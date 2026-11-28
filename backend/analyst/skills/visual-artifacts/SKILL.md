---
name: visual-artifacts
description: Select grounded generative answer components from Dime's bounded catalog (player_card, team_card, scatter, shot_chart, compare, table, chart, memo) — and emit inline JSON chart specs when an ask names a structured payload or a "kind" like line/bar.

# Dime Visual Artifacts & Multimodal Output Guide

Dime empowers analysts to generate rich, interactive visual artifacts directly rendered in the user interface. This guide establishes selection criteria, schemas, and evidence grounding standards.

## 1. Artifact Selection Matrix

| Query Intent / Data Shape | Optimal Artifact | Key Features & Attributes |
|---|---|---|
| **One Player at a Glance** | `player_card` | Select identity and up to six metrics from a single actual source row. The host supplies values and declared units; no invented statistics, team names or portraits. |
| **One Team at a Glance** | `team_card` | Team name plus up to six headline metrics from one row; optional sections each resolve their own source row for roster, payroll vs cap/aprons, four factors, lineups, injuries or picks, with per-section provenance. |
| **Two Continuous Variables** (e.g., TS% vs USG%, ORAPM vs DRAPM) | `scatter` | Quadrant divisions via `xMid` & `yMid`, point labels, `highlight` flag for focal players, CSV copy. |
| **Court Location & Shooting Profiles** | `shot_chart` | Court zones with attempt counts (`att`) and shooting percentages (`pct`). |
| **Head-to-Head Showdowns** (2 players or 2 teams) | `compare` | Visual bars comparing normalized metrics between entity `a` and entity `b`. |
| **Rankings, Rosters, Ledgers, Multi-Metric Lists** | `table` | Sortable columns with typed numeric formatting, source footnotes, CSV copy. |
| **Time-Series, Trajectories, Multi-Game Trends** | `chart` | Line/bar series over ordered games, months, or seasons with `unit`, `xLabels`, and semantic `tone`. `variant:"bar"` renders a ranked leaderboard; `marks`, `annotations`, `labelValues`, `xLabel`/`yLabel`, `subtitle` cover threshold lines, callouts and axis labels. |
| **Executive Briefings, GM/Owner Deliverables, Multi-Section Reports** | `memo` | Titled document with headed `sections`, per-section citation `anchors`, and markdown export. |

---

## 1b. Inline JSON specs when the ask names one

When the task explicitly asks for a structured JSON chart payload (for example a spec with `"kind": "line"`), embed the spec as a JSON code block directly in the answer text — do not substitute a catalog artifact. Catalog artifacts use their own `kind` values (`chart`, not `line`), so they do not satisfy a spec-shaped ask. Multi-series trend example:

```json
{
  "kind": "line",
  "title": "Nuggets net rating peaked in 2023-24",
  "xLabels": ["2015-16", "2016-17", "2017-18"],
  "series": [
    { "name": "offensive rating", "values": [105.1, 106.2, 107.3] },
    { "name": "defensive rating", "values": [108.4, 107.5, 106.6] },
    { "name": "net rating", "values": [-3.3, -1.3, 0.7] }
  ],
  "xLabel": "Season",
  "yLabel": "Rating per game"
}
```

Values come from the queried rows only — one entry per xLabel per series, no gaps.

Ranked-list bar example (top-N asks with `"kind": "bar"`):

```json
{
  "kind": "bar",
  "title": "SGA leads 2024-25 scoring at 32.7 PPG",
  "xLabels": ["Gilgeous-Alexander", "Antetokounmpo", "Jokic"],
  "series": [
    { "name": "points per game", "values": [32.7, 30.4, 29.6] }
  ],
  "xLabel": "Player",
  "yLabel": "PPG",
  "marks": [{ "value": 27.6, "label": "top-10 mean" }]
}
```

The inline spec and catalog artifacts coexist — you may emit BOTH: the inline spec satisfies the explicit spec contract, catalog artifacts (`chart`, `table`) drive the rendered UI. The submission audit reads inline `"kind"` keys in answer blocks, so a correct inline spec is never flagged as missing artifacts. When the ask names `"kind": "line"` or `"kind": "bar"` verbatim, copy that exact kind string — `chart` does not satisfy it.

---

## 2. Artifact Schema Specifications

`submit_answer` checks artifacts before accepting them. Typed table, compare, chart,
scatter and shot_chart payloads that reach schema validation are rejected with
field-level errors when malformed; player_card and team_card are validated when
source-resolved, and memo sections/anchors are checked. Kinds outside this catalog
or without usable data are dropped and reported as warnings. Fix the artifact and
resubmit.

### `player_card`

Use for a compact player overview, not a ranking or a replacement for the prose.
Query a row with a player name and numeric statistics first. Select fields; never
copy values into this artifact. Header fields refer to the same `ref` and `row` so
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

Optional `sections` extends the card into a multi-source snapshot — each section
selects from its own `ref`/`row`, so contract, season line, impact, zones and
injury status can each cite a different queried source. Identity stays on the
header row only; a section never carries a name column. Per section the host
resolves values, declared units and provenance from that source's result:
capability, origin (`live`, `warehouse` or `undeclared`), `warehouse_id` for
warehouse-origin rows, live-source identities for live-origin rows, dataset,
season, as-of and SQL when declared. `metrics` selects numbers (finite or null);
`fields` selects text (e.g. status, contract type). Up to 6 sections, each with
1-6 metrics and/or fields; a section with neither is rejected.

```typescript
{
  kind: "player_card",
  title: "Player snapshot",
  ref: "ref-identity",
  row: 0,
  nameColumn: "player_name",
  teamColumn: "team",
  metrics: [{ column: "pts", label: "PTS" }, { column: "ts_pct", label: "TS%" }],
  sections: [
    { label: "Contract", ref: "ref-contract", row: 0,
      fields: [{ column: "contract_type", label: "Deal" }],
      metrics: [{ column: "salary", label: "Salary" }] },
    { label: "Impact rank", ref: "ref-rapm", row: 0,
      metrics: [{ column: "rapm", label: "RAPM" }, { column: "rank", label: "Rank" }] },
    { label: "Availability", ref: "ref-injury", row: 0,
      fields: [{ column: "status", label: "Status" }] }
  ]
}
```
Never output JSX, HTML, CSS, executable scripts, component imports or arbitrary
OpenUI programs. Dime's allowlisted components render in the existing answer
stream; choose only the components that make this question clearer, not every
component on every answer. Existing chart/table artifacts still require explicit
grounding in the prose: unlike player-card values, they are not source-resolved.

### `team_card`

Use for a compact team overview — record, net rating, cap sheet status — not a
standings list or roster dump (use `table` for those). Same selector contract as
`player_card`: `nameColumn` selects the team name from the header `ref`/`row`,
`metrics` selects up to six headline numbers, and optional `sections` extend the
card across sources — roster size, payroll vs cap and aprons, four factors and
rank, top lineup, injuries, future picks — each citing its own `ref`/`row` with
per-section provenance. One `ref`/`row` selects one source row, so multi-row
sections like a roster or pick list belong in `table`, not `fields`.
For the canonical `get_team_four_factors` source, the row exposes uppercase
top-level keys; use `EFG_PCT`, `TOV_PCT`, `ORB_PCT` and `FT_RATE` exactly as
returned.

```typescript
{
  kind: "team_card",
  title: "Team snapshot",
  ref: "ref-team",
  row: 0,
  nameColumn: "team_name",
  metrics: [
    { column: "wins", label: "W" }, { column: "losses", label: "L" },
    { column: "net_rating", label: "Net Rtg" }
  ],
  sections: [
    { label: "Payroll", ref: "ref-cap", row: 0,
      metrics: [{ column: "total_salary", label: "Payroll" },
                { column: "first_apron_room", label: "Apron room" }] },
    { label: "Four factors", ref: "ref-4f", row: 0,
      metrics: [{ column: "EFG_PCT", label: "eFG%" },
                { column: "TOV_PCT", label: "TOV%" },
                { column: "ORB_PCT", label: "ORB%" },
                { column: "FT_RATE", label: "FTr" }] },
    { label: "Injuries", ref: "ref-inj", row: 0,
      fields: [{ column: "injury_summary", label: "Out/DTD" }] },
    { label: "Draft capital", ref: "ref-picks", row: 0,
      fields: [{ column: "pick_summary", label: "Picks" }] }
  ]
}
```

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
  footnote: "Source: silver_hist_player_seasons. Highlight indicates All-NBA first team candidates."
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
  title: "Top 5 RAPM Leaders (2025-26)",
  columns: [
    { key: "rank", label: "Rank", numeric: true },
    { key: "player", label: "Player" },
    { key: "team", label: "Team" },
    { key: "rapm", label: "RAPM", numeric: true },
    { key: "possessions", label: "Possessions", numeric: true }
  ],
  rows: [
    { rank: 1, player: "Victor Wembanyama", team: "SAS", rapm: 4.82, possessions: 3450 },
    { rank: 2, player: "Rudy Gobert", team: "MIN", rapm: 3.91, possessions: 3820 }
  ],
  footnote: "Source: silver_rapm. n=5 leaders shown of 12 qualified."
}
```

### `chart`
Default `variant` is `"line"`. Use `variant: "bar"` for ranked leaderboards and
any x-axis of distinct entities (players, teams, lineups) rather than a sequence —
it renders horizontal bars sorted in the order you provide, so order values
descending before submitting. Style the answer the way a public NBA analyst
post would: the `title` states the takeaway in a few words, `subtitle` carries
the metric/scope context, `marks` draw labeled threshold lines (league mean,
max-slot cap, playoff line), `annotations` call out the single observation the
task asks for (biggest drop, best, first below half), `labelValues` prints each
value on the bars/points, and `xLabel`/`yLabel` name the axes.
```typescript
{
  kind: "chart",
  title: "Franz's four-month slide sits below the floor",
  subtitle: "Catch & shoot eFG% by month · Magic wings, 2025-26",
  variant: "line",
  unit: "eFG%",
  xLabels: ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"],
  xLabel: "Month",
  yLabel: "Catch & shoot eFG%",
  series: [
    { name: "Franz Wagner", values: [0.512, 0.498, 0.451, 0.432, 0.418, 0.407, 0.396], tone: "accent" },
    { name: "Team wings avg", values: [0.481, 0.479, 0.476, 0.474, 0.473, 0.471, 0.470], tone: "muted" }
  ],
  marks: [{ value: 0.466, label: "Wing floor (league median)" }],
  annotations: [{ index: 4, text: "First month below the team average — slope steepens here" }],
  labelValues: false,
  footnote: "Source: silver_shots · 7 months · 82 games · eFG 0.512 → 0.396"
}
```
For a leaderboard bar chart, pass one series and pre-sorted `xLabels`:
```typescript
{
  kind: "chart",
  title: "Five spots clear a full max slot",
  variant: "bar",
  unit: "$M",
  xLabels: ["DET", "CHI", "IND", "OKC", "ORL", "SAS", "ATL"],
  xLabel: "Practical cap space ($M)",
  series: [{ name: "2026 practical space", values: [74.2, 63.1, 58.7, 55.9, 54.6, 48.2, 41.5], tone: "accent" }],
  marks: [{ value: 54.45, label: "Max-slot threshold" }],
  annotations: [{ index: 4, text: "ORL is the last team that clears a full max" }],
  labelValues: true,
  footnote: "Source: silver_cap_room · 7 teams shown of 30"
}
```

### `shot_chart`
Call `get_shot_chart` (player or team, season, playoffs, opponent) to fill `zones`
from `silver_shots`; pass its `x`/`y`/`att`/`pct` through and forward `makes`
and `delta` (its `delta_pp`) when present. `makes` renders a `makes/att`
caption; `delta` colors each region vs the league average.
```typescript
{
  kind: "shot_chart",
  title: "Shai Gilgeous-Alexander Shot Diet vs League (2025-26)",
  zones: [
    { x: 0, y: 4, att: 380, makes: 260, pct: 68.4, delta: 8.1, label: "rim-C" },
    { x: -14, y: 14, att: 120, makes: 56, pct: 46.5, delta: 3.4, label: "long_mid-L" },
    { x: 22, y: 5, att: 40, makes: 16, pct: 39.5, delta: -1.2, label: "corner_3-R" },
    { x: 0, y: 25, att: 210, makes: 79, pct: 37.8, delta: 1.6, label: "atb_3-C" }
  ],
  footnote: "Source: silver_shots via get_shot_chart. Dot size is attempts; color is FG% vs league."
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
  text: "Victor Wembanyama leads the NBA in RAPM (+4.82) over 3,450 possessions...",
  anchors: [
    { ref: "ref_rapm_query", row: 0, columns: ["name", "rapm", "possessions"] }
  ],
}
```
Pass `artifacts` beside `blocks` in `submit_answer({ blocks: [...], artifacts: [...] })`,
not inside a prose block. Selectors validate traceability to actual rows/columns;
they do not prove the prose, metric label, scope or basketball conclusion correct.

---

## 4. Headline Numbers Live Inside the Payload

When the task names headline or scope numbers — month/game counts, denominators,
cohort sizes, first/last endpoint values — every emitted artifact must carry
them inside its own payload. A number stated only in prose blocks, or only in
the series it is derived from, does not count as delivered inside the artifact.

- `table`: put scope counts and endpoint values in `footnote` (e.g.
  `"n=11 eligible · 14625.2 min · mean AST/36 3.62 · mean TOV/36 1.93"`), and/or
  include summary and denominator rows (e.g. `Months: 7`, `Season games: 82`,
  first/last rows) alongside the detail rows. `title` is the wrong home — a
  number that only lives in the title does not count as artifact data.
- `chart`: put scope counts and endpoint values in `footnote` — it renders and
  stays inside the payload (e.g.
  `"7 months · 82 games · eFG 0.464 → 0.502 · TOV/g 16.5 → 13.0"`).
  The series arrays alone do not make a count or a summary value visible.
- `scatter`/`shot_chart`: same rule — scope counts belong in `footnote`.
- `compare`: headline values go in their own `rows` entries.
- `memo`: each section's `body` states its own figures; `footnote` carries scope.

Before submitting, re-check each artifact dict: could a reader recover every
reported headline number from that payload alone? If not, add the
missing rows or the footnote line rather than hoping the prose covers it.

## 5. Analyst Chart Craft — What Separates a Take From a Plot

A chart that names its axes is not an analysis. The craft rules below are what
twitter-analyst-grade visuals do; apply them to every visual artifact.

- **Headline-as-take**: the title states the finding ("Corner campers", "The
  math doesn't work on Lonzo"), not the axis names ("FGA vs TS%"). A chart that
  only describes its axes forfeits the take to the reader.
- **Honest axes**: zero-baseline where the shape implies magnitude, consistent
  scales in comparisons, declared units. A truncated axis that flatters a delta
  is a credibility hit, not a visual trick.
- **Annotation over decoration**: one callout carries the take — `highlight` on
  the named point, a `xMid`/`yMid` midline, a threshold line — not five. The
  reader should find the conclusion without reading the axes.
- **Percentile context**: frame marks against the cohort (percentile lines,
  league-average reference, median midline), not raw values alone. A point is
  only interesting relative to its pool.
- **Glyph vocabulary**: beeswarm-style scatter for distributions, shot_chart
  zones for spatial claims, rolling lines for trends, slope-shaped comparisons
  for before/after, quadrant scatters (midlines on both axes) for
  PPP-vs-volume or efficiency-vs-usage takes.
- **Density discipline**: leader charts show ~8-15 rows, not 60. Aggregate or
  filter to the sample the take needs, and state the qualifying threshold in
  `footnote` (the field exists; use it).
- **Identity anchors**: highlight the specific entity the take is about in a
  different visual weight — a labeled outlier, a highlighted bar — so the
  reader can find the subject instantly.
