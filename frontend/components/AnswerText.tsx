"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* Answer rendering, harness style: no verdict hero, no display type.
 * The harness renders agent output as flat 13px prose (ChatComposer
 * Section body). Verdict text stays inline where the composer put it -
 * only the "This data covers X." preamble drops to a provenance caption.
 * Numerals stay tabular. */

const COVERAGE_RX = /^\s*This data covers the ([^.]+)\.\s*/;

export default function AnswerText({ text }: { text: string }) {
  if (!text) return null;
  let body = text;
  let coverage: string | null = null;
  const cm = body.match(COVERAGE_RX);
  if (cm) {
    coverage = cm[1];
    body = body.slice(cm[0].length);
  }
  return (
    <div
      style={{
        fontSize: 13,
        lineHeight: 1.5,
        overflowWrap: "break-word",
        fontVariantNumeric: "tabular-nums",
        color: "var(--color-ink-black)",
      }}
      className="answer-md"
    >
      {coverage && (
        <div
          style={{
            fontSize: 12,
            color: "var(--color-ash-gray)",
            marginBottom: 6,
          }}
        >
          Covers the {coverage}.
        </div>
      )}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <div style={{ fontWeight: 600, margin: "10px 0 3px" }}>{children}</div>
          ),
          h2: ({ children }) => (
            <div style={{ fontWeight: 600, margin: "10px 0 3px" }}>{children}</div>
          ),
          h3: ({ children }) => (
            <div style={{ fontWeight: 500, margin: "8px 0 2px" }}>{children}</div>
          ),
          p: ({ children }) => <p style={{ margin: "6px 0" }}>{children}</p>,
          ul: ({ children }) => (
            <ul style={{ margin: "6px 0", paddingLeft: 18 }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: "6px 0", paddingLeft: 18 }}>{children}</ol>
          ),
          li: ({ children }) => <li style={{ margin: "2px 0" }}>{children}</li>,
          strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
          code: ({ children }) => (
            <code
              style={{
                background: "var(--color-field)",
                border: "1px solid var(--color-stone-border)",
                borderRadius: 4,
                padding: "0 4px",
                fontSize: 12,
              }}
            >
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div style={{ overflowX: "auto", margin: "8px 0" }}>
              <table style={{ borderCollapse: "collapse", fontSize: 12 }}>{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th
              style={{
                textAlign: "left",
                padding: "6px 10px",
                borderBottom: "1px solid var(--color-stone-muted)",
                color: "var(--color-warm-gray)",
                fontWeight: 500,
                whiteSpace: "nowrap",
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              style={{
                padding: "6px 10px",
                borderBottom: "1px solid var(--color-stone-border)",
                whiteSpace: "nowrap",
              }}
            >
              {children}
            </td>
          ),
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
