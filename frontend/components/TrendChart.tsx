"use client";

export interface RaptorPoint {
  season: string;
  total: number | null;
  offense: number | null;
  defense: number | null;
  war: number | null;
}

function unwrap(rows: unknown): Record<string, unknown>[] {
  const inner =
    rows && typeof rows === "object" && !Array.isArray(rows) && "rows" in rows
      ? (rows as { rows?: unknown }).rows
      : rows;
  if (!Array.isArray(inner)) return [];
  return inner.filter(
    (r): r is Record<string, unknown> => typeof r === "object" && r !== null,
  );
}

export function isRaptorRows(rows: unknown): boolean {
  const list = unwrap(rows);
  if (!list.length) return false;
  const first = list[0];
  return "RAPTOR" in first && "WAR" in first && "SEASON" in first;
}

const asNum = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

export function normalizeRaptor(rows: unknown): RaptorPoint[] {
  const pts: RaptorPoint[] = [];
  for (const r of unwrap(rows)) {
    const season = typeof r.SEASON === "string" ? r.SEASON : null;
    if (!season) continue;
    const total = asNum(r.RAPTOR);
    const offense = asNum(r.RAPTOR_O);
    const defense = asNum(r.RAPTOR_D);
    if (total === null && offense === null && defense === null) continue;
    pts.push({ season, total, offense, defense, war: asNum(r.WAR) });
  }
  return pts.sort((a, b) => (a.season < b.season ? -1 : a.season > b.season ? 1 : 0));
}

const W = 560;
const H = 230;
const PAD_L = 38;
const PAD_R = 12;
const PAD_T = 14;
const PAD_B = 30;

const shortSeason = (s: string) =>
  s.length >= 7 ? `'${s.slice(2, 4)}` : s;

function pathFor(
  pts: RaptorPoint[],
  pick: (p: RaptorPoint) => number | null,
  x: (i: number) => number,
  y: (v: number) => number,
): string {
  let d = "";
  pts.forEach((p, i) => {
    const v = pick(p);
    if (v === null) return;
    d += `${d ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  return d;
}

export default function TrendChart({
  rows,
  playerName,
}: {
  rows: unknown;
  playerName?: string;
}) {
  const pts = normalizeRaptor(rows);
  if (!pts.length) return null;

  const vals: number[] = [];
  for (const p of pts) {
    for (const v of [p.total, p.offense, p.defense]) {
      if (v !== null) vals.push(v);
    }
  }
  if (!vals.length) return null;
  let lo = Math.min(...vals, 0);
  let hi = Math.max(...vals, 0);
  if (hi - lo < 1) {
    hi += 0.5;
    lo -= 0.5;
  }
  const pad = (hi - lo) * 0.08;
  hi += pad;
  lo -= pad;

  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const x = (i: number) => PAD_L + (pts.length === 1 ? innerW / 2 : (i * innerW) / (pts.length - 1));
  const y = (v: number) => PAD_T + (1 - (v - lo) / (hi - lo)) * innerH;

  const ticks = [hi - pad, 0, lo + pad];
  const zeroY = y(0);

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink-black)" }}>
        {playerName ? `${playerName} RAPTOR trajectory` : "RAPTOR trajectory"}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginTop: 2, marginBottom: 8 }}>
        Total plus offense and defense split by season
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="RAPTOR trajectory by season"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD_L}
              x2={W - PAD_R}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--color-stone-border)"
              strokeWidth={1}
            />
            <text
              x={PAD_L - 6}
              y={y(t) + 3.5}
              textAnchor="end"
              fontSize={10}
              fill="var(--color-ash-gray)"
            >
              {t.toFixed(1)}
            </text>
          </g>
        ))}
        <line
          x1={PAD_L}
          x2={W - PAD_R}
          y1={zeroY}
          y2={zeroY}
          stroke="var(--color-stone-muted)"
          strokeWidth={1}
        />
        <path
          d={pathFor(pts, (p) => p.defense, x, y)}
          fill="none"
          stroke="var(--color-warm-gray)"
          strokeWidth={1.5}
          strokeDasharray="5 3"
        />
        <path
          d={pathFor(pts, (p) => p.offense, x, y)}
          fill="none"
          stroke="var(--color-soot)"
          strokeWidth={1.5}
        />
        <path
          d={pathFor(pts, (p) => p.total, x, y)}
          fill="none"
          stroke="var(--color-cyan-signal)"
          strokeWidth={2.25}
        />
        {pts.map((p, i) =>
          p.total !== null ? (
            <circle
              key={p.season}
              cx={x(i)}
              cy={y(p.total)}
              r={3}
              fill="var(--color-cyan-signal)"
              stroke="var(--color-pure-white)"
              strokeWidth={1.25}
            >
              <title>{`${p.season}: RAPTOR ${p.total.toFixed(1)} (O ${p.offense?.toFixed(1) ?? "n/a"}, D ${p.defense?.toFixed(1) ?? "n/a"}, WAR ${p.war?.toFixed(1) ?? "n/a"})`}</title>
            </circle>
          ) : null,
        )}
        {pts.map((p, i) => (
          <text
            key={`l-${p.season}`}
            x={x(i)}
            y={H - 8}
            textAnchor="middle"
            fontSize={10}
            fill="var(--color-warm-gray)"
          >
            {shortSeason(p.season)}
          </text>
        ))}
      </svg>
      <div
        style={{
          display: "flex",
          gap: 14,
          marginTop: 6,
          fontSize: 11,
          color: "var(--color-warm-gray)",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 16, height: 2.5, borderRadius: 2, background: "var(--color-cyan-signal)" }} />
          Total
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 16, height: 2, borderRadius: 2, background: "var(--color-soot)" }} />
          Offense
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span
            style={{
              width: 16,
              height: 2,
              borderRadius: 2,
              background:
                "repeating-linear-gradient(90deg, var(--color-warm-gray) 0 4px, transparent 4px 7px)",
            }}
          />
          Defense
        </span>
      </div>
      <div style={{ fontSize: 10, color: "var(--color-ash-gray)", marginTop: 4 }}>
        Hover a point for WAR and exact splits.
      </div>
    </div>
  );
}
