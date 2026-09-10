"use client";

import { Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface ImpactBar {
  label: string;
  value: number;
}

export interface ImpactRows {
  name: string;
  team: string;
  season: string;
  estimate: number;
  method: string;
  methodology: string;
  bars: ImpactBar[];
  minutes: number | null;
  possessions: number | null;
  confidence: string;
  notes: string[];
  disclaimer: string;
}

function strList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string" && x.length > 0);
}

function unwrap(v: unknown): unknown {
  if (isObj(v) && v.rows !== undefined && isObj(v.rows)) {
    const r = v.rows;
    if (num(r.estimate_per_100) !== null) return r;
  }
  return v;
}

export function parseImpact(input: unknown): ImpactRows | null {
  const v = unwrap(input);
  if (!isObj(v)) return null;
  if (v.ok === false) return null;
  const estimate = num(v.estimate_per_100);
  if (estimate === null) return null;
  const player = isObj(v.player) ? v.player : {};
  const name = str(player.name) || str(v.player);
  if (!name) return null;
  const season = str(v.season);
  const method = str(v.method) || "estimate";
  const comp = isObj(v.components) ? v.components : {};
  const conf = isObj(v.confidence) ? v.confidence : {};
  const bars: ImpactBar[] = [];
  const box = num(comp.raptor_box_per_100);
  const onoff = num(comp.raptor_onoff_per_100);
  const lift = num(comp.measured_lift_per_100);
  const prior = num(comp.box_prior_per_100);
  if (box !== null && onoff !== null) {
    bars.push({ label: "Box", value: box });
    bars.push({ label: "On-off", value: onoff });
  } else if (lift !== null && prior !== null) {
    bars.push({ label: "On-court lift", value: lift });
    bars.push({ label: "Box prior", value: prior });
  } else if (lift !== null) {
    bars.push({ label: "On-court lift", value: lift });
  }
  if (!bars.length) return null;
  return {
    name,
    team: str(player.team),
    season,
    estimate,
    method,
    methodology: str(v.methodology),
    bars,
    minutes: num(comp.minutes),
    possessions: num(comp.measured_possessions ?? comp.possessions),
    confidence: str(conf.level) || "low",
    notes: strList(conf.notes),
    disclaimer: str(v.disclaimer),
  };
}

export default function ImpactView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string; coverage_note?: string };
}) {
  const parsed = parseImpact(rows ?? {});
  const fallback = !parsed && isObj(rows) ? parseImpact(rows) : null;
  const im = parsed ?? fallback;
  if (!im) return null;
  const maxAbs = Math.max(1, ...im.bars.map((b) => Math.abs(b.value)));
  const season = meta?.season || im.season;

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
        <SectionTitle>{im.name} impact estimate</SectionTitle>
        {im.team && <Chip>{im.team}</Chip>}
        {season && <Chip>{season}</Chip>}
        <Chip tone="accent">estimate</Chip>
      </div>

      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "14px",
          marginBottom: 8,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 11, color: "var(--color-ash-gray)", marginBottom: 4 }}>
          Net rating swing per 100
        </div>
        <div
          style={{
            fontSize: 28,
            fontWeight: 600,
            color: "var(--color-cyan-edge)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {im.estimate >= 0 ? "+" : ""}
          {im.estimate.toFixed(2)}
        </div>
        <div
          style={{
            marginTop: 6,
            fontSize: 12,
            color: "var(--color-warm-gray)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {im.minutes !== null && `${Math.round(im.minutes)} min`}
          {im.minutes !== null && im.possessions !== null && " · "}
          {im.possessions !== null && `${Math.round(im.possessions)} poss`}
          {` · ${im.confidence} confidence`}
        </div>
      </div>

      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "12px 14px",
          overflowX: "auto",
        }}
      >
        <div style={{ minWidth: 260, display: "flex", flexDirection: "column", gap: 10 }}>
          {im.bars.map((b) => (
            <div key={b.label}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                  {b.label}
                </span>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: "var(--color-ink-black)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {b.value >= 0 ? "+" : ""}
                  {b.value.toFixed(2)}
                </span>
              </div>
              <div
                style={{
                  height: 6,
                  background: "var(--color-stone-border)",
                  borderRadius: 3,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${(Math.abs(b.value) / maxAbs) * 100}%`,
                    height: "100%",
                    background: "var(--color-cyan-signal)",
                    borderRadius: 3,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--color-ash-gray)" }}>
          {im.method === "raptor_components"
            ? "Box vs on-off blend"
            : "On-court lift vs box prior"}
        </div>
      </div>

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
        {im.notes.slice(0, 2).map((n, i) => (
          <Caption key={i}>{n}</Caption>
        ))}
        {im.methodology && <Caption>{im.methodology}</Caption>}
        {meta?.coverage_note && <Caption>{meta.coverage_note}</Caption>}
      </div>
    </div>
  );
}
