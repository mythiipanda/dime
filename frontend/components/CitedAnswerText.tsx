"use client";

import { memo, useState } from "react";
import type { ReactNode } from "react";
import AnswerText from "./AnswerText";
import type { AiMessage } from "../lib/chat";
import {
  contextPills,
  evidenceSources,
  gapReasons,
  unverifiedSummary,
  unverifiedValues,
  withCitationMarkers,
  withUnverifiedMarkers,
} from "../lib/evidence";
import { Chip } from "./view-shared";
import type { EvidenceSource } from "../lib/evidence";
import { gradeLimits } from "../lib/grades";

export function CiteTable({ source }: { source: EvidenceSource }) {
  const cells: { head: string; body: string; alignRight?: boolean; strong?: boolean }[] = [];
  if (source.subject) cells.push({ head: "Subject", body: source.subject });
  if (source.stat) cells.push({ head: "Stat", body: source.stat });
  if (source.value) cells.push({ head: "Value", body: source.value, alignRight: true, strong: true });
  cells.push({ head: "Source", body: source.origin || "Dime data" });
  return (
    <div style={{ overflowX: "auto", margin: "8px 0 4px" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 12, lineHeight: 1.5 }}>
        <thead>
          <tr>
            {cells.map((c, i) => (
              <th
                key={i}
                style={{
                  textAlign: c.alignRight ? "right" : "left",
                  padding: "4px 10px 4px 0",
                  borderBottom: "1px solid var(--color-stone-muted)",
                  color: "var(--color-warm-gray)",
                  fontWeight: 500,
                  fontSize: 11,
                  whiteSpace: "nowrap",
                }}
              >
                {c.head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {cells.map((c, i) => (
              <td
                key={i}
                style={{
                  padding: "4px 10px 4px 0",
                  textAlign: c.alignRight ? "right" : "left",
                  whiteSpace: "nowrap",
                  color: c.strong ? "var(--color-ink-black)" : "var(--color-warm-gray)",
                  fontVariantNumeric: "tabular-nums",
                  fontWeight: c.strong ? 600 : 400,
                }}
              >
                {c.body}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export interface FlagEntry {
  outputId: string;
  subjectType: string;
  subjectId: string;
  stat: string;
  subject: string;
  value: string;
  source: string;
  timestamp: string;
}

export function claimKeyOf(entry: Pick<FlagEntry, "outputId" | "subjectType" | "subjectId" | "value">): string {
  return [entry.outputId, entry.subjectType, entry.subjectId, entry.value].join("|");
}

const FLAG_FIELDS = [
  "outputId",
  "subjectType",
  "subjectId",
  "stat",
  "subject",
  "value",
  "source",
  "timestamp",
];

export function validFlagEntry(value: unknown): value is FlagEntry {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  for (const field of FLAG_FIELDS) {
    if (typeof record[field] !== "string") return false;
  }
  return !Number.isNaN(Date.parse(record.timestamp as string));
}

export function dedupedFlagLog(entries: FlagEntry[]): FlagEntry[] {
  const seen = new Set<string>();
  return entries.filter((entry) => {
    if (!validFlagEntry(entry)) return false;
    const key = claimKeyOf(entry);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function flagEntry(source: EvidenceSource, at: string): FlagEntry {
  return {
    outputId: source.outputId,
    subjectType: source.subjectType,
    subjectId: source.subjectId,
    stat: source.stat,
    subject: source.subject,
    value: source.value,
    source: source.origin,
    timestamp: at,
  };
}

const CLAIM_LOG_KEY = "dime_claim_log_v1";

function loadClaimLog(): { flagged: FlagEntry[]; accepted: string[] } {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return { flagged: [], accepted: [] };
    }
    const raw = window.localStorage.getItem(CLAIM_LOG_KEY);
    if (!raw) return { flagged: [], accepted: [] };
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return { flagged: [], accepted: [] };
    const record = parsed as Record<string, unknown>;
    const flagged = Array.isArray(record.flagged)
      ? (record.flagged as FlagEntry[]).filter(
          (f) => typeof f === "object" && f !== null && typeof (f as FlagEntry).value === "string",
        )
      : [];
    const accepted = Array.isArray(record.accepted)
      ? (record.accepted as unknown[]).filter((k): k is string => typeof k === "string")
      : [];
    return { flagged, accepted };
  } catch {
    return { flagged: [], accepted: [] };
  }
}

function saveClaimLog(flagged: FlagEntry[], accepted: string[]) {
  try {
    window.localStorage.setItem(CLAIM_LOG_KEY, JSON.stringify({ flagged, accepted }));
  } catch (e) {
    try {
      console.warn("[claims] claim log persistence unavailable", e);
    } catch {}
  }
}

function RowActions({
  flagged,
  onAccept,
  onFlag,
}: {
  flagged: boolean;
  onAccept: () => void;
  onFlag: () => void;
}) {
  const action = {
    background: "none",
    border: "none",
    padding: "2px 0",
    marginRight: 12,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    color: "var(--color-warm-gray)",
  } as const;
  if (flagged) {
    return <div style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>Flagged</div>;
  }
  return (
    <div style={{ display: "flex", marginTop: 2 }}>
      <button type="button" onClick={onAccept} style={action}>
        Accept
      </button>
      <button type="button" onClick={onFlag} style={action}>
        Flag
      </button>
    </div>
  );
}

export function GradeTag({ tag }: { tag: string }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: ".08em",
        textTransform: "uppercase",
        color: "var(--color-ash-gray)",
        whiteSpace: "nowrap",
      }}
    >
      {tag}
    </span>
  );
}

export function EvidenceCard({ source }: { source: EvidenceSource }) {
  const graded = source.grade;
  if (!graded) return null;
  const rows: { head: string; body: string }[] = [{ head: "Scope", body: graded.scope }];
  if (graded.method) rows.push({ head: "Method", body: graded.method });
  const limits = gradeLimits(graded.grade, graded.unknownScope);
  if (limits) rows.push({ head: "Doesn't cover", body: limits });
  if (graded.gap) rows.push({ head: "Gap", body: graded.gap });
  if (source.asOf) rows.push({ head: "As of", body: source.asOf });
  return (
    <div style={{ margin: "2px 0 4px 8px", fontVariantNumeric: "tabular-nums" }}>
      {rows.map((r) => (
        <div key={r.head} style={{ fontSize: 12, lineHeight: 1.5 }}>
          <span style={{ color: "var(--color-ash-gray)", marginRight: 6 }}>{r.head}</span>
          <span style={{ color: "var(--color-warm-gray)" }}>{r.body}</span>
        </div>
      ))}
    </div>
  );
}

export function EvidenceLedger({
  sources,
  openIndex,
  flagged = [],
  onAccept,
  onFlag,
}: {
  sources: EvidenceSource[];
  openIndex: number | null;
  flagged?: number[];
  onAccept?: (index: number) => void;
  onFlag?: (index: number) => void;
}) {
  if (!sources.length) return null;
  return (
    <div style={{ marginTop: 8 }}>
      {sources.map((source) => {
        const open = openIndex === source.index;
        const line = [source.subject, source.stat, source.value, source.origin]
          .filter(Boolean)
          .join(" · ");
        return (
          <div key={source.key} id={`cite-${source.index}`}>
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.5,
                padding: "3px 8px",
                borderRadius: 6,
                color: open ? "var(--color-ink-black)" : "var(--color-ash-gray)",
                background: open ? "var(--color-bg-selected)" : "transparent",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {line || "Dime data"}
              {source.grade ? (
                <>
                  {" · "}
                  <GradeTag tag={source.grade.tag} />
                </>
              ) : null}
              {source.note ? (
                <div style={{ fontSize: 12, color: "var(--color-ash-gray)", marginTop: 2 }}>
                  {source.note}
                </div>
              ) : null}
            </div>
            {open ? (
              <>
                <CiteTable source={source} />
                <EvidenceCard source={source} />
                {onAccept && onFlag ? (
                  <RowActions
                    flagged={flagged.includes(source.index)}
                    onAccept={() => onAccept(source.index)}
                    onFlag={() => onFlag(source.index)}
                  />
                ) : null}
              </>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

const UNTRACED_SUFFIX = " could not be traced to the source data.";

export function untracedOutputs(ai: AiMessage): string[] {
  const caution = Array.isArray(ai.caution) ? ai.caution : [];
  return caution.filter((c): c is string => typeof c === "string" && c.length > 0);
}

export function UntracedNote({ ai }: { ai: AiMessage }) {
  const outputs = untracedOutputs(ai);
  if (!outputs.length) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-warm-gray)", marginBottom: 4 }}>
        Not traced to source
      </div>
      {outputs.map((line, i) => {
        const cut = line.endsWith(UNTRACED_SUFFIX)
          ? line.slice(0, line.length - UNTRACED_SUFFIX.length)
          : "";
        return (
          <div key={i} style={{ fontSize: 12, lineHeight: 1.5, color: "var(--color-ash-gray)" }}>
            {cut ? (
              <>
                <span style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>{cut}</span>
                {UNTRACED_SUFFIX}
              </>
            ) : (
              line
            )}
          </div>
        );
      })}
    </div>
  );
}

export function UnverifiedNote({ ai }: { ai: AiMessage }) {
  const note = unverifiedSummary(ai);
  if (!note) return null;
  return (
    <div style={{ marginTop: 10, fontSize: 12, lineHeight: 1.5, color: "var(--color-ash-gray)" }}>
      {note}
    </div>
  );
}

export function GapPanel({ ai }: { ai: AiMessage }) {
  const reasons = gapReasons(ai);
  if (!reasons.length) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-warm-gray)", marginBottom: 4 }}>
        Couldn't verify
      </div>
      {reasons.map((reason) => (
        <div key={reason} style={{ fontSize: 12, lineHeight: 1.5, color: "var(--color-ash-gray)" }}>
          {reason}
        </div>
      ))}
    </div>
  );
}

function CiteAnchor(props: {
  children?: ReactNode;
  onToggle: (index: number) => void;
  open: boolean;
  index: number;
  label: string;
}) {
  return (
    <button
      type="button"
      className={"cite-marker" + (props.open ? " is-open" : "")}
      aria-expanded={props.open}
      aria-label={props.label}
      onClick={() => props.onToggle(props.index)}
    >
      {props.children}
    </button>
  );
}

function anchorLabel(source: EvidenceSource): string {
  const detail = [source.subject, source.stat, source.value, source.origin]
    .filter(Boolean)
    .join(", ");
  return detail ? `Show source: ${detail}` : "Show source data";
}

export function ContextPills({ ai }: { ai: AiMessage }) {
  const pills = contextPills(ai);
  if (!pills.length) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        marginBottom: 8,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {pills.map((p) => (
        <Chip key={p}>{p}</Chip>
      ))}
    </div>
  );
}

function CopyLogButton({ entries }: { entries: FlagEntry[] }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="pill-ghost"
      style={{ fontSize: 12, padding: "3px 10px", marginTop: 8, marginLeft: 8 }}
      onClick={() => {
        const text = JSON.stringify(dedupedFlagLog(entries), null, 2);
        try {
          const clipboard = navigator.clipboard;
          if (!clipboard) return;
          clipboard.writeText(text).then(
            () => setCopied(true),
            () => {},
          );
        } catch {}
      }}
    >
      {copied ? "Copied" : "Copy log"}
    </button>
  );
}

function downloadLog(entries: FlagEntry[]) {
  const blob = new Blob([JSON.stringify(dedupedFlagLog(entries), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "dime-flagged-claims.json";
  link.click();
  URL.revokeObjectURL(url);
}

function CitedAnswerText({ text, ai }: { text: string; ai: AiMessage }) {
  const [openCite, setOpenCite] = useState<number | null>(null);
  const [stored, setStored] = useState(() => loadClaimLog());
  const accepted = stored.accepted;
  const flagged = stored.flagged;
  const sources = evidenceSources(ai);
  const marked = withUnverifiedMarkers(
    withCitationMarkers(text, sources),
    unverifiedValues(
      ai,
      sources.map((s) => s.value),
    ),
  );
  const persist = (nextFlagged: FlagEntry[], nextAccepted: string[]) => {
    setStored({ flagged: nextFlagged, accepted: nextAccepted });
    saveClaimLog(nextFlagged, nextAccepted);
  };
  const toggle = (index: number) => {
    setOpenCite((cur) => (cur === index ? null : index));
    setTimeout(() => {
      const row = document.getElementById(`cite-${index}`);
      if (row && typeof row.scrollIntoView === "function") {
        row.scrollIntoView({ block: "nearest" });
      }
    }, 0);
  };
  const accept = (index: number) => {
    const source = sources[index];
    if (!source) return;
    const key = claimKeyOf(source);
    if (!accepted.includes(key)) {
      persist(flagged, [...accepted, key]);
    }
    setOpenCite((cur) => (cur === index ? null : cur));
  };
  const flag = (index: number) => {
    const source = sources[index];
    if (!source) return;
    const key = claimKeyOf(source);
    if (flagged.some((f) => claimKeyOf(f) === key)) return;
    persist([...flagged, flagEntry(source, new Date().toISOString())], accepted);
  };
  const flaggedIndexes = flagged
    .map((f) =>
      sources.findIndex((s) => claimKeyOf(s) === claimKeyOf(f)),
    )
    .filter((i) => i >= 0);
  return (
    <div>
      <ContextPills ai={ai} />
      <AnswerText
        text={marked}
        components={{
          a: ({ href, children }) => {
            const target = href || "";
            if (target.startsWith("#unverified")) {
              return (
                <span
                  className="unverified-marker"
                  title="Not verified against source data"
                  aria-label="Not verified against source data"
                >
                  {children}
                </span>
              );
            }
            if (target.startsWith("#cite-")) {
              const index = Number(target.slice("#cite-".length));
              if (!Number.isInteger(index) || !sources[index]) return <>{children}</>;
              if (accepted.includes(claimKeyOf(sources[index]))) return <>{children}</>;
              return (
                <CiteAnchor
                  index={index}
                  open={openCite === index}
                  onToggle={toggle}
                  label={anchorLabel(sources[index])}
                >
                  {children}
                </CiteAnchor>
              );
            }
            return <a href={target}>{children}</a>;
          },
        }}
      />
      <EvidenceLedger
        sources={sources}
        openIndex={openCite}
        flagged={flaggedIndexes}
        onAccept={accept}
        onFlag={flag}
      />
      <UntracedNote ai={ai} />
      {flagged.length > 0 ? (
        <span>
          <button
            type="button"
            className="pill-ghost"
            style={{ fontSize: 12, padding: "3px 10px", marginTop: 8 }}
            onClick={() => downloadLog(flagged)}
          >
            Download log ({flagged.length})
          </button>
          <CopyLogButton entries={flagged} />
        </span>
      ) : null}
      <UnverifiedNote ai={ai} />
      <GapPanel ai={ai} />
    </div>
  );
}

export default memo(CitedAnswerText);
