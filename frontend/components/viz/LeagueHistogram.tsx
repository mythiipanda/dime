"use client";

import { histogramBins, ordinal, percentileRank } from "../../lib/viz";

const W = 340;
const BAR_H = 64;
const PAD_X = 4;
const BASE_Y = 76;

export default function LeagueHistogram({
  label,
  values,
  playerValue,
  format,
  note,
}: {
  label: string;
  values: number[]; // league-wide values for the same stat
  playerValue: number;
  format: (v: number) => string;
  note?: string;
}) {
  const bins = histogramBins(values, 22);
  if (!bins.length) return null;
  const maxCount = Math.max(...bins.map((b) => b.count), 1);
  const slot = (W - PAD_X * 2) / bins.length;
  const barW = Math.max(2, slot - 2);

  const sorted = [...values].sort((a, b) => a - b);
  const rank = percentileRank(sorted, playerValue);
  const beaten = Math.round(rank * values.length);

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>{label}</span>
        <span style={{ fontSize: 13, color: "var(--color-ink-black)" }}>
          <span style={{ fontSize: 18, fontWeight: 500 }}>{format(playerValue)}</span>
          <span style={{ color: "var(--color-ash-gray)", marginLeft: 8 }}>
            {ordinal(beaten)} of {values.length}
          </span>
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${BASE_Y + 20}`}
        role="img"
        aria-label={`${label} league distribution`}
        style={{ width: "100%", height: "auto", display: "block", marginTop: 6 }}
      >
        {bins.map((b, i) => {
          const h = Math.max(2, (b.count / maxCount) * BAR_H);
          const isPlayer = playerValue >= b.lo && (playerValue < b.hi || i === bins.length - 1);
          return (
            <rect
              key={i}
              x={PAD_X + slot * i + (slot - barW) / 2}
              y={BASE_Y - h}
              width={barW}
              height={h}
              rx={1.5}
              fill={isPlayer ? "var(--color-soot)" : "var(--color-stone-muted)"}
            >
              <title>{`${b.count} players between ${format(b.lo)} and ${format(b.hi)}`}</title>
            </rect>
          );
        })}
        <text x={PAD_X} y={BASE_Y + 14} fontSize={10} fill="var(--color-ash-gray)">
          {format(bins[0].lo)}
        </text>
        <text
          x={W - PAD_X}
          y={BASE_Y + 14}
          textAnchor="end"
          fontSize={10}
          fill="var(--color-ash-gray)"
        >
          {format(bins[bins.length - 1].hi)}
        </text>
      </svg>
      {note && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>{note}</div>
      )}
    </div>
  );
}
