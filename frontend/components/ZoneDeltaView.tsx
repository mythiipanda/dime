"use client";

import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface ZoneDelta {
  zone: string;
  attempts: number | null;
  makes: number | null;
  fgPct: number | null;
  leagueFgPct: number | null;
  deltaPp: number | null;
  leagueAttempts: number | null;
}

export interface ZoneDeltasMeta {
  seasonLabel?: string;
  minAttempts?: number;
  excludedZones?: string[];
  source?: string;
  dataNote?: string;
}

const ZONE_LABELS: Record<string, string> = {
  rim: "Rim",
  short_mid: "Short mid",
  long_mid: "Long mid",
  corner_3: "Corner 3",
  atb_3: "Above-break 3",
};

export function zoneLabel(key: string): string {
  return ZONE_LABELS[key] || key;
}

function parseDelta(r: Record<string, unknown>): ZoneDelta | null {
  const zone = str(r.zone);
  const attempts = num(r.attempts);
  if (!zone || attempts === null) return null;
  return {
    zone,
    attempts,
    makes: num(r.makes),
    fgPct: num(r.fg_pct),
    leagueFgPct: num(r.league_fg_pct),
    deltaPp: num(r.delta_pp),
    leagueAttempts: num(r.league_attempts),
  };
}

export function parseZoneDeltas(
  rows: unknown,
): { player: string; seasonLabel: string; zones: ZoneDelta[] } | null {
  if (!isObj(rows)) return null;
  const zones = asList(rows.zones)
    .map(parseDelta)
    .filter((z): z is ZoneDelta => z !== null);
  if (!zones.length) return null;
  return {
    player: str(rows.player),
    seasonLabel: str(rows.season_label),
    zones,
  };
}

function fmtPct(v: number | null): string {
  return v === null ? "—" : `${(v * 100).toFixed(1)}%`;
}

function fmtDelta(v: number | null): string {
  if (v === null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)} pp`;
}

function DeltaCard({
  delta,
  rank,
}: {
  delta: ZoneDelta;
  rank: number;
}) {
  const up = (delta.deltaPp ?? 0) >= 0;
  return (
    <div
      style={{
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "12px 16px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 8,
        }}
      >
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 600,
            flexShrink: 0,
            background:
              rank === 1
                ? "var(--color-ink-black)"
                : "var(--color-stone-canvas)",
            color:
              rank === 1
                ? "var(--color-pure-white)"
                : "var(--color-warm-gray)",
            border: "1px solid var(--color-stone-border)",
          }}
        >
          {rank}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "var(--color-ink-black)",
            }}
          >
            {zoneLabel(delta.zone)}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
            {delta.attempts} attempts
          </div>
        </div>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: up
              ? "var(--color-cyan-edge)"
              : "var(--color-warm-gray)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {fmtDelta(delta.deltaPp)}
        </span>
      </div>
      <Bar pct={(delta.fgPct ?? 0) * 100} />
      <div
        style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}
      >
        <Chip tone={up ? "accent" : "neutral"}>
          {fmtPct(delta.fgPct)} vs league {fmtPct(delta.leagueFgPct)}
        </Chip>
        {delta.makes !== null && <Chip>Makes {delta.makes}</Chip>}
      </div>
    </div>
  );
}

export default function ZoneDeltaView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: ZoneDeltasMeta;
}) {
  const parsed = parseZoneDeltas(rows);
  if (!parsed) return null;
  const title = parsed.player
    ? `${parsed.player} vs league average${parsed.seasonLabel ? ` ${parsed.seasonLabel}` : ""}`.trim()
    : "Zone efficiency deltas";

  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {parsed.zones.map((z, i) => (
          <DeltaCard key={z.zone} delta={z} rank={i + 1} />
        ))}
      </div>
      {(meta?.minAttempts || meta?.excludedZones?.length || meta?.source || meta?.dataNote) && (
        <div
          style={{
            marginTop: 10,
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {meta?.minAttempts !== undefined && (
            <Caption>Zones below {meta.minAttempts} attempts are excluded.</Caption>
          )}
          {!!meta?.excludedZones?.length && (
            <Caption>
              Excluded: {meta.excludedZones.map(zoneLabel).join(", ")}.
            </Caption>
          )}
          {meta?.source && <Caption>{meta.source}</Caption>}
          {meta?.dataNote && <Caption>{meta.dataNote}</Caption>}
        </div>
      )}
    </div>
  );
}
