"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";








const COVERAGE_RX = /^\s*This data covers the ([^.]+)\.\s*/;
const TAKEAWAY_HEAD_RX = /^\s*(#{1,3}\s*)?\*{0,2}takeaways\*{0,2}\s*:?\s*$/i;
const SECTION_HEAD_RX = /^\s*(#{1,3}\s+\S|\*\*\S.*\S\*\*\s*:?\s*)$/;
const MAX_TAKEAWAYS = 3;
const MAX_TAKEAWAY_CHARS = 160;

function capTakeaways(body: string): string {
  const lines = body.split("\n");
  const head = lines.findIndex((l) => TAKEAWAY_HEAD_RX.test(l));
  if (head < 0) return body;
  let end = lines.length;
  for (let i = head + 1; i < lines.length; i++) {
    if (SECTION_HEAD_RX.test(lines[i])) {
      end = i;
      break;
    }
  }
  const kept: string[] = [lines[head]];
  let count = 0;
  for (let i = head + 1; i < end && count < MAX_TAKEAWAYS; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    kept.push(
      line.length > MAX_TAKEAWAY_CHARS
        ? `${line.slice(0, MAX_TAKEAWAY_CHARS).replace(/\s+\S*$/, "")}…`
        : line,
    );
    count++;
  }
  return [...kept, ...lines.slice(end)].join("\n");
}

export default function AnswerText({ text, components }: { text: string; components?: Components }) {
  if (!text) return null;
  let body = capTakeaways(text);
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
        whiteSpace: "pre-wrap",
        fontVariantNumeric: "tabular-nums",
        color: "var(--color-ink-black)",
      }}
      className="answer-md t-skel-in"
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
          ...components,
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
