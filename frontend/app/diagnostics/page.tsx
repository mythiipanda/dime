"use client";

import { useEffect, useRef, useState } from "react";
import { getRevision, postChatStream } from "../../lib/api";
import {
  bindingDiagnostics,
  diffDiagnostics,
  diffMarker,
  fastFailVerdict,
  parseSseText,
  revisionInfo,
  type SseEvent,
} from "../../lib/diagnostics";
import {
  DiagnosticsTable,
  RevisionCard,
  RunMetaHeader,
} from "../../components/DiagnosticsTable";

export function FastFailBanner({ events, label }: { events: SseEvent[]; label?: string }) {
  const verdict = fastFailVerdict(events);
  if (!verdict.fastFail) return null;
  return (
    <div
      style={{
        marginTop: 12,
        border: "1px solid var(--line)",
        borderRadius: 10,
        padding: "10px 14px",
        background: "var(--surface)",
        fontSize: 13,
        color: "var(--ink)",
      }}
    >
      Fast fail{label ? ` (${label})` : ""}: understand finished in {verdict.understandMs}
      ms with {verdict.gapKinds.join(", ")}.
    </div>
  );
}

export function DiffTable({ leftText, rightText }: { leftText: string; rightText: string }) {
  const rows = diffDiagnostics(
    bindingDiagnostics(parseSseText(leftText)),
    bindingDiagnostics(parseSseText(rightText)),
  );
  if (!leftText.trim() || !rightText.trim()) return null;
  const cell = {
    padding: "6px 10px 6px 0",
    fontSize: 12,
    color: "var(--ink-2)",
    verticalAlign: "top",
    textAlign: "left",
  } as const;
  return (
    <div style={{ overflowX: "auto", marginTop: 16 }}>
      <table style={{ borderCollapse: "collapse", minWidth: 900 }}>
        <thead>
          <tr>
            {["Output", "Run A rejection", "Run B rejection", "Marker"].map((h) => (
              <th
                key={h}
                style={{
                  ...cell,
                  fontSize: 11,
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                  borderBottom: "1px solid var(--line-strong)",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td style={{ ...cell, fontWeight: 500, color: "var(--ink)" }}>
                {r.output_id}
              </td>
              <td style={cell}>{r.left?.rejection || ""}</td>
              <td style={cell}>{r.right?.rejection || ""}</td>
              <td
                style={{
                  ...cell,
                  fontWeight: 500,
                  color: r.changed ? "var(--ink)" : "var(--ink-3)",
                }}
              >
                {diffMarker(r)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DiagnosticsPage() {
  const [q, setQ] = useState("");
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"probe" | "compare">("probe");
  const [leftText, setLeftText] = useState("");
  const [rightText, setRightText] = useState("");
  const [leftRevision, setLeftRevision] = useState("");
  const [leftRuntime, setLeftRuntime] = useState("");
  const [rightRevision, setRightRevision] = useState("");
  const [rightRuntime, setRightRuntime] = useState("");
  const abort = useRef<AbortController | null>(null);
  const [revision, setRevision] = useState<{ revision: string; runtime: string } | null>(null);

  useEffect(() => {
    let live = true;
    getRevision()
      .then((data) => {
        if (live) setRevision(revisionInfo(data, "v2"));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const run = async () => {
    const question = q.trim();
    if (!question || running) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setEvents([]);
    setError("");
    setRunning(true);
    const seen: SseEvent[] = [];
    await postChatStream(
      question,
      null,
      {
        onEvent: (type, data) => {
          seen.push({ type, data });
          setEvents([...seen]);
        },
        onDone: () => setRunning(false),
        onError: (message) => {
          setError(message);
          setRunning(false);
        },
      },
      abort.current.signal,
      null,
      { diagnostics: true },
    );
  };

  const diags = bindingDiagnostics(events);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px 80px" }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-3)" }}>
        Dev probe
      </div>
      <h1 className="font-medium tracking-tight" style={{ fontSize: 24, margin: "4px 0 6px" }}>
        Binding diagnostics
      </h1>
      <div style={{ fontSize: 13, color: "var(--ink-2)", marginBottom: 16 }}>
        Runs a chat stream with diagnostics on and lists every rejected evidence binding.
      </div>
      <RevisionCard info={revision} />
      <div style={{ display: "flex", gap: 4, marginBottom: 12 }} role="group" aria-label="Mode">
        {(["probe", "compare"] as const).map((m) => (
          <button
            key={m}
            type="button"
            className={mode === m ? "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-surface text-ink shadow-hairline" : "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-field text-ink-2 hover:bg-hover"}
            aria-pressed={mode === m}
            style={{ fontSize: 12, padding: "3px 10px", cursor: "pointer" }}
            onClick={() => setMode(m)}
          >
            {m === "probe" ? "Run probe" : "Compare runs"}
          </button>
        ))}
      </div>
      {mode === "probe" && (
        <>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
              style={{ flex: 1 }}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") run();
              }}
              placeholder="Ask the question to probe"
              aria-label="Probe question"
            />
            <button className="inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-ink text-page hover:opacity-90 disabled:opacity-50" onClick={run} disabled={running || !q.trim()}>
              {running ? "Running..." : "Run probe"}
            </button>
          </div>
          {error && <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 12 }}>{error}</div>}
        </>
      )}
      {mode === "compare" ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
            <div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input
                  className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                  style={{ flex: 1, fontSize: 12 }}
                  value={leftRevision}
                  onChange={(e) => setLeftRevision(e.target.value)}
                  placeholder="Run A revision"
                  aria-label="Run A revision"
                />
                <input
                  className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                  style={{ width: 90, fontSize: 12 }}
                  value={leftRuntime}
                  onChange={(e) => setLeftRuntime(e.target.value)}
                  placeholder="Runtime"
                  aria-label="Run A runtime"
                />
              </div>
              <RunMetaHeader text={leftText} revision={leftRevision} runtime={leftRuntime} />
              <textarea
                className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                style={{ minHeight: 160, fontFamily: "monospace", fontSize: 11, width: "100%" }}
                value={leftText}
                onChange={(e) => setLeftText(e.target.value)}
                placeholder="Paste run A SSE here"
                aria-label="Run A SSE"
              />
            </div>
            <div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <input
                  className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                  style={{ flex: 1, fontSize: 12 }}
                  value={rightRevision}
                  onChange={(e) => setRightRevision(e.target.value)}
                  placeholder="Run B revision"
                  aria-label="Run B revision"
                />
                <input
                  className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                  style={{ width: 90, fontSize: 12 }}
                  value={rightRuntime}
                  onChange={(e) => setRightRuntime(e.target.value)}
                  placeholder="Runtime"
                  aria-label="Run B runtime"
                />
              </div>
              <RunMetaHeader text={rightText} revision={rightRevision} runtime={rightRuntime} />
              <textarea
                className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
                style={{ minHeight: 160, fontFamily: "monospace", fontSize: 11, width: "100%" }}
                value={rightText}
                onChange={(e) => setRightText(e.target.value)}
                placeholder="Paste run B SSE here"
                aria-label="Run B SSE"
              />
            </div>
          </div>
          <FastFailBanner events={parseSseText(leftText)} label="run A" />
          <FastFailBanner events={parseSseText(rightText)} label="run B" />
          <DiffTable leftText={leftText} rightText={rightText} />
        </>
      ) : (
        <>
          {!!events.length && (
            <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 12 }}>
              {events.length} events · {diags.length} rejected bindings
            </div>
          )}
          <FastFailBanner events={events} />
          <DiagnosticsTable rows={diags} />
        </>
      )}
    </div>
  );
}
