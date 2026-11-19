"use client";

export type ScatterPoint = {
  label: string;
  x: number;
  y: number;
  highlight?: boolean;
  tone?: "ink" | "muted" | "accent";
};

function formatTick(val: number): string {
  if (Number.isInteger(val)) return String(val);
  const rounded = Math.round(val * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

export default function ArtifactScatter({
  xLabel,
  yLabel,
  points,
  height = 220,
  xMid,
  yMid,
  footnote,
}: {
  xLabel: string;
  yLabel: string;
  points: ScatterPoint[];
  height?: number;
  xMid?: number;
  yMid?: number;
  footnote?: string;
}) {
  if (!points || points.length === 0) return null;

  const W = 600;
  const H = height;
  const PAD_LEFT = 48;
  const PAD_BOTTOM = 36;
  const PAD_TOP = 20;
  const PAD_RIGHT = 32;

  const plotLeft = PAD_LEFT;
  const plotRight = W - PAD_RIGHT;
  const plotTop = PAD_TOP;
  const plotBottom = H - PAD_BOTTOM;

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  if (xMid !== undefined) xs.push(xMid);
  if (yMid !== undefined) ys.push(yMid);

  const rawMinX = Math.min(...xs);
  const rawMaxX = Math.max(...xs);
  const rawMinY = Math.min(...ys);
  const rawMaxY = Math.max(...ys);

  const xSpan = rawMaxX - rawMinX || 1;
  const ySpan = rawMaxY - rawMinY || 1;
  const padX = xSpan * 0.08;
  const padY = ySpan * 0.08;

  const minX = rawMinX - padX;
  const maxX = rawMaxX + padX;
  const minY = rawMinY - padY;
  const maxY = rawMaxY + padY;

  const scaleX = (x: number) =>
    plotLeft + ((x - minX) / (maxX - minX)) * (plotRight - plotLeft);
  const scaleY = (y: number) =>
    plotBottom - ((y - minY) / (maxY - minY)) * (plotBottom - plotTop);

  const yMidVal = (rawMinY + rawMaxY) / 2;
  const yTicks = [rawMaxY, yMidVal, rawMinY];

  const xMidVal = (rawMinX + rawMaxX) / 2;
  const xTicks = [rawMinX, xMidVal, rawMaxX];

  return (
    <div className="px-4 py-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-2 w-full"
        role="img"
        aria-label={`${xLabel} vs ${yLabel} scatter plot`}
      >
        {/* Subtle grid lines & Y ticks */}
        {yTicks.map((t, idx) => (
          <g key={`y-tick-${idx}`}>
            <line
              x1={plotLeft}
              x2={plotRight}
              y1={scaleY(t)}
              y2={scaleY(t)}
              stroke="var(--line)"
              strokeWidth={1}
            />
            <text
              x={plotLeft - 6}
              y={scaleY(t) + 3}
              textAnchor="end"
              fontSize={9}
              fontFamily="var(--font-mono)"
              fill="var(--ink-3)"
            >
              {formatTick(t)}
            </text>
          </g>
        ))}

        {/* X ticks */}
        {xTicks.map((t, idx) => (
          <g key={`x-tick-${idx}`}>
            <line
              x1={scaleX(t)}
              x2={scaleX(t)}
              y1={plotTop}
              y2={plotBottom}
              stroke="var(--line)"
              strokeWidth={1}
              strokeDasharray="2 4"
            />
            <text
              x={scaleX(t)}
              y={plotBottom + 13}
              textAnchor="middle"
              fontSize={9}
              fontFamily="var(--font-mono)"
              fill="var(--ink-3)"
            >
              {formatTick(t)}
            </text>
          </g>
        ))}

        {/* Quadrant crosshairs */}
        {xMid !== undefined && (
          <line
            x1={scaleX(xMid)}
            x2={scaleX(xMid)}
            y1={plotTop}
            y2={plotBottom}
            stroke="var(--ink-3)"
            strokeWidth={1.25}
            strokeDasharray="4 3"
          />
        )}
        {yMid !== undefined && (
          <line
            x1={plotLeft}
            x2={plotRight}
            y1={scaleY(yMid)}
            y2={scaleY(yMid)}
            stroke="var(--ink-3)"
            strokeWidth={1.25}
            strokeDasharray="4 3"
          />
        )}

        {/* Axes lines */}
        <line
          x1={plotLeft}
          x2={plotLeft}
          y1={plotTop}
          y2={plotBottom}
          stroke="var(--line)"
          strokeWidth={1.5}
        />
        <line
          x1={plotLeft}
          x2={plotRight}
          y1={plotBottom}
          y2={plotBottom}
          stroke="var(--line)"
          strokeWidth={1.5}
        />

        {/* X Axis Label */}
        <text
          x={(plotLeft + plotRight) / 2}
          y={H - 6}
          textAnchor="middle"
          fontSize={10}
          fontWeight={500}
          fontFamily="var(--font-mono)"
          fill="var(--ink-2)"
        >
          {xLabel}
        </text>

        {/* Y Axis Label */}
        <text
          transform="rotate(-90)"
          x={-((plotTop + plotBottom) / 2)}
          y={12}
          textAnchor="middle"
          fontSize={10}
          fontWeight={500}
          fontFamily="var(--font-mono)"
          fill="var(--ink-2)"
        >
          {yLabel}
        </text>

        {/* Points */}
        {points.map((p, idx) => {
          const cx = scaleX(p.x);
          const cy = scaleY(p.y);
          const isHighlight = Boolean(p.highlight);
          const tone = p.tone ?? (isHighlight ? "ink" : "muted");
          const fill =
            tone === "accent"
              ? "var(--ink)"
              : tone === "muted"
                ? "var(--ink-3)"
                : "var(--ink)";
          const r = isHighlight ? 4.5 : 3.5;
          const isNearRight = cx > plotRight - 60;
          const textX = isNearRight ? cx - (r + 5) : cx + (r + 5);
          const textAnchor = isNearRight ? "end" : "start";

          return (
            <g key={`${p.label}-${idx}`}>
              <circle
                cx={cx}
                cy={cy}
                r={r}
                fill={fill}
                stroke="var(--surface)"
                strokeWidth={1.5}
                opacity={isHighlight ? 1 : 0.85}
              >
                <title>{`${p.label}: (${p.x}, ${p.y})`}</title>
              </circle>
              {isHighlight && (
                <text
                  x={textX}
                  y={cy + 3.5}
                  textAnchor={textAnchor}
                  fontSize={10}
                  fontWeight={600}
                  fontFamily="var(--font-mono)"
                  fill="var(--ink)"
                >
                  {p.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {footnote && (
        <div className="mt-1 font-mono text-[11px] text-ink-3">{footnote}</div>
      )}
    </div>
  );
}
