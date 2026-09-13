"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// S2 answer-hero: the take leads. A trailing "**Verdict**" block is
// pulled to the top as the 20px call line, the "This data covers ..."
// preamble drops to a provenance caption, and all numerals render
// tabular (broadcast lower-third, not spreadsheet).
const COVERAGE_RX = /^\s*This data covers the ([^.]+)\.\s*/;
const VERDICT_RX = /\n\s*(?:\*\*Verdict:?\*\*|Verdict:?)\s+([\s\S]+?)\s*$/;

export default function AnswerText({ text }: { text: string }) {
  if (!text) return null;
  let body = text;
  let coverage: string | null = null;
  let verdict: string | null = null;
  const cm = body.match(COVERAGE_RX);
  if (cm) {
    coverage = cm[1];
    body = body.slice(cm[0].length);
  }
  const vm = body.match(VERDICT_RX);
  if (vm) {
    verdict = vm[1].trim();
    body = body.slice(0, vm.index);
  }
  return (
    <div
      style={{
        fontSize: 14,
        lineHeight: 1.64,
        overflowWrap: "break-word",
        fontVariantNumeric: "tabular-nums",
      }}
      className="answer-md"
    >
      {verdict && (
        <div style={{ margin: "2px 0 10px" }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--color-ash-gray)",
              marginBottom: 2,
            }}
          >
            The call
          </div>
          <div
            className="display"
            style={{ fontSize: 20, lineHeight: 1.35, fontWeight: 600 }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              p: ({ children }) => <span>{children}</span>,
            }}>
              {verdict}
            </ReactMarkdown>
          </div>
        </div>
      )}
      {coverage && (
        <div
          style={{
            fontSize: 11,
            color: "var(--color-ash-gray)",
            marginBottom: 8,
          }}
        >
          Covers the {coverage}.
        </div>
      )}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <div className="display" style={{ fontSize: 20, margin: "12px 0 4px" }}>
              {children}
            </div>
          ),
          h2: ({ children }) => (
            <div className="display" style={{ fontSize: 18, margin: "12px 0 4px" }}>
              {children}
            </div>
          ),
          h3: ({ children }) => (
            <div style={{ fontWeight: 500, margin: "10px 0 2px" }}>{children}</div>
          ),
          p: ({ children }) => <p style={{ margin: "6px 0" }}>{children}</p>,
          ul: ({ children }) => (
            <ul style={{ margin: "6px 0", paddingLeft: 20 }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: "6px 0", paddingLeft: 20 }}>{children}</ol>
          ),
          li: ({ children }) => <li style={{ margin: "2px 0" }}>{children}</li>,
          strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
          code: ({ children }) => (
            <code
              style={{
                background: "var(--color-stone-canvas)",
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
                borderBottom: "1px solid var(--color-stone-border)",
                padding: "4px 8px",
                color: "var(--color-warm-gray)",
                fontWeight: 500,
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "4px 8px" }}>
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
