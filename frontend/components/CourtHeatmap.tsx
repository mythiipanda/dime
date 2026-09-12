"use client";

import { useMemo, useState } from "react";

export interface ZoneData {
  zone: string;
  FGM?: number;
  FGA?: number;
  FG_PCT?: number;
  eFG_PCT?: number;
  SHARE?: number;
  share?: number;
  LEAGUE_DELTA?: number;
  a_eFG?: number;
  b_eFG?: number;
  a_fg?: number;
  b_fg?: number;
  a_share?: number;
  b_share?: number;
  edge?: string;
}

// Three-point zones read as 3P% (FG on threes), not eFG: labeling an
// all-threes zone with its 1.5x eFG next to surfaces that show 3P%
// made the same number look like two different stats (QA F23).
const isThreeZone = (name: string) => /3|corner|break/i.test(name);

interface CourtHeatmapProps {
  rows: unknown;
  meta?: {
    source?: string;
    season?: string;
    a?: string;
    b?: string;
    player?: string;
  };
  verdict?: string;
}

// Visual zone SVG path definitions mapped to NBA half-court coordinates (500 x 470)
// Baseline at bottom y=470, basket at cx=250, cy=417.5
const ZONE_PATHS: { id: string; label: string; d: string }[] = [
  {
    id: "Restricted Area",
    label: "Restricted Area",
    // Semi-circle around basket
    d: "M 210,470 L 210,430 A 40,40 0 0,1 290,430 L 290,470 Z",
  },
  {
    id: "In The Paint (Non-RA)",
    label: "Paint (Non-RA)",
    // Paint key minus the restricted area
    d: "M 170,470 L 170,280 L 330,280 L 330,470 L 290,470 L 290,430 A 40,40 0 0,0 210,430 L 210,470 Z",
  },
  {
    id: "Mid-Range",
    label: "Mid-Range",
    // 2-point territory outside paint and inside 3-point arc
    d: "M 35,470 L 35,330 A 237.5,237.5 0 0,1 465,330 L 465,470 L 330,470 L 330,280 L 170,280 L 170,470 Z",
  },
  {
    id: "Left Corner 3",
    label: "Left Corner 3",
    // Left baseline corner
    d: "M 0,470 L 0,330 L 35,330 L 35,470 Z",
  },
  {
    id: "Right Corner 3",
    label: "Right Corner 3",
    // Right baseline corner
    d: "M 465,470 L 465,330 L 500,330 L 500,470 Z",
  },
  {
    id: "Above the Break 3",
    label: "Above the Break 3",
    // Beyond 3-point arc above the corners up to half-court
    d: "M 0,330 A 237.5,237.5 0 0,1 500,330 L 500,0 L 0,0 Z",
  },
];

function findZoneRecord(list: ZoneData[], targetId: string): ZoneData | undefined {
  const norm = targetId.toLowerCase();
  return list.find((r) => {
    const z = (r.zone || "").toLowerCase();
    if (z === norm) return true;
    if (norm.includes("restricted") && z.includes("restricted")) return true;
    if (norm.includes("paint") && z.includes("paint")) return true;
    if (norm.includes("mid") && z.includes("mid")) return true;
    if (norm.includes("corner") && norm.includes("left") && z.includes("left")) return true;
    if (norm.includes("corner") && norm.includes("right") && z.includes("right")) return true;
    if (norm.includes("above") && (z.includes("above") || z.includes("break"))) return true;
    return false;
  });
}

export default function CourtHeatmap({ rows, meta, verdict }: CourtHeatmapProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const dataList = useMemo<ZoneData[]>(() => {
    if (Array.isArray(rows)) return rows as ZoneData[];
    if (typeof rows === "object" && rows !== null && "rows" in rows) {
      const inner = (rows as { rows?: unknown }).rows;
      if (Array.isArray(inner)) return inner as ZoneData[];
    }
    return [];
  }, [rows]);

  const isCompare = dataList.some((r) => r.edge !== undefined || r.a_eFG !== undefined);

  const activeRecord = useMemo(() => {
    if (!hovered) return null;
    return findZoneRecord(dataList, hovered);
  }, [hovered, dataList]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {verdict && (
        <div
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: "var(--color-ink-black)",
            background: "var(--color-stone-canvas)",
            padding: "8px 14px",
            borderRadius: 8,
            border: "1px solid var(--color-stone-border)",
          }}
        >
          {verdict}
        </div>
      )}

      <div style={{ position: "relative", width: "100%", maxWidth: 500, margin: "0 auto" }}>
        <svg
          viewBox="0 0 500 470"
          style={{
            width: "100%",
            height: "auto",
            display: "block",
            borderRadius: 10,
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
          }}
        >
          {/* Half-Court Boundary Line */}
          <rect x="1" y="1" width="498" height="468" fill="none" stroke="var(--color-stone-border)" strokeWidth="1.5" />

          {/* Interactive Zone Polygons */}
          {ZONE_PATHS.map((zp) => {
            const rec = findZoneRecord(dataList, zp.id);
            const isHover = hovered === zp.id;

            let fill = "rgba(0, 0, 0, 0.02)";
            let stroke = "var(--color-stone-border)";
            let strokeWidth = 1;

            if (isCompare && rec) {
              const edgeName = (rec.edge || "").trim();
              const nameA = (meta?.a || "Player A").trim();
              const nameB = (meta?.b || "Player B").trim();

              if (edgeName && edgeName !== "wash") {
                if (edgeName.toLowerCase().includes(nameA.toLowerCase())) {
                  fill = isHover ? "rgba(59, 166, 241, 0.45)" : "rgba(59, 166, 241, 0.24)";
                  stroke = "var(--color-cyan-signal)";
                  strokeWidth = isHover ? 2 : 1.2;
                } else if (edgeName.toLowerCase().includes(nameB.toLowerCase())) {
                  fill = isHover ? "rgba(28, 25, 23, 0.35)" : "rgba(28, 25, 23, 0.18)";
                  stroke = "var(--color-soot)";
                  strokeWidth = isHover ? 2 : 1.2;
                }
              }
            } else if (rec) {
              // Missing delta means "no baseline", never "neutral": render
              // it like no-data instead of faking a league-average zone.
              const delta = rec.LEAGUE_DELTA ?? null;
              const efg = rec.eFG_PCT ?? 0;

              if (delta === null) {
                fill = isHover ? "rgba(0, 0, 0, 0.05)" : "rgba(0, 0, 0, 0.02)";
              } else if (delta > 0.03 || efg >= 0.58) {
                fill = isHover ? "rgba(59, 166, 241, 0.42)" : "rgba(59, 166, 241, 0.22)";
                stroke = "var(--color-cyan-signal)";
                strokeWidth = isHover ? 2 : 1.2;
              } else if (delta < -0.03) {
                fill = isHover ? "rgba(168, 162, 158, 0.3)" : "rgba(168, 162, 158, 0.14)";
              } else {
                // League-average WITH data must read differently from an
                // empty zone (QA F2): subtle tint + dashed outline.
                fill = isHover ? "rgba(59, 166, 241, 0.14)" : "rgba(59, 166, 241, 0.07)";
              }
            }

            return (
              <path
                key={zp.id}
                d={zp.d}
                fill={fill}
                stroke={stroke}
                strokeWidth={strokeWidth}
                style={{
                  cursor: "pointer",
                  transition: "fill 140ms ease, stroke 140ms ease, stroke-width 140ms ease",
                }}
                onMouseEnter={() => setHovered(zp.id)}
                onMouseLeave={() => setHovered(null)}
              />
            );
          })}

          {/* Court Markings & Hardware */}
          {/* Basket Rim */}
          <circle cx="250" cy="417.5" r="7.5" fill="none" stroke="var(--color-ink-black)" strokeWidth="1.8" />
          {/* Backboard */}
          <line x1="220" y1="430" x2="280" y2="430" stroke="var(--color-ink-black)" strokeWidth="2.5" />
          {/* Free Throw Circle */}
          <circle cx="250" cy="280" r="60" fill="none" stroke="var(--color-stone-muted)" strokeWidth="1.2" strokeDasharray="4 4" />
          <circle cx="250" cy="280" r="60" fill="none" stroke="var(--color-stone-muted)" strokeWidth="1.2" clipPath="url(#top-circle)" />
          {/* Center Court Line at Top */}
          <line x1="0" y1="0" x2="500" y2="0" stroke="var(--color-stone-border)" strokeWidth="2" />
          <circle cx="250" cy="0" r="60" fill="none" stroke="var(--color-stone-border)" strokeWidth="1.2" />
        </svg>

        {/* Hover Zone Tooltip Popover */}
        {activeRecord && hovered && (
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 8,
              padding: "8px 12px",
              boxShadow: "var(--shadow-card)",
              pointerEvents: "none",
              fontSize: 12,
              lineHeight: 1.5,
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 600, color: "var(--color-ink-black)" }}>
              {activeRecord.zone || hovered}
            </div>
            {isCompare ? (
              <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 2 }}>
                <div style={{ color: "var(--color-warm-gray)" }}>
                  {meta?.a || "Player A"}:{" "}
                  {(() => {
                    const three = isThreeZone(activeRecord.zone || hovered || "");
                    const acc = three && activeRecord.a_fg != null ? activeRecord.a_fg : activeRecord.a_eFG;
                    const lbl = three && activeRecord.a_fg != null ? "3P" : "eFG";
                    return acc != null ? `${(acc * 100).toFixed(1)}% ${lbl}` : "n/a";
                  })()}{" "}
                  ({((activeRecord.a_share ?? 0) * 100).toFixed(0)}% vol)
                </div>
                <div style={{ color: "var(--color-warm-gray)" }}>
                  {meta?.b || "Player B"}:{" "}
                  {(() => {
                    const three = isThreeZone(activeRecord.zone || hovered || "");
                    const acc = three && activeRecord.b_fg != null ? activeRecord.b_fg : activeRecord.b_eFG;
                    const lbl = three && activeRecord.b_fg != null ? "3P" : "eFG";
                    return acc != null ? `${(acc * 100).toFixed(1)}% ${lbl}` : "n/a";
                  })()}{" "}
                  ({((activeRecord.b_share ?? 0) * 100).toFixed(0)}% vol)
                </div>
                {activeRecord.edge && (
                  <div style={{ fontWeight: 500, color: "var(--color-cyan-edge)", marginTop: 2 }}>
                    Advantage: {activeRecord.edge}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 2 }}>
                <div style={{ color: "var(--color-warm-gray)" }}>
                  {(() => {
                    const three = isThreeZone(activeRecord.zone || hovered || "");
                    const acc = three && activeRecord.FG_PCT != null
                      ? activeRecord.FG_PCT
                      : (activeRecord.eFG_PCT ?? activeRecord.FG_PCT);
                    const lbl = three && activeRecord.FG_PCT != null ? "3P" : "eFG";
                    return `Efficiency: ${acc != null ? ((acc * 100).toFixed(1) + "% " + lbl) : "n/a"}`;
                  })()}
                </div>
                <div style={{ color: "var(--color-warm-gray)" }}>
                  Volume: {((activeRecord.SHARE ?? activeRecord.share ?? 0) * 100).toFixed(1)}% of shots
                  {activeRecord.FGA !== undefined && ` (${activeRecord.FGM}/${activeRecord.FGA})`}
                </div>
                {activeRecord.LEAGUE_DELTA !== undefined && (
                  <div
                    style={{
                      fontWeight: 500,
                      color: activeRecord.LEAGUE_DELTA >= 0 ? "var(--color-cyan-edge)" : "var(--color-warm-gray)",
                    }}
                  >
                    vs League: {activeRecord.LEAGUE_DELTA >= 0 ? "+" : ""}
                    {(activeRecord.LEAGUE_DELTA * 100).toFixed(1)}%
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend & Provenance */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--color-ash-gray)", padding: "0 4px" }}>
        <span>Hover court zones to inspect volume and shooting efficiency</span>
        {isCompare ? (
          <div style={{ display: "flex", gap: 12 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-cyan-signal)" }} />
              {meta?.a || "Player A"}
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-soot)" }} />
              {meta?.b || "Player B"}
            </span>
          </div>
        ) : (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-cyan-signal)" }} />
            Above league average
          </span>
        )}
      </div>
    </div>
  );
}
