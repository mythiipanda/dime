"use client";

export interface ZonePoint {
  zone: string;
  short: string;
  fgm: number;
  fga: number;
  share: number;
  acc: number;
  delta: number | null;
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

export function isZoneRows(rows: unknown): boolean {
  const list = unwrap(rows);
  if (!list.length) return false;
  const first = list[0];
  return (
    typeof first.zone === "string" &&
    (typeof first.SHARE === "number" || typeof first.share === "number") &&
    (typeof first.FG_PCT === "number" ||
      typeof first.eFG_PCT === "number" ||
      typeof first.FGA === "number")
  );
}

const asNum = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

const SHORT: [RegExp, string][] = [
  [/restricted/i, "Rim"],
  [/paint/i, "Paint"],
  [/mid/i, "Mid"],
  [/left.*corner/i, "LC3"],
  [/right.*corner/i, "RC3"],
  [/corner/i, "C3"],
  [/above|break/i, "ATB3"],
];

function shortZone(zone: string): string {
  for (const [re, s] of SHORT) {
    if (re.test(zone)) return s;
  }
  return zone.length > 8 ? zone.slice(0, 8) : zone;
}

export function normalizeZones(rows: unknown): ZonePoint[] {
  const pts: ZonePoint[] = [];
  for (const r of unwrap(rows)) {
    const zone = typeof r.zone === "string" ? r.zone : null;
    if (!zone) continue;
    const fga = asNum(r.FGA) ?? 0;
    const fgm = asNum(r.FGM) ?? 0;
    const share = asNum(r.SHARE) ?? asNum(r.share) ?? null;
    const acc = asNum(r.eFG_PCT) ?? asNum(r.FG_PCT) ?? null;
    if (share === null || acc === null) continue;
    pts.push({
      zone,
      short: shortZone(zone),
      fgm,
      fga,
      share: Math.max(0, Math.min(1, share)),
      acc: Math.max(0, Math.min(1.5, acc)),
      delta: asNum(r.LEAGUE_DELTA),
    });
  }
  return pts.sort((a, b) => b.share - a.share);
}

const W = 560;
const BAR_H = 152;
const PAD_L = 38;
const PAD_R = 12;
const PAD_T = 18;

export default function ZoneBars({ rows }: { rows: unknown }) {
  const pts = normalizeZones(rows);
  if (!pts.length) return null;

  const innerW = W - PAD_L - PAD_R;
  const slot = innerW / pts.length;
  const barW = Math.max(10, Math.min(26, slot / 3.4));
  const gap = Math.max(3, barW * 0.22);
  const baseY = PAD_T + BAR_H;
  const y = (v: number) => PAD_T + (1 - Math.min(1, v)) * BAR_H;

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink-black)" }}>
        Shot diet by zone
      </div>
      <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginTop: 2, marginBottom: 8 }}>
        Frequency is share of shots. Accuracy is eFG where available.
      </div>
      <svg
        viewBox={`0 0 ${W} ${baseY + 44}`}
        role="img"
        aria-label="Shot frequency versus accuracy by zone"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        {[0.25, 0.5, 0.75, 1].map((t) => (
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
              {`${Math.round(t * 100)}%`}
            </text>
          </g>
        ))}
        {pts.map((p, i) => {
          const cx = PAD_L + slot * i + slot / 2;
          const fX = cx - barW - gap / 2;
          const aX = cx + gap / 2;
          return (
            <g key={p.zone}>
              <rect
                x={fX}
                y={y(p.share)}
                width={barW}
                height={Math.max(1.5, baseY - y(p.share))}
                rx={2.5}
                fill="var(--color-soot)"
              >
                <title>{`${p.zone}: ${(p.share * 100).toFixed(1)}% of shots (${p.fgm}/${p.fga})`}</title>
              </rect>
              <rect
                x={aX}
                y={y(p.acc)}
                width={barW}
                height={Math.max(1.5, baseY - y(p.acc))}
                rx={2.5}
                fill="var(--color-cyan-signal)"
              >
                <title>{`${p.zone}: ${(p.acc * 100).toFixed(1)}% eFG${p.delta !== null ? ` (${p.delta >= 0 ? "+" : ""}${(p.delta * 100).toFixed(1)} vs league)` : ""}`}</title>
              </rect>
              <text
                x={fX + barW / 2}
                y={y(p.share) - 4}
                textAnchor="middle"
                fontSize={9.5}
                fill="var(--color-warm-gray)"
              >
                {`${Math.round(p.share * 100)}`}
              </text>
              <text
                x={aX + barW / 2}
                y={y(p.acc) - 4}
                textAnchor="middle"
                fontSize={9.5}
                fontWeight={600}
                fill="var(--color-ink-black)"
              >
                {`${Math.round(Math.min(1, p.acc) * 100)}`}
              </text>
              <text
                x={cx}
                y={baseY + 14}
                textAnchor="middle"
                fontSize={10}
                fontWeight={500}
                fill="var(--color-ink-black)"
              >
                {p.short}
              </text>
              <text
                x={cx}
                y={baseY + 27}
                textAnchor="middle"
                fontSize={9.5}
                fill="var(--color-ash-gray)"
              >
                {`${p.fgm}/${p.fga}`}
              </text>
            </g>
          );
        })}
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
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--color-soot)" }} />
          Frequency
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--color-cyan-signal)" }} />
          Accuracy
        </span>
      </div>
    </div>
  );
}
