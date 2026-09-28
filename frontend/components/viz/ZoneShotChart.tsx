"use client";

import { clamp } from "../../lib/viz";

export interface ZoneStat {
  key: string;
  short: string; // "Rim"
  label: string; // "Restricted area"
  fgm: number;
  fga: number;
  fgPct: number; // 0..1
  leagueAvg: number; // 0..1
}

// Court geometry in NBA tenths-of-feet, basket at (0, 0). Same mapping as
// the canvas ShotChart: x in [-250, 250], y in [-50, 425].
const W = 500;
const H = 475;
const sx = (x: number) => ((x + 250) / 500) * W;
const sy = (y: number) => H - ((y + 50) / 475) * H;

// Hex centers, one per shooting zone.
const CENTROIDS: Record<string, [number, number]> = {
  "restricted-area": [0, 22],
  paint: [0, 118],
  "mid-left": [-138, 122],
  "mid-center": [0, 205],
  "mid-right": [138, 122],
  "corner-3-left": [-208, 62],
  "corner-3-right": [208, 62],
  "above-break-3": [0, 305],
};

function hexPoints(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`);
  }
  return pts.join(" ");
}

const mix = (colorVar: string, amount: number) =>
  `color-mix(in oklch, ${colorVar} ${Math.round(clamp(amount, 0, 1) * 100)}%, transparent)`;

/** Zone fill: blue tint above league average, red tint below, gray near it. */
function zoneFill(deltaPp: number, hasShots: boolean): string {
  if (!hasShots) return mix("var(--color-stone-muted)", 0.35);
  if (deltaPp >= 1.5) return mix("var(--color-cyan-signal)", 0.18 + Math.min(0.45, deltaPp / 16));
  if (deltaPp <= -1.5) return mix("var(--color-ember)", 0.18 + Math.min(0.45, -deltaPp / 16));
  return mix("var(--color-stone-muted)", 0.55);
}

function CourtLines() {
  const line = "var(--color-stone-border)";
  // 3pt arc: circle around the basket, clipped by the corner lines.
  const r = 237.5;
  const ax = r * Math.cos(Math.PI * 0.05);
  const ay = r * Math.sin(Math.PI * 0.05);
  return (
    <g fill="none" stroke={line} strokeWidth={2}>
      <rect x={sx(-250)} y={sy(422)} width={500} height={sy(-50) - sy(422)} />
      <rect x={sx(-80)} y={sy(140)} width={160} height={sy(-50) - sy(140)} />
      <circle cx={sx(0)} cy={sy(0)} r={7.5} stroke="var(--color-ink-black)" />
      <path d={`M ${sx(ax)} ${sy(0) + ay} A ${r} ${r} 0 0 0 ${sx(-ax)} ${sy(0) + ay}`} />
      <line x1={sx(-220)} y1={sy(-47)} x2={sx(-220)} y2={sy(92)} />
      <line x1={sx(220)} y1={sy(-47)} x2={sx(220)} y2={sy(92)} />
    </g>
  );
}

export default function ZoneShotChart({ zones }: { zones: ZoneStat[] }) {
  const total = zones.reduce((a, z) => a + z.fga, 0);
  const maxShare = Math.max(...zones.map((z) => (total ? z.fga / total : 0)), 0.0001);
  const attempts = total.toLocaleString("en-US");

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}>
        Shot chart
      </div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 2, marginBottom: 8 }}>
        {attempts} attempts. Hex size is share of attempts. Color is accuracy vs league average.
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Shot chart by zone"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        <CourtLines />
        {zones.map((z) => {
          const c = CENTROIDS[z.key];
          if (!c) return null;
          const share = total ? z.fga / total : 0;
          const r = 20 + 24 * Math.sqrt(share / maxShare);
          const cx = sx(c[0]);
          const cy = sy(c[1]);
          const hasShots = z.fga > 0;
          const deltaPp = (z.fgPct - z.leagueAvg) * 100;
          return (
            <g key={z.key}>
              <polygon points={hexPoints(cx, cy, r)} fill={zoneFill(deltaPp, hasShots)}>
                <title>
                  {`${z.label}: ${z.fgm}/${z.fga} (${Math.round(z.fgPct * 100)}%). League average ${Math.round(z.leagueAvg * 100)}%.`}
                </title>
              </polygon>
              {hasShots && (
                <text
                  x={cx}
                  y={cy + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={500}
                  fill="var(--color-ink-black)"
                >
                  {Math.round(z.fgPct * 100)}
                </text>
              )}
              <text
                x={cx}
                y={cy + r + 15}
                textAnchor="middle"
                fontSize={10.5}
                fill="var(--color-warm-gray)"
              >
                {z.short}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
