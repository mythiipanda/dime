"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface CompDriver {
  stat: string;
  target: number | null;
  comp: number | null;
}

export interface CompRow {
  player: string;
  team: string;
  season: string;
  era: string;
  similarity: number;
  archetype: string;
  sharedArchetype: boolean;
  drivers: CompDriver[];
}

function parseDriver(v: unknown): CompDriver | null {
  if (!isObj(v)) return null;
  return {
    stat: str(v.stat) || "stat",
    target: num(v.target),
    comp: num(v.comp),
  };
}

export function parseCompsRows(rows: unknown): CompRow[] | null {
  const list = asList(rows);
  if (!list.length) return null;
  const out: CompRow[] = [];
  for (const r of list) {
    const player = str(r.PLAYER);
    const similarity = num(r.similarity);
    if (!player || similarity === null) return null;
    out.push({
      player,
      team: str(r.TEAM),
      season: str(r.season),
      era: str(r.era),
      similarity,
      archetype: str(r.archetype),
      sharedArchetype: r.shared_archetype === true,
      drivers: asList(r.drivers)
        .map(parseDriver)
        .filter((d): d is CompDriver => d !== null),
    });
  }
  return out;
}

function fmtVal(v: number | null): string {
  if (v === null) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

export default function CompsView({
  rows,
  target,
  meta,
}: {
  rows: unknown;
  target?: unknown;
  meta?: { similarity?: string; season?: string };
}) {
  const comps = parseCompsRows(rows);
  if (!comps) return null;
  const t = isObj(target) ? target : null;
  const targetName = t ? str(t.name) : "";
  const targetArchetype = t ? str(t.archetype) : "";

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <SectionTitle>
          {targetName ? `Comps for ${targetName}` : "Player comps"}
        </SectionTitle>
        {targetArchetype && <Chip tone="accent">{targetArchetype}</Chip>}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 10,
        }}
      >
        {comps.map((c, i) => (
          <div
            key={`${c.player}-${i}`}
            style={{
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 10,
              padding: "12px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <div>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  color: "var(--color-ink-black)",
                }}
              >
                {c.player}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--color-ash-gray)",
                  marginTop: 2,
                }}
              >
                {[c.team, c.season || c.era].filter(Boolean).join(" · ")}
              </div>
            </div>
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--color-warm-gray)",
                    fontWeight: 500,
                  }}
                >
                  Similarity
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--color-cyan-edge)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {c.similarity.toFixed(1)}
                </span>
              </div>
              <Bar pct={c.similarity} />
            </div>
            {c.archetype && (
              <div>
                <Chip tone={c.sharedArchetype ? "accent" : "neutral"}>
                  {c.archetype}
                </Chip>
              </div>
            )}
            {c.drivers.length > 0 && (
              <div
                style={{
                  borderTop: "1px solid var(--color-stone-border)",
                  paddingTop: 8,
                  display: "flex",
                  flexDirection: "column",
                  gap: 3,
                }}
              >
                {c.drivers.slice(0, 4).map((d, j) => (
                  <div
                    key={j}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: "var(--color-warm-gray)",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    <span>{d.stat}</span>
                    <span>
                      {fmtVal(d.target)} vs {fmtVal(d.comp)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {meta?.similarity && (
        <div style={{ marginTop: 10 }}>
          <Caption>{meta.similarity}</Caption>
        </div>
      )}
    </div>
  );
}
