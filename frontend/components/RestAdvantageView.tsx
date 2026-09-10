"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface RestGame {
  date: string;
  opponent: string;
  home: boolean;
  result: string;
  rest: number | null;
  oppRest: number | null;
  diff: number | null;
}

export interface RestTeamSummary {
  team: string;
  games: number | null;
  backToBacks: number | null;
  avgRest: number | null;
  avgDiff: number | null;
  withEdge: string;
  even: string;
  atDisadvantage: string;
}

export type RestAdvantageRows =
  | { kind: "team"; team: string; summary: RestTeamSummary; games: RestGame[] }
  | { kind: "league"; teams: RestTeamSummary[] };

function parseSummary(team: string, s: Record<string, unknown>): RestTeamSummary | null {
  if (!team) return null;
  if (num(s.games) === null) return null;
  return {
    team,
    games: num(s.games) === null ? null : Math.round(num(s.games) as number),
    backToBacks:
      num(s.back_to_backs) === null ? null : Math.round(num(s.back_to_backs) as number),
    avgRest: num(s.avg_rest_days),
    avgDiff: num(s.avg_rest_diff),
    withEdge: str(s.record_with_edge),
    even: str(s.record_even),
    atDisadvantage: str(s.record_at_disadvantage),
  };
}

function parseGame(g: Record<string, unknown>): RestGame | null {
  const date = str(g.date);
  if (!date) return null;
  return {
    date,
    opponent: str(g.opponent),
    home: g.home === true,
    result: str(g.result).toUpperCase(),
    rest: num(g.rest_days),
    oppRest: num(g.opp_rest_days),
    diff: num(g.rest_diff),
  };
}

export function parseRestAdvantage(rows: unknown): RestAdvantageRows | null {
  if (!isObj(rows)) return null;
  if (Array.isArray(rows.teams)) {
    const teams: RestTeamSummary[] = [];
    for (const t of asList(rows.teams)) {
      const s = parseSummary(str(t.team), t);
      if (!s) return null;
      teams.push(s);
    }
    if (!teams.length) return null;
    return { kind: "league", teams };
  }
  if (!isObj(rows.summary)) return null;
  const team = str(rows.team);
  const summary = parseSummary(team, rows.summary);
  if (!team || !summary) return null;
  const games: RestGame[] = [];
  for (const g of asList(rows.games)) {
    const p = parseGame(g);
    if (p) games.push(p);
  }
  return { kind: "team", team, summary, games };
}

function fmtDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtRest(n: number | null): string {
  if (n === null) return "—";
  return `${Math.round(n)}d`;
}

function SummaryLine({ s }: { s: RestTeamSummary }) {
  const edge = s.avgDiff ?? 0;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
        fontVariantNumeric: "tabular-nums",
      }}
    >
      <span
        style={{ fontSize: 14, fontWeight: 600, color: "var(--color-cyan-edge)" }}
      >
        {edge > 0 ? "+" : ""}
        {edge.toFixed(2)} avg edge
      </span>
      <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
        {s.avgRest !== null ? `${s.avgRest.toFixed(1)}d avg rest` : "no rest baseline"}
        {s.backToBacks !== null ? ` · ${s.backToBacks} back-to-back` : ""}
      </span>
    </div>
  );
}

export default function RestAdvantageView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; season_type?: string };
}) {
  const parsed = parseRestAdvantage(rows);
  if (!parsed) return null;
  const season = meta?.season;
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
          {parsed.kind === "team" ? `${parsed.team} rest edge` : "League rest edge"}
        </SectionTitle>
        {season && <Chip>{season}</Chip>}
        {meta?.season_type && <Chip>{meta.season_type}</Chip>}
      </div>

      {parsed.kind === "league" ? (
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
              minWidth: 480,
              borderCollapse: "collapse",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <thead>
              <tr style={{ fontSize: 10, color: "var(--color-ash-gray)", textAlign: "left" }}>
                <th style={{ fontWeight: 500, padding: "8px 12px" }}>Team</th>
                <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>Avg edge</th>
                <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>B2B</th>
                <th style={{ fontWeight: 500, padding: "8px 12px", textAlign: "right" }}>With edge</th>
              </tr>
            </thead>
            <tbody>
              {parsed.teams.map((s, i) => (
                <tr
                  key={`${s.team}-${i}`}
                  style={{ borderTop: "1px solid var(--color-stone-border)" }}
                >
                  <td style={{ padding: "7px 12px", fontSize: 12, fontWeight: 500, color: "var(--color-ink-black)" }}>
                    {s.team}
                  </td>
                  <td
                    style={{
                      padding: "7px 8px",
                      fontSize: 13,
                      fontWeight: 600,
                      color: "var(--color-cyan-edge)",
                      textAlign: "right",
                    }}
                  >
                    {s.avgDiff !== null
                      ? `${s.avgDiff >= 0 ? "+" : ""}${s.avgDiff.toFixed(2)}`
                      : "—"}
                  </td>
                  <td style={{ padding: "7px 8px", fontSize: 12, color: "var(--color-warm-gray)", textAlign: "right" }}>
                    {s.backToBacks ?? "—"}
                  </td>
                  <td style={{ padding: "7px 12px", fontSize: 12, color: "var(--color-warm-gray)", textAlign: "right" }}>
                    {s.withEdge || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          <div style={{ marginBottom: 10 }}>
            <SummaryLine s={parsed.summary} />
          </div>
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              marginBottom: 12,
            }}
          >
            <Chip tone="accent">edge {parsed.summary.withEdge || "—"}</Chip>
            <Chip>even {parsed.summary.even || "—"}</Chip>
            <Chip>behind {parsed.summary.atDisadvantage || "—"}</Chip>
          </div>
          {parsed.games.length > 0 && (
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
                  minWidth: 480,
                  borderCollapse: "collapse",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                <thead>
                  <tr style={{ fontSize: 10, color: "var(--color-ash-gray)", textAlign: "left" }}>
                    <th style={{ fontWeight: 500, padding: "8px 12px" }}>Date</th>
                    <th style={{ fontWeight: 500, padding: "8px 8px" }}>Opp</th>
                    <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>Rest</th>
                    <th style={{ fontWeight: 500, padding: "8px 8px", textAlign: "right" }}>Opp rest</th>
                    <th style={{ fontWeight: 500, padding: "8px 12px", textAlign: "right" }}>Edge</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.games.map((g, i) => {
                    const b2b = g.rest === 0;
                    return (
                      <tr
                        key={`${g.date}-${i}`}
                        style={{ borderTop: "1px solid var(--color-stone-border)" }}
                      >
                        <td style={{ padding: "7px 12px", fontSize: 12, color: "var(--color-warm-gray)" }}>
                          {fmtDate(g.date)}
                        </td>
                        <td style={{ padding: "7px 8px", fontSize: 12, color: "var(--color-ink-black)" }}>
                          {g.home ? "vs " : "@ "}
                          {g.opponent || "—"}
                          {g.result && (
                            <span style={{ color: "var(--color-ash-gray)", marginLeft: 4 }}>
                              {g.result}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "7px 8px", fontSize: 12, color: "var(--color-warm-gray)", textAlign: "right" }}>
                          {fmtRest(g.rest)}
                          {b2b && (
                            <span style={{ marginLeft: 4 }}>
                              <Chip>B2B</Chip>
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "7px 8px", fontSize: 12, color: "var(--color-warm-gray)", textAlign: "right" }}>
                          {fmtRest(g.oppRest)}
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
                          {g.diff !== null
                            ? `${g.diff > 0 ? "+" : ""}${Math.round(g.diff)}`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      <div style={{ marginTop: 10 }}>
        <Caption>Rest = days since previous game minus 1 · edge = own rest minus opponent rest</Caption>
      </div>
    </div>
  );
}
