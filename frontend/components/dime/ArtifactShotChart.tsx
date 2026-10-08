"use client";

import type { ShotZone } from "@/lib/dime-data";

const LINE = "var(--line-strong)";

function Court() {
  return (
    <g fill="none" stroke={LINE} strokeWidth={1.5}>
      <rect x={1} y={1} width={498} height={468} />
      <line x1={0} y1={470} x2={500} y2={470} />
      {}
      <rect x={170} y={0} width={160} height={190} />
      {}
      <path d="M190,190 A60 60 0 0 1 310,190" />
      <path d="M190,190 A60 60 0 0 0 310,190" strokeDasharray="6 5" />
      {}
      <circle cx={250} cy={52.5} r={7.5} />
      <line x1={220} y1={40} x2={280} y2={40} />
      {}
      <path d="M210,52.5 A40 40 0 0 0 290,52.5" />
      {}
      <path d="M30,0 L30,142 A237.5 237.5 0 0 0 470,142 L470,0" />
    </g>
  );
}

export default function ArtifactShotChart({ zones }: { zones: ShotZone[] }) {
  const maxAtt = Math.max(...zones.map((z) => z.att));
  const px = (x: number) => (x / 100) * 500;
  const py = (y: number) => (y / 100) * 470;

  return (
    <div className="px-4 py-3">
      <svg viewBox="0 0 500 470" className="mx-auto w-full max-w-[420px]" role="img" aria-label="Shot chart">
        <rect x={0} y={0} width={500} height={470} fill="var(--surface)" />
        <Court />
        {zones.map((z, i) => {
          const r = 5 + (z.att / maxAtt) * 9;
          const opacity = 0.4 + (z.pct / 100) * 0.55;
          const cx = px(z.x);
          const cy = py(z.y);
          return (
            <g key={i}>
              <circle
                cx={cx} cy={cy} r={r}
                fill="var(--ink)" opacity={opacity}
                stroke="var(--page)" strokeWidth={2}
              />
              <text
                x={cx} y={cy + r + 11} textAnchor="middle"
                fontSize={9} fontFamily="var(--font-mono)" fill="var(--ink-2)"
              >
                {z.pct}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex items-center gap-6 font-mono text-[11px] text-ink-3">
        <span className="flex items-center gap-2">
          <span className="flex items-end gap-1.5" aria-hidden>
            <span className="rounded-full bg-ink" style={{ width: 7, height: 7 }} />
            <span className="rounded-full bg-ink" style={{ width: 11, height: 11 }} />
            <span className="rounded-full bg-ink" style={{ width: 15, height: 15 }} />
          </span>
          shots
        </span>
        <span className="flex items-center gap-2">
          <span className="flex items-center gap-1.5" aria-hidden>
            <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.4 }} />
            <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.68 }} />
            <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.95 }} />
          </span>
          fg%
        </span>
      </div>
    </div>
  );
}
