"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface ValuedPlayer {
  name: string;
  salary: number | null;
  age: number | null;
  gp: number | null;
  ppg: number | null;
  marketValueM: number | null;
  residualM: number | null;
  archetypes: string[];
}

export interface ValuedPick {
  desc: string;
  slot: number | null;
  valueM: number | null;
}

export interface TradeSide {
  team: string;
  players: ValuedPlayer[];
  picks: ValuedPick[];
  sideTotalM: number | null;
}

export interface TradeValueRows {
  sideA: TradeSide;
  sideB: TradeSide;
  fit: { team: string; timeline: string; needs: string[]; notes: string[] }[];
  verdict: { winner: string; deltaM: number | null; grades: Record<string, string>; text: string };
  dataGaps: string[];
  disclaimer: string;
}

function parsePlayer(v: unknown): ValuedPlayer | null {
  if (!isObj(v)) return null;
  const name = str(v.name);
  if (!name) return null;
  return {
    name,
    salary: num(v.salary_26_27),
    age: num(v.age),
    gp: num(v.gp),
    ppg: num(v.ppg),
    marketValueM: num(v.est_market_value_m),
    residualM: num(v.residual_m),
    archetypes: Array.isArray(v.archetypes)
      ? v.archetypes.filter((t): t is string => typeof t === "string")
      : [],
  };
}

function parsePick(v: unknown): ValuedPick | null {
  if (!isObj(v)) return null;
  const desc = str(v.desc);
  if (!desc) return null;
  return { desc, slot: num(v.est_slot), valueM: num(v.est_value_m) };
}

function parseSide(v: unknown): TradeSide | null {
  if (!isObj(v)) return null;
  const team = str(v.team);
  if (!team) return null;
  return {
    team,
    players: asList(v.players).map(parsePlayer).filter((p): p is ValuedPlayer => p !== null),
    picks: asList(v.picks).map(parsePick).filter((p): p is ValuedPick => p !== null),
    sideTotalM: num(v.side_total_m),
  };
}

export function parseTradeValue(rows: unknown): TradeValueRows | null {
  if (!isObj(rows)) return null;
  const sideA = parseSide(rows.team_a);
  const sideB = parseSide(rows.team_b);
  const verdict = isObj(rows.verdict) ? rows.verdict : null;
  if (!sideA || !sideB || !verdict) return null;
  const fit = isObj(rows.fit)
    ? Object.entries(rows.fit).map(([team, f]) => {
        const fo = isObj(f) ? f : {};
        return {
          team,
          timeline: str(fo.timeline),
          needs: Array.isArray(fo.needs)
            ? fo.needs.filter((t): t is string => typeof t === "string")
            : [],
          notes: Array.isArray(fo.notes)
            ? fo.notes.filter((t): t is string => typeof t === "string")
            : [],
        };
      })
    : [];
  const grades: Record<string, string> = {};
  if (isObj(verdict.grades)) {
    for (const [k, v] of Object.entries(verdict.grades)) {
      if (typeof v === "string") grades[k] = v;
    }
  }
  return {
    sideA,
    sideB,
    fit,
    verdict: {
      winner: str(verdict.winner) || "even",
      deltaM: num(verdict.delta_m),
      grades,
      text: str(verdict.text),
    },
    dataGaps: Array.isArray(rows.data_gaps)
      ? rows.data_gaps.filter((t): t is string => typeof t === "string")
      : [],
    disclaimer: str(rows.disclaimer),
  };
}

function moneyM(v: number | null): string {
  if (v === null) return "—";
  return `$${v.toFixed(1)}M`;
}

function SideCard({ side, grade }: { side: TradeSide; grade?: string }) {
  return (
    <div
      style={{
        flex: "1 1 240px",
        minWidth: 0,
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "12px 14px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <span
          style={{
            fontWeight: 600,
            fontSize: 15,
            color: "var(--color-ink-black)",
          }}
        >
          {side.team}
        </span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {grade && <Chip tone="accent">{grade}</Chip>}
          {side.sideTotalM !== null && (
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {moneyM(side.sideTotalM)}
            </span>
          )}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {side.players.map((p, i) => (
          <div
            key={`${p.name}-${i}`}
            style={{
              borderTop: i === 0 && side.picks.length === 0 ? "none" : "1px solid var(--color-stone-border)",
              paddingTop: i === 0 && side.picks.length === 0 ? 0 : 8,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 8,
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--color-ink-black)",
                }}
              >
                {p.name}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--color-cyan-edge)",
                  fontVariantNumeric: "tabular-nums",
                  whiteSpace: "nowrap",
                }}
              >
                {moneyM(p.marketValueM)}
              </span>
            </div>
            <div
              style={{
                fontSize: 11,
                color: "var(--color-warm-gray)",
                marginTop: 2,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {p.ppg !== null ? `${p.ppg.toFixed(1)} ppg` : "no production row"}
              {p.gp !== null ? ` · ${p.gp} gp` : ""}
              {p.salary !== null ? ` · salary $${(p.salary / 1_000_000).toFixed(1)}M` : ""}
              {p.residualM !== null
                ? ` · residual ${p.residualM >= 0 ? "+" : ""}${p.residualM.toFixed(1)}M`
                : ""}
            </div>
            {p.archetypes.length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                {p.archetypes.map((t, j) => (
                  <Chip key={j}>{t}</Chip>
                ))}
              </div>
            )}
          </div>
        ))}
        {side.picks.map((k, i) => (
          <div
            key={`pick-${i}`}
            style={{
              borderTop: "1px solid var(--color-stone-border)",
              paddingTop: 8,
              display: "flex",
              justifyContent: "space-between",
              gap: 8,
              fontSize: 12,
            }}
          >
            <span style={{ color: "var(--color-warm-gray)" }}>{k.desc}</span>
            <span
              style={{
                fontVariantNumeric: "tabular-nums",
                whiteSpace: "nowrap",
                color: "var(--color-ink-black)",
              }}
            >
              {k.slot !== null ? `~pick ${k.slot}` : ""}
              {k.valueM !== null ? ` · ${moneyM(k.valueM)}` : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TradeValueView({ rows }: { rows: unknown }) {
  const tv = parseTradeValue(rows);
  if (!tv) return null;
  const { verdict } = tv;
  const winnerLabel =
    verdict.winner === "even"
      ? "Even value"
      : `${verdict.winner} wins the value`;

  return (
    <div>
      <SectionTitle>Trade value</SectionTitle>
      <div
        style={{
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 12,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div
            style={{
              fontWeight: 600,
              fontSize: 15,
              color: "var(--color-ink-black)",
            }}
          >
            {winnerLabel}
            {verdict.deltaM !== null && verdict.winner !== "even" && (
              <span style={{ fontWeight: 400, color: "var(--color-warm-gray)" }}>
                {" "}
                by {moneyM(Math.abs(verdict.deltaM))}
              </span>
            )}
          </div>
          {verdict.text && (
            <div
              style={{
                fontSize: 12,
                color: "var(--color-warm-gray)",
                marginTop: 4,
                lineHeight: 1.55,
              }}
            >
              {verdict.text}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {Object.entries(verdict.grades).map(([team, grade]) => (
            <span
              key={team}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 13,
                fontWeight: 600,
                borderRadius: 9999,
                padding: "4px 12px",
                background:
                  grade.startsWith("A") || grade.startsWith("B")
                    ? "var(--color-ink-black)"
                    : "var(--color-stone-border)",
                color:
                  grade.startsWith("A") || grade.startsWith("B")
                    ? "var(--color-pure-white)"
                    : "var(--color-ink-black)",
              }}
            >
              {team} {grade}
            </span>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <SideCard side={tv.sideA} grade={verdict.grades[tv.sideA.team]} />
        <SideCard side={tv.sideB} grade={verdict.grades[tv.sideB.team]} />
      </div>
      {tv.fit.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <SectionTitle>Team fit</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {tv.fit.map((f) => (
              <div
                key={f.team}
                style={{
                  border: "1px solid var(--color-stone-border)",
                  borderRadius: 10,
                  padding: "10px 14px",
                  background: "var(--color-pure-white)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    flexWrap: "wrap",
                    marginBottom: 6,
                  }}
                >
                  <span
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                      color: "var(--color-ink-black)",
                    }}
                  >
                    {f.team}
                  </span>
                  {f.timeline && <Chip>{f.timeline}</Chip>}
                  {f.needs.map((n, i) => (
                    <Chip key={i}>{n.replace(/^need_/, "")}</Chip>
                  ))}
                </div>
                {f.notes.map((n, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 12,
                      color: "var(--color-warm-gray)",
                      lineHeight: 1.55,
                    }}
                  >
                    {n.replace(/need_/g, "")}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
      {tv.dataGaps.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <Caption>
            Data gaps: {tv.dataGaps.join(" · ")}
          </Caption>
        </div>
      )}
      {tv.disclaimer && (
        <div style={{ marginTop: 6 }}>
          <Caption>{tv.disclaimer}</Caption>
        </div>
      )}
    </div>
  );
}
