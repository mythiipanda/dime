"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function AnswerText({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div
      style={{
        fontSize: 14,
        lineHeight: 1.64,
        overflowWrap: "break-word",
      }}
      className="answer-md"
    >
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
                background: "#fafaf9",
                border: "1px solid #e8e6e5",
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
                borderBottom: "1px solid #e8e6e5",
                padding: "4px 8px",
                color: "#78716c",
                fontWeight: 500,
              }}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ borderBottom: "1px solid #e8e6e5", padding: "4px 8px" }}>
              {children}
            </td>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
