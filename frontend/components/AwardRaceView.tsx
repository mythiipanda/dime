"use client";

import { useState } from "react";
import DebateCardModal from "./DebateCardModal";
import { asList, Bar, Caption, Chip, isObj, num, SectionTitle, str } from "./view-shared";

export interface AwardDriver {
  stat: string;
  value: string;
  z: number | null;
}

export interface AwardCandidate {
  rank: number;
  player: string;
  team: string;
  score: number;
  drivers: AwardDriver[];
  caseFor: string;
  caseAgainst: string;
}

export interface AwardRaceMeta {
  award?: string;
  season?: string;
  formula?: string;
  qualification?: string;
  proxy_caveat?: string;
  advanced_metrics?: string;
}

export function parseAwardRace(rows: unknown): AwardCandidate[] | null {
  if (!isObj(rows)) return null;
  const list = asList(rows.candidates);
  if (!list.length) return null;
  const out: AwardCandidate[] = [];
  for (const r of list) {
    const player = str(r.player);
    const score = num(r.score);
    if (!player || score === null) return null;
    out.push({
      rank: num(r.rank) ?? out.length + 1,
      player,
      team: str(r.team),
      score,
      drivers: asList(r.drivers).map((d) => ({
        stat: str(d.stat) || "stat",
        value: String(d.value ?? "—"),
        z: num(d.z),
      })),
      caseFor: str(r.case_for),
      caseAgainst: str(r.case_against),
    });
  }
  return out;
}

export default function AwardRaceView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: AwardRaceMeta;
}) {
  const [debateOpen, setDebateOpen] = useState(false);
  const candidates = parseAwardRace(rows);
  if (!candidates) return null;
  const maxScore = Math.max(...candidates.map((c) => Math.abs(c.score)), 1);
  const top = candidates[0];
  const runner = candidates[1];

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 4,
        }}
      >
        <SectionTitle>
          {[meta?.award, meta?.season].filter(Boolean).join(" · ") || "Award race"}
        </SectionTitle>
        {top && runner && (
          <button
            type="button"
            className="pill-ghost"
            style={{ fontSize: 12, padding: "4px 14px" }}
            onClick={() => setDebateOpen(true)}
          >
            Debate {top.player} vs {runner.player}
          </button>
        )}
      </div>
      {debateOpen && top && runner && (
        <DebateCardModal
          initialA={top.player}
          initialB={runner.player}
          season={meta?.season}
          topic={meta?.award ? `${meta.award} race` : undefined}
          onClose={() => setDebateOpen(false)}
        />
      )}
      {meta?.formula && (
        <div style={{ marginBottom: 12 }}>
          <Caption>{meta.formula}</Caption>
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {candidates.map((c) => (
          <div
            key={`${c.player}-${c.rank}`}
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
                    c.rank === 1
                      ? "var(--color-ink-black)"
                      : "var(--color-stone-canvas)",
                  color:
                    c.rank === 1
                      ? "var(--color-pure-white)"
                      : "var(--color-warm-gray)",
                  border: "1px solid var(--color-stone-border)",
                }}
              >
                {c.rank}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: 14,
                    color: "var(--color-ink-black)",
                  }}
                >
                  {c.player}
                </div>
                {c.team && (
                  <div
                    style={{ fontSize: 11, color: "var(--color-ash-gray)" }}
                  >
                    {c.team}
                  </div>
                )}
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-cyan-edge)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {c.score.toFixed(2)}
              </span>
            </div>
            <Bar pct={(Math.abs(c.score) / maxScore) * 100} />
            {c.drivers.length > 0 && (
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                  marginTop: 10,
                }}
              >
                {c.drivers.map((d, j) => (
                  <Chip key={j}>
                    {d.stat} {d.value}
                    {d.z !== null ? ` (z ${d.z >= 0 ? "+" : ""}${d.z.toFixed(2)})` : ""}
                  </Chip>
                ))}
              </div>
            )}
            {(c.caseFor || c.caseAgainst) && (
              <div
                style={{
                  marginTop: 10,
                  paddingTop: 8,
                  borderTop: "1px solid var(--color-stone-border)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                }}
              >
                {c.caseFor && (
                  <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                    {c.caseFor}
                  </div>
                )}
                {c.caseAgainst && (
                  <div style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>
                    {c.caseAgainst}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {(meta?.qualification || meta?.proxy_caveat || meta?.advanced_metrics) && (
        <div
          style={{
            marginTop: 10,
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {meta.qualification && <Caption>{meta.qualification}</Caption>}
          {meta.proxy_caveat && <Caption>{meta.proxy_caveat}</Caption>}
          {meta.advanced_metrics && <Caption>{meta.advanced_metrics}</Caption>}
        </div>
      )}
    </div>
  );
}
