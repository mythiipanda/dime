"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface RegSummary {
  gp: number | null;
  perGame: number | null;
  mpg: number | null;
  fgaPg: number | null;
  tsPct: number | null;
}

export interface RegDriver {
  factor: string;
  window: number | null;
  baseline: number | null;
  delta: number | null;
}

export interface RegressionRows {
  player: string;
  stat: string;
  windowN: number | null;
  window: RegSummary;
  season: RegSummary;
  career: { available: boolean; gp: number | null; perGame: number | null; note: string };
  drivers: RegDriver[];
  verdict: string;
  verdictNote: string;
}

function parseSummary(v: unknown): RegSummary {
  const o = isObj(v) ? v : {};
  return {
    gp: num(o.gp),
    perGame: num(o.per_game),
    mpg: num(o.mpg),
    fgaPg: num(o.fga_pg),
    tsPct: num(o.ts_pct),
  };
}

export function parseRegression(rows: unknown): RegressionRows | null {
  if (!isObj(rows)) return null;
  const verdict = str(rows.verdict);
  const window = parseSummary(rows.window);
  const season = parseSummary(rows.season);
  if (!verdict || window.perGame === null || season.perGame === null) return null;
  const co = isObj(rows.career) ? rows.career : {};
  return {
    player: str(rows.player),
    stat: str(rows.stat) || "PTS",
    windowN: num(rows.window_n),
    window,
    season,
    career: {
      available: co.available === true,
      gp: num(co.gp),
      perGame: num(co.per_game),
      note: str(co.note),
    },
    drivers: asList(rows.drivers).map((d) => ({
      factor: str(d.factor).replace(/_/g, " ") || "factor",
      window: num(d.window),
      baseline: num(d.baseline),
      delta: num(d.delta),
    })),
    verdict,
    verdictNote: str(rows.verdict_note),
  };
}

function fmtDelta(d: number | null, digits = 1): string {
  if (d === null) return "—";
  return `${d >= 0 ? "+" : ""}${d.toFixed(digits)}`;
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 72 }}>
      <div
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: "var(--color-ink-black)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>{label}</div>
    </div>
  );
}

export default function RegressionView({ rows }: { rows: unknown }) {
  const r = parseRegression(rows);
  if (!r) return null;
  const gap = r.window.perGame !== null && r.season.perGame !== null
    ? r.window.perGame - r.season.perGame
    : null;
  const hot = gap !== null && gap > 0;

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
          {r.player ? `${r.player} · ${r.stat}` : "Regression check"}
        </SectionTitle>
        {r.windowN !== null && <Chip>last {r.windowN} games</Chip>}
      </div>
      <div
        style={{
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 12,
        }}
      >
        <div
          style={{
            display: "inline-block",
            fontSize: 12,
            fontWeight: 600,
            borderRadius: 9999,
            padding: "3px 12px",
            marginBottom: 6,
            background:
              r.verdict === "sustainable"
                ? "var(--color-sky-wash)"
                : "var(--color-ink-black)",
            color:
              r.verdict === "sustainable"
                ? "var(--color-cyan-edge)"
                : "var(--color-pure-white)",
          }}
        >
          {r.verdict}
        </div>
        {r.verdictNote && (
          <div
            style={{
              fontSize: 12,
              color: "var(--color-warm-gray)",
              lineHeight: 1.55,
            }}
          >
            {r.verdictNote}
          </div>
        )}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 10,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "12px 14px",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-warm-gray)",
              marginBottom: 8,
            }}
          >
            Recent window
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <StatCell label={`${r.stat}/game`} value={r.window.perGame?.toFixed(1) ?? "—"} />
            <StatCell label="min" value={r.window.mpg?.toFixed(1) ?? "—"} />
            <StatCell label="TS%" value={fmtPct(r.window.tsPct)} />
          </div>
        </div>
        <div
          style={{
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "12px 14px",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--color-warm-gray)",
              marginBottom: 8,
            }}
          >
            Season baseline
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <StatCell label={`${r.stat}/game`} value={r.season.perGame?.toFixed(1) ?? "—"} />
            <StatCell label="min" value={r.season.mpg?.toFixed(1) ?? "—"} />
            <StatCell label="TS%" value={fmtPct(r.season.tsPct)} />
          </div>
        </div>
      </div>
      {gap !== null && (
        <div
          style={{
            fontSize: 13,
            color: "var(--color-ink-black)",
            marginBottom: 12,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          Gap{" "}
          <span
            style={{
              fontWeight: 600,
              color: hot ? "var(--color-cyan-edge)" : "var(--color-warm-gray)",
            }}
          >
            {fmtDelta(gap)}
          </span>{" "}
          {r.stat}/game vs season
        </div>
      )}
      {r.drivers.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <SectionTitle>Drivers</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {r.drivers.map((d, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  border: "1px solid var(--color-stone-border)",
                  borderRadius: 8,
                  padding: "8px 12px",
                  background: "var(--color-pure-white)",
                  fontSize: 12,
                }}
              >
                <span style={{ color: "var(--color-ink-black)", fontWeight: 500 }}>
                  {d.factor}
                </span>
                <span
                  style={{
                    color: "var(--color-warm-gray)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {d.window !== null ? d.window.toFixed(1) : "—"} vs{" "}
                  {d.baseline !== null ? d.baseline.toFixed(1) : "—"}
                  <span
                    style={{
                      marginLeft: 8,
                      fontWeight: 600,
                      color:
                        d.delta !== null && d.delta > 0
                          ? "var(--color-cyan-edge)"
                          : "var(--color-warm-gray)",
                    }}
                  >
                    {fmtDelta(d.delta, 2)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {r.career.available && r.career.perGame !== null && (
        <Caption>
          Career baseline: {r.career.perGame.toFixed(1)} {r.stat}/game
          {r.career.gp !== null ? ` over ${Math.round(r.career.gp)} games` : ""}
        </Caption>
      )}
      {!r.career.available && r.career.note && (
        <Caption>{r.career.note}</Caption>
      )}
    </div>
  );
}
