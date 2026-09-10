"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface LineupStatUnit {
  name: string;
  estMin: number | null;
  poss: number | null;
  gp: number | null;
  off: number | null;
  def: number | null;
  net: number | null;
  plusMinus: number | null;
  best: boolean;
  blowout: boolean;
}

export interface LineupStatsRows {
  units: LineupStatUnit[];
}

function unwrap(rows: unknown): Record<string, unknown>[] {
  if (Array.isArray(rows)) return asList(rows);
  if (isObj(rows) && Array.isArray(rows.rows)) return asList(rows.rows);
  return [];
}

function parseUnit(u: Record<string, unknown>): LineupStatUnit | null {
  const name = str(u.GROUP_NAME);
  if (!name) return null;
  const off = num(u.OFF_RATING);
  const def = num(u.DEF_RATING);
  const net = num(u.NET_RATING);
  const poss = num(u.poss);
  const estMin = num(u.EST_MIN);
  if (off === null && def === null && net === null && poss === null && estMin === null)
    return null;
  const flags = Array.isArray(u.flags)
    ? u.flags.filter((f): f is string => typeof f === "string")
    : [];
  return {
    name,
    estMin,
    poss: poss === null ? null : Math.round(poss),
    gp: num(u.GP) === null ? null : Math.round(num(u.GP) as number),
    off,
    def,
    net,
    plusMinus: num(u.PLUS_MINUS),
    best: u.is_best_net_unit === true,
    blowout: flags.some((f) => f.toLowerCase().startsWith("blowout")),
  };
}

export function parseLineupStats(rows: unknown): LineupStatsRows | null {
  const list = unwrap(rows);
  if (!list.length) return null;
  const units: LineupStatUnit[] = [];
  for (const u of list) {
    const p = parseUnit(u);
    if (!p) return null;
    units.push(p);
  }
  if (!units.length) return null;
  units.sort((a, b) => (b.poss ?? b.estMin ?? 0) - (a.poss ?? a.estMin ?? 0));
  return { units };
}

function fmtNet(n: number | null): string {
  if (n === null) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}`;
}

export default function LineupStatsView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; team?: string; sample_floor?: string };
}) {
  const parsed = parseLineupStats(rows);
  if (!parsed) return null;
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
        <SectionTitle>Lineup stats</SectionTitle>
        {meta?.team && <Chip>{meta.team}</Chip>}
        {meta?.season && <Chip>{meta.season}</Chip>}
        {meta?.sample_floor && <Chip>{meta.sample_floor}</Chip>}
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
            minWidth: 520,
            borderCollapse: "collapse",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <thead>
            <tr
              style={{
                fontSize: 10,
                color: "var(--color-ash-gray)",
                textAlign: "left",
              }}
            >
              <th style={{ fontWeight: 500, padding: "8px 12px" }}>Unit</th>
              <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>Min</th>
              <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>ORtg</th>
              <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>DRtg</th>
              <th style={{ fontWeight: 500, padding: "8px 12px", textAlign: "right" }}>Net</th>
            </tr>
          </thead>
          <tbody>
            {parsed.units.map((u, i) => (
              <tr
                key={`${u.name}-${i}`}
                style={{ borderTop: "1px solid var(--color-stone-border)" }}
              >
                <td
                  style={{
                    padding: "7px 12px",
                    fontSize: 12,
                    color: "var(--color-ink-black)",
                    maxWidth: 220,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={u.name}
                >
                  {u.name}
                  {u.best && (
                    <span style={{ marginLeft: 6 }}>
                      <Chip tone="accent">best net</Chip>
                    </span>
                  )}
                  {u.blowout && (
                    <span style={{ marginLeft: 6 }}>
                      <Chip>blowout</Chip>
                    </span>
                  )}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    textAlign: "right",
                  }}
                >
                  {u.estMin !== null ? u.estMin.toFixed(1) : "—"}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    textAlign: "right",
                  }}
                >
                  {u.off !== null ? u.off.toFixed(1) : "—"}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    textAlign: "right",
                  }}
                >
                  {u.def !== null ? u.def.toFixed(1) : "—"}
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
                  {fmtNet(u.net)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 10 }}>
        <Caption>
          {parsed.units.length} {parsed.units.length === 1 ? "unit" : "units"} by minutes
          · net per 100 possessions
        </Caption>
      </div>
    </div>
  );
}
