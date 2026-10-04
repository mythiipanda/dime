"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import AnswerText from "./AnswerText";
import type { AiMessage } from "../lib/chat";
import { contextPills, evidenceSources, unverifiedSummary, withCitationMarkers, withUnverifiedMarkers } from "../lib/evidence";
import { Chip } from "./view-shared";
import type { EvidenceSource } from "../lib/evidence";

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

export function EvidenceLedger({
  sources,
  openIndex,
}: {
  sources: EvidenceSource[];
  openIndex: number | null;
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
            </div>
            {open ? <CiteTable source={source} /> : null}
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

export default function CitedAnswerText({ text, ai }: { text: string; ai: AiMessage }) {
  const [openCite, setOpenCite] = useState<number | null>(null);
  const sources = evidenceSources(ai);
  const marked = withUnverifiedMarkers(withCitationMarkers(text, sources), sources);
  const toggle = (index: number) => {
    setOpenCite((cur) => (cur === index ? null : index));
    setTimeout(() => {
      document.getElementById(`cite-${index}`)?.scrollIntoView({ block: "nearest" });
    }, 0);
  };
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
      <EvidenceLedger sources={sources} openIndex={openCite} />
      <UnverifiedNote ai={ai} />
    </div>
  );
}
