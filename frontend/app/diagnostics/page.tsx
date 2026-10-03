"use client";

import { useRef, useState } from "react";
import { postChatStream } from "../../lib/api";
import { chatRuntime } from "../../lib/runtime";
import { bindingDiagnostics, type SseEvent } from "../../lib/diagnostics";
import { DiagnosticsTable } from "../../components/DiagnosticsTable";

export default function DiagnosticsPage() {
  const [q, setQ] = useState("");
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null);
  const v2 = chatRuntime() === "v2";

  const run = async () => {
    const question = q.trim();
    if (!question || running || !v2) return;
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
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--color-ash-gray)" }}>
        Dev probe
      </div>
      <h1 className="display" style={{ fontSize: 24, margin: "4px 0 6px" }}>
        Binding diagnostics
      </h1>
      <div style={{ fontSize: 13, color: "var(--color-warm-gray)", marginBottom: 16 }}>
        Runs a chat stream with diagnostics on and lists every rejected evidence binding.
      </div>
      {!v2 && (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)", marginBottom: 16 }}>
          Needs the v2 chat runtime. Diagnostics events only exist on v2 streams.
        </div>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="field"
          style={{ flex: 1 }}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") run();
          }}
          placeholder="Ask the question to probe"
          aria-label="Probe question"
        />
        <button className="pill-cta" onClick={run} disabled={running || !v2 || !q.trim()}>
          {running ? "Running..." : "Run probe"}
        </button>
      </div>
      {error && <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 12 }}>{error}</div>}
      {!!events.length && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 12 }}>
          {events.length} events · {diags.length} rejected bindings
        </div>
      )}
      <DiagnosticsTable rows={diags} />
    </div>
  );
}
