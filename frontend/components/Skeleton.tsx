"use client";

export default function Skeleton({
  lines = 3,
  widths,
  label,
}: {
  lines?: number;
  widths?: number[];
  label?: string;
}) {
  const fallback = [90, 70, 55, 80];
  const ws = widths && widths.length ? widths : fallback;
  const rows = Array.from(
    { length: Math.max(1, Math.min(8, lines)) },
    (_, i) => ws[i % ws.length],
  );
  return (
    <div
      role="status"
      aria-label={label ?? "Loading"}
      style={{ width: "100%", padding: "4px 0" }}
    >
      {label && (
        <div
          style={{
            fontSize: 12,
            color: "var(--color-ash-gray)",
            marginBottom: 8,
          }}
        >
          {label}
        </div>
      )}
      {rows.map((w, i) => (
        <div
          key={i}
          className="skeleton-row skeleton-pulse"
          style={{ width: `${w}%` }}
        />
      ))}
    </div>
  );
}
