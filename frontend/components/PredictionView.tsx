"use client";

import { Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface PredictionRows {
  home: string;
  away: string;
  gameDate: string;
  venue: string;
  homeProb: number;
  awayProb: number;
  homeCi: [number, number] | null;
  awayCi: [number, number] | null;
  homeScore: number;
  awayScore: number;
  total: number;
  totalCi: [number, number] | null;
  marginCi: [number, number] | null;
  nSims: number | null;
  seed: number | null;
  pace: number | null;
  homeCourtPts: number | null;
  note: string;
  assumptions: string[];
  methodology: string[];
  limitations: string[];
}

function strList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter(
    (x): x is string => typeof x === "string" && x.length > 0,
  );
}

function pairNums(v: unknown): [number, number] | null {
  if (!Array.isArray(v) || v.length < 2) return null;
  const a = num(v[0]);
  const b = num(v[1]);
  return a === null || b === null ? null : [a, b];
}

function unwrap(v: unknown): unknown {
  if (Array.isArray(v)) return v.length ? v[0] : null;
  return v;
}

export function parsePrediction(input: unknown): PredictionRows | null {
  let v = unwrap(input);
  if (isObj(v) && !isObj(v.matchup) && !isObj(v.estimate) && v.rows !== undefined) {
    v = unwrap(v.rows);
  }
  if (!isObj(v)) return null;
  const matchup = isObj(v.matchup) ? v.matchup : null;
  const estimate = isObj(v.estimate) ? v.estimate : null;
  if (!matchup || !estimate) return null;
  const home = str(matchup.home);
  const away = str(matchup.away);
  if (!home || !away) return null;
  const probs = isObj(estimate.win_prob) ? estimate.win_prob : null;
  const homeProb = probs ? num(probs[home]) : null;
  const awayProb = probs ? num(probs[away]) : null;
  if (homeProb === null || awayProb === null) return null;
  const scores = isObj(estimate.projected_score) ? estimate.projected_score : null;
  const homeScore = scores ? num(scores[home]) : null;
  const awayScore = scores ? num(scores[away]) : null;
  if (homeScore === null || awayScore === null) return null;
  const total = num(estimate.projected_total);
  if (total === null) return null;
  const inputs = isObj(v.inputs) ? v.inputs : {};
  const ci = isObj(estimate.win_prob_ci90) ? estimate.win_prob_ci90 : null;
  return {
    home,
    away,
    gameDate: str(matchup.game_date),
    venue: str(matchup.venue),
    homeProb,
    awayProb,
    homeCi: ci ? pairNums(ci[home]) : null,
    awayCi: ci ? pairNums(ci[away]) : null,
    homeScore,
    awayScore,
    total,
    totalCi: pairNums(estimate.total_ci90),
    marginCi: pairNums(estimate.margin_ci90),
    nSims: num(inputs.n_sims),
    seed: num(inputs.seed),
    pace: num(inputs.game_pace),
    homeCourtPts: num(inputs.home_court_pts),
    note: str(estimate.note),
    assumptions: strList(v.assumptions),
    methodology: strList(v.methodology),
    limitations: strList(v.limitations),
  };
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function ciPct(ci: [number, number] | null): string {
  if (!ci) return "";
  return `90% CI ${pct(ci[0])}–${pct(ci[1])}`;
}

function ProbRow({
  abbr,
  prob,
  ci,
  accent,
}: {
  abbr: string;
  prob: number;
  ci: [number, number] | null;
  accent: boolean;
}) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 8,
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
          {abbr}
        </span>
        <span
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: accent
              ? "var(--color-cyan-edge)"
              : "var(--color-ink-black)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {pct(prob)}
        </span>
      </div>
      <Bar pct={prob * 100} color={accent ? undefined : "var(--color-stone-muted)"} />
      {ci && (
        <div
          style={{
            fontSize: 11,
            color: "var(--color-ash-gray)",
            marginTop: 4,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {ciPct(ci)}
        </div>
      )}
    </div>
  );
}

export default function PredictionView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string };
}) {
  const p = parsePrediction(rows);
  if (!p) return null;
  const favHome = p.homeProb >= p.awayProb;
  const simLine = [
    p.nSims !== null ? `${Math.round(p.nSims).toLocaleString()} simulations` : "",
    p.seed !== null ? `seed ${Math.round(p.seed)}` : "",
    p.pace !== null ? `pace ${p.pace.toFixed(1)}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  const extras = [...p.assumptions, ...p.methodology, ...p.limitations];

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 4,
        }}
      >
        <SectionTitle>
          {p.away} @ {p.home}
        </SectionTitle>
        {meta?.season && <Chip>{meta.season}</Chip>}
      </div>
      {[p.gameDate, p.venue].filter(Boolean).length > 0 && (
        <div
          style={{
            fontSize: 12,
            color: "var(--color-warm-gray)",
            marginBottom: 12,
          }}
        >
          {[p.gameDate, p.venue].filter(Boolean).join(" · ")}
        </div>
      )}
      <div
        style={{
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 10,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--color-warm-gray)",
            marginBottom: 10,
          }}
        >
          Win probability
        </div>
        <ProbRow abbr={p.away} prob={p.awayProb} ci={p.awayCi} accent={!favHome} />
        <div style={{ marginBottom: 0 }}>
          <ProbRow abbr={p.home} prob={p.homeProb} ci={p.homeCi} accent={favHome} />
        </div>
      </div>
      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "12px 16px",
          marginBottom: 10,
        }}
      >
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--color-warm-gray)",
            marginBottom: 6,
          }}
        >
          Projected score
        </div>
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: "var(--color-ink-black)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {p.away} {p.awayScore.toFixed(1)} – {p.homeScore.toFixed(1)} {p.home}
        </div>
        <div
          style={{
            fontSize: 12,
            color: "var(--color-warm-gray)",
            marginTop: 4,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          Total {p.total.toFixed(1)}
          {p.totalCi ? ` (90%: ${p.totalCi[0].toFixed(1)}–${p.totalCi[1].toFixed(1)})` : ""}
        </div>
        {p.marginCi && (
          <div
            style={{
              fontSize: 11,
              color: "var(--color-ash-gray)",
              marginTop: 2,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            Margin 90%: {p.marginCi[0].toFixed(1)} to {p.marginCi[1].toFixed(1)} (home minus
            away)
          </div>
        )}
      </div>
      {simLine && <Caption>{simLine}</Caption>}
      {p.note && (
        <div style={{ marginTop: 4 }}>
          <Caption>{p.note}</Caption>
        </div>
      )}
      {extras.length > 0 && (
        <details
          style={{
            fontSize: 11,
            color: "var(--color-warm-gray)",
            marginTop: 10,
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 500 }}>
            Methodology and assumptions
          </summary>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              marginTop: 6,
              lineHeight: 1.55,
            }}
          >
            {extras.map((t, i) => (
              <div key={i}>{t}</div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
