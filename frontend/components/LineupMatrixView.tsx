"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface LineupMatrixPair {
  aName: string;
  bName: string;
  poss: number;
  estMin: number | null;
  offA: number | null;
  defA: number | null;
  netA: number | null;
  tinySample: boolean;
  blowoutHeavy: boolean;
}

export interface LineupMatrixRows {
  pairs: LineupMatrixPair[];
}

function unwrap(rows: unknown): Record<string, unknown>[] {
  if (Array.isArray(rows)) return asList(rows);
  if (isObj(rows) && Array.isArray(rows.rows)) return asList(rows.rows);
  return [];
}

function parsePair(p: Record<string, unknown>): LineupMatrixPair | null {
  const aName = str(p.team_a_lineup);
  const bName = str(p.team_b_lineup);
  const poss = num(p.poss);
  if (!aName || !bName || poss === null) return null;
  const flags = Array.isArray(p.flags)
    ? p.flags.filter((f): f is string => typeof f === "string")
    : [];
  const low = flags.join(" ").toLowerCase();
  return {
    aName,
    bName,
    poss: Math.round(poss),
    estMin: num(p.est_minutes),
    offA: num(p.OFF_RATING_A),
    defA: num(p.DEF_RATING_A),
    netA: num(p.NET_RATING_A),
    tinySample: low.includes("tiny-sample"),
    blowoutHeavy: low.includes("blowout-heavy"),
  };
}

export function parseLineupMatrix(rows: unknown): LineupMatrixRows | null {
  const list = unwrap(rows);
  if (!list.length) return null;
  const pairs: LineupMatrixPair[] = [];
  for (const p of list) {
    const r = parsePair(p);
    if (!r) return null;
    pairs.push(r);
  }
  if (!pairs.length) return null;
  pairs.sort((a, b) => (b.estMin ?? b.poss) - (a.estMin ?? a.poss));
  return { pairs };
}

export default function LineupMatrixView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: {
    season?: string;
    team_a?: { abbr?: string };
    team_b?: { abbr?: string };
  };
}) {
  const parsed = parseLineupMatrix(rows);
  if (!parsed) return null;
  const aAbbr =
    (meta?.team_a && typeof meta.team_a === "object" && str(meta.team_a.abbr)) || "A";
  const bAbbr =
    (meta?.team_b && typeof meta.team_b === "object" && str(meta.team_b.abbr)) || "B";
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
          {aAbbr} vs {bAbbr} lineup matrix
        </SectionTitle>
        {meta?.season && <Chip>{meta.season}</Chip>}
        <Chip>
          {parsed.pairs.length} {parsed.pairs.length === 1 ? "pair" : "pairs"}
        </Chip>
      </div>
      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          overflowX: "auto",
        }}
      >
        <table
          style={{
            width: "100%",
            minWidth: 560,
            borderCollapse: "collapse",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <thead>
            <tr style={{ fontSize: 10, color: "var(--color-ash-gray)", textAlign: "left" }}>
              <th style={{ fontWeight: 500, padding: "8px 12px" }}>{aAbbr} unit</th>
              <th style={{ fontWeight: 500, padding: "8px 8px" }}>{bAbbr} unit</th>
              <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>Min</th>
              <th style={{ fontWeight: 500, padding: "8px 12px", textAlign: "right" }}>
                Net ({aAbbr})
              </th>
            </tr>
          </thead>
          <tbody>
            {parsed.pairs.map((p, i) => (
              <tr
                key={`${p.aName}-${p.bName}-${i}`}
                style={{ borderTop: "1px solid var(--color-stone-border)" }}
              >
                <td
                  style={{
                    padding: "7px 12px",
                    fontSize: 12,
                    color: "var(--color-ink-black)",
                    maxWidth: 180,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={p.aName}
                >
                  {p.aName}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    maxWidth: 180,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={p.bName}
                >
                  {p.bName}
                </td>
                <td style={{ padding: "7px 8px", fontSize: 12, color: "var(--color-warm-gray)", textAlign: "right" }}>
                  {p.estMin !== null ? p.estMin.toFixed(1) : "—"}
                  {p.tinySample && (
                    <span style={{ marginLeft: 4 }}>
                      <Chip>small</Chip>
                    </span>
                  )}
                  {p.blowoutHeavy && (
                    <span style={{ marginLeft: 4 }}>
                      <Chip>blowout</Chip>
                    </span>
                  )}
                </td>
                <td
                  style={{
                    padding: "7px 12px",
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-cyan-edge)",
                    textAlign: "right",
                  }}
                >
                  {p.netA !== null
                    ? `${p.netA >= 0 ? "+" : ""}${p.netA.toFixed(1)}`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 10 }}>
        <Caption>Shared minutes estimated from possessions (~2 per minute), not play-clock minutes</Caption>
      </div>
    </div>
  );
}
