"use client";

import { asList, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface RotationPlayer {
  name: string;
  gp: number | null;
  mpg: number | null;
  diff: number | null;
  cached: boolean;
}

export interface RotationUnit {
  name: string;
  poss: number | null;
  net: number | null;
  best: boolean;
  flags: string[];
}

export interface RotationCloser {
  name: string;
  gp: number | null;
  w: number | null;
  l: number | null;
}

export interface RotationRows {
  team: string;
  season: string;
  units: number | null;
  starterShare: number | null;
  starterDiff: number | null;
  benchDiff: number | null;
  core: RotationPlayer[];
  bench: RotationPlayer[];
  fringe: RotationPlayer[];
  mostUsed: RotationUnit | null;
  closing: RotationUnit[];
  flags: string[];
  clutchNote: string;
  closers: RotationCloser[];
}

function parsePlayer(v: unknown): RotationPlayer | null {
  if (!isObj(v)) return null;
  const name = str(v.PLAYER);
  if (!name) return null;
  return {
    name,
    gp: num(v.GP),
    mpg: num(v.MPG),
    diff: num(v.DIFF),
    cached: v.CACHED === true,
  };
}

function parseUnit(v: unknown): RotationUnit | null {
  if (!isObj(v)) return null;
  const name = str(v.GROUP_NAME);
  if (!name) return null;
  return {
    name,
    poss: num(v.poss),
    net: num(v.NET_RATING),
    best: v.is_best_net_unit === true,
    flags: Array.isArray(v.flags)
      ? v.flags.filter((f): f is string => typeof f === "string")
      : [],
  };
}

export function parseRotation(rows: unknown): RotationRows | null {
  if (!isObj(rows)) return null;
  const teamObj = isObj(rows.team) ? rows.team : null;
  const team =
    (teamObj ? str(teamObj.abbrev) : "") || (teamObj ? String(teamObj.id ?? "") : "");
  const tiers = isObj(rows.tiers) ? rows.tiers : null;
  if (!team || !tiers) return null;
  if (
    !Array.isArray(tiers.core) ||
    !Array.isArray(tiers.bench) ||
    !Array.isArray(tiers.fringe)
  )
    return null;
  if (!Array.isArray(rows.thin_flags)) return null;
  const split = isObj(rows.starter_bench_split) ? rows.starter_bench_split : {};
  const coverage = isObj(rows.coverage) ? rows.coverage : {};
  const clutch = isObj(rows.clutch_context) ? rows.clutch_context : {};
  const closers: RotationCloser[] = [];
  for (const c of asList(clutch.closers)) {
    const name = str(c.PLAYER);
    if (!name) continue;
    closers.push({ name, gp: num(c.GP), w: num(c.W), l: num(c.L) });
  }
  const mu = isObj(rows.most_used_unit) ? parseUnit(rows.most_used_unit) : null;
  return {
    team,
    season: str(coverage.season),
    units: num(coverage.units),
    starterShare: num(split.starter_min_share),
    starterDiff: num(split.starter_avg_diff),
    benchDiff: num(split.bench_avg_diff),
    core: asList(tiers.core)
      .map(parsePlayer)
      .filter((p): p is RotationPlayer => p !== null),
    bench: asList(tiers.bench)
      .map(parsePlayer)
      .filter((p): p is RotationPlayer => p !== null),
    fringe: asList(tiers.fringe)
      .map(parsePlayer)
      .filter((p): p is RotationPlayer => p !== null),
    mostUsed: mu,
    closing: asList(rows.closing_candidates)
      .map(parseUnit)
      .filter((u): u is RotationUnit => u !== null),
    flags: rows.thin_flags.filter((f): f is string => typeof f === "string"),
    clutchNote: str(clutch.note),
    closers,
  };
}

function TierGroup({ label, players }: { label: string; players: RotationPlayer[] }) {
  if (!players.length) return null;
  return (
    <div style={{ marginBottom: 10 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-warm-gray)",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          background: "var(--color-pure-white)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
        }}
      >
        {players.map((p, i) => (
          <div
            key={`${p.name}-${i}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 14px",
              borderTop: i === 0 ? "none" : "1px solid var(--color-stone-border)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <span
              style={{ flex: 1, fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}
            >
              {p.name}
            </span>
            {p.mpg !== null && (
              <span style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                {p.mpg.toFixed(1)} mpg
              </span>
            )}
            {p.cached && p.diff !== null ? (
              <span
                style={{
                  minWidth: 92,
                  textAlign: "right",
                  fontSize: 12,
                  fontWeight: 600,
                  color:
                    p.diff >= 0 ? "var(--color-cyan-edge)" : "var(--color-warm-gray)",
                }}
              >
                {p.diff >= 0 ? "+" : ""}
                {p.diff.toFixed(1)} net/100
              </span>
            ) : (
              <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>no on/off</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function UnitRow({ u, bestLabel }: { u: RotationUnit; bestLabel?: string }) {
  return (
    <div
      className="unit-row"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      <span className="unit-name" style={{ flex: 1, fontSize: 12, color: "var(--color-ink-black)" }}>
        {u.name.split("-").join(", ")}
      </span>
      {u.best && (
        <Chip tone="accent" className="unit-chip">
          {bestLabel ?? "best net"}
        </Chip>
      )}
      {u.net !== null && (
        <span
          className="unit-net"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: u.best ? "var(--color-cyan-edge)" : "var(--color-ink-black)",
          }}
        >
          {u.net >= 0 ? "+" : ""}
          {u.net.toFixed(1)}
        </span>
      )}
      {u.poss !== null && (
        <span className="unit-poss" style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
          {Math.round(u.poss)} poss
        </span>
      )}
    </div>
  );
}

export default function RotationCheckView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: { season?: string };
}) {
  const r = parseRotation(rows);
  if (!r) return null;
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
        <SectionTitle>{r.team} rotation check</SectionTitle>
        {(r.season || meta?.season) && <Chip>{r.season || meta?.season}</Chip>}
        {r.units !== null && (
          <Chip>
            {r.units} {r.units === 1 ? "lineup" : "lineups"}
          </Chip>
        )}
        {r.starterShare !== null && (
          <Chip tone="accent">starters {(r.starterShare * 100).toFixed(0)}% of minutes</Chip>
        )}
      </div>
      <Caption>
        on/off = net rating per 100 possessions, on-court minus off-court · mpg = minutes per
        game · poss = possessions
      </Caption>

      {r.flags.length > 0 ? (
        <div
          style={{
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "12px 16px",
            marginBottom: 12,
            marginTop: 12,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {r.flags.map((f, i) => (
            <div
              key={i}
              style={{ fontSize: 12, color: "var(--color-ink-black)", lineHeight: 1.55 }}
            >
              {f}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginBottom: 12 }}>
          <Caption>No rotation flags — depth looks healthy.</Caption>
        </div>
      )}

      <TierGroup label="Core" players={r.core} />
      <TierGroup label="Bench" players={r.bench} />
      <TierGroup label="Fringe" players={r.fringe} />

      {(r.starterDiff !== null || r.benchDiff !== null) && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 12 }}>
          Starters {r.starterDiff !== null ? `${r.starterDiff >= 0 ? "+" : ""}${r.starterDiff.toFixed(1)} net/100` : "—"}
          {" · "}bench {r.benchDiff !== null ? `${r.benchDiff >= 0 ? "+" : ""}${r.benchDiff.toFixed(1)} net/100` : "—"}
          {" (avg on/off)"}
        </div>
      )}

      {(r.mostUsed || r.closing.length > 0) && (
        <div style={{ marginBottom: 12 }}>
          <SectionTitle>Units</SectionTitle>
          <div
            style={{
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 10,
              padding: "10px 14px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {r.mostUsed && (
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--color-warm-gray)",
                    marginBottom: 4,
                  }}
                >
                  Most used
                </div>
                <UnitRow u={r.mostUsed} bestLabel="best net overall" />
              </div>
            )}
            {r.closing.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--color-warm-gray)",
                    marginBottom: 4,
                  }}
                >
                  Closing candidates
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {r.closing.map((u, i) => (
                    <UnitRow key={`${u.name}-${i}`} u={u} bestLabel="best net closing" />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {(r.clutchNote || r.closers.length > 0) && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {r.closers.length > 0 && (
            <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
              Clutch minutes:{" "}
              {r.closers
                .slice(0, 5)
                .map((c) =>
                  c.w !== null && c.l !== null
                    ? `${c.name} ${c.w}-${c.l}${c.gp !== null ? ` (${c.gp} GP)` : ""}`
                    : c.name,
                )
                .join(" · ")}
            </div>
          )}
          {r.clutchNote && <Caption>{r.clutchNote}</Caption>}
        </div>
      )}
    </div>
  );
}
