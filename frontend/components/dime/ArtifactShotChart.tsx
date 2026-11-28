"use client";

import type { ShotZone } from "@/lib/dime-data";

const LINE = "var(--ink-3)";

function Court() {
  return (
    <g fill="none" stroke={LINE} strokeWidth={1.5}>
      <rect x={1} y={1} width={498} height={468} />
      <line x1={0} y1={470} x2={500} y2={470} />
      <rect x={170} y={0} width={160} height={190} />
      <path d="M190,190 A60 60 0 0 1 310,190" />
      <path d="M190,190 A60 60 0 0 0 310,190" strokeDasharray="6 5" />
      <circle cx={250} cy={52.5} r={7.5} />
      <line x1={220} y1={40} x2={280} y2={40} />
      <path d="M210,52.5 A40 40 0 0 0 290,52.5" />
      <path d="M30,0 L30,142 A237.5 237.5 0 0 0 470,142 L470,0" />
    </g>
  );
}

function mapCoordinates(zones: ShotZone[]): { cx: number; cy: number; att: number; pct: number; makes?: number; delta?: number; label?: string }[] {
  if (zones.length === 0) return [];
  const minX = Math.min(...zones.map((z) => z.x));
  const maxX = Math.max(...zones.map((z) => z.x));
  const maxY = Math.max(...zones.map((z) => z.y));

  if (minX < 0 || (maxX <= 30 && maxY <= 45 && minX >= -30)) {
    return zones.map((z) => ({
      cx: Math.max(15, Math.min(485, 250 + z.x * 10)),
      cy: Math.max(15, Math.min(455, 52.5 + z.y * 10)),
      att: z.att, pct: z.pct, makes: z.makes, delta: z.delta, label: z.label,
    }));
  }

  if (minX <= -30 || maxX > 100 || maxY > 100) {
    return zones.map((z) => ({
      cx: Math.max(15, Math.min(485, 250 + z.x)),
      cy: Math.max(15, Math.min(455, 52.5 + z.y)),
      att: z.att, pct: z.pct, makes: z.makes, delta: z.delta, label: z.label,
    }));
  }

  return zones.map((z) => ({
    cx: (z.x / 100) * 500,
    cy: (z.y / 100) * 470,
    att: z.att, pct: z.pct, makes: z.makes, delta: z.delta, label: z.label,
  }));
}

export default function ArtifactShotChart({
  zones,
  footnote,
}: {
  zones: ShotZone[];
  footnote?: string;
}) {
  if (!zones || zones.length === 0) return null;
  const mapped = mapCoordinates(zones);
  const maxAtt = Math.max(...zones.map((z) => z.att), 1);

  return (
    <div className="px-4 py-3">
      <svg viewBox="0 0 500 470" className="mx-auto w-full max-w-[420px]" role="img" aria-label="Shot chart">
        <rect x={0} y={0} width={500} height={470} fill="var(--surface)" />
        <Court />
        {mapped.map((z, i) => {
          const r = 5 + (z.att / maxAtt) * 9;
          const delta = z.delta;
          const fill = delta === undefined
            ? "var(--ink)"
            : delta >= 2
              ? "var(--green)"
              : delta <= -2
                ? "var(--orange)"
                : "var(--ink)";
          const opacity = 0.4 + (z.pct / 100) * 0.55;
          const caption = z.makes !== undefined ? `${z.makes}/${z.att} · ${z.pct}` : `${z.pct}`;
          return (
            <g key={i}>
              <circle
                cx={z.cx} cy={z.cy} r={r}
                fill={fill} opacity={opacity}
                stroke="var(--page)" strokeWidth={2}
              />
              <text
                x={z.cx} y={z.cy + r + 11} textAnchor="middle"
                fontSize={9} fontFamily="var(--font-mono)" fill="var(--ink-2)"
              >
                {caption}
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
        {mapped.some((z) => z.delta !== undefined) ? (
          <span className="flex items-center gap-2">
            <span className="flex items-center gap-1.5" aria-hidden>
              <span className="rounded-full" style={{ width: 11, height: 11, background: "var(--orange)", opacity: 0.7 }} />
              <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.6 }} />
              <span className="rounded-full" style={{ width: 11, height: 11, background: "var(--green)", opacity: 0.7 }} />
            </span>
            vs league fg%
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <span className="flex items-center gap-1.5" aria-hidden>
              <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.4 }} />
              <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.68 }} />
              <span className="rounded-full bg-ink" style={{ width: 11, height: 11, opacity: 0.95 }} />
            </span>
            fg%
          </span>
        )}
      </div>
      {footnote && <div className="mt-1 font-mono text-[11px] text-ink-3">{footnote}</div>}
    </div>
  );
}
