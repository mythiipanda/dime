"use client";

import { useEffect, useRef, useState } from "react";
import {
  AiMessage,
  ChatMessage,
  ModelOption,
  NodeName,
  emptyNode,
} from "../lib/chat";
import { getModels, postChatStream } from "../lib/api";
import AnswerText from "./AnswerText";
import NodeCards from "./NodeCards";

function applyEvent(ai: AiMessage, type: string, data: unknown): AiMessage {
  const d = data as Record<string, unknown>;
  const next: AiMessage = {
    ...ai,
    nodes: { ...ai.nodes },
  };
  const touch = (n: NodeName) => {
    if (!next.nodes[n]) next.nodes[n] = emptyNode();
    return next.nodes[n]!;
  };
  if (type === "node_update") {
    const node = d.node as NodeName;
    touch(node).status = d.status === "complete" ? "complete" : "running";
  } else if (type === "thought_stream") {
    if (!next.thoughtStarted) next.thoughtStarted = Date.now();
    touch(d.node as NodeName).thoughts.push(String(d.text || ""));
  } else if (type === "message") {
    const node = touch(d.node as NodeName);
    if (d.tool_call) {
      const c = d.tool_call as { name: string; args: Record<string, unknown> };
      node.toolCalls.push({ name: c.name, args: c.args || {} });
    }
    if (d.tool_result) {
      const r = d.tool_result as {
        tool: string;
        ok?: boolean;
        rows?: unknown;
        meta?: { source?: string; fetched_at?: string };
        error?: string;
      };
      node.toolResults.push(r);
    }
  } else if (type === "custom_data") {
    const node = touch(d.node as NodeName);
    const tables = (d.tables as unknown[]) || [];
    node.tables.push(
      ...(tables as {
        tool: string;
        rows?: unknown;
        meta?: { source?: string; fetched_at?: string };
      }[]),
    );
    const unverified = d.unverified_numbers as string[] | undefined;
    if (unverified && unverified.length) {
      next.caution = [...(next.caution || []), ...unverified];
    }
  } else if (type === "token") {
    next.text = (next.text || "") + String(d.text || "");
    next.streaming = true;
  } else if (type === "final_answer") {
    next.text = String(d.text || "");
    next.streaming = false;
  } else if (type === "suggestions") {
    const items = (d.items as string[]) || [];
    next.suggestions = items;
  } else if (type === "error") {
    next.error = String(d.message || "error");
  } else if (type === "graph_end") {
    next.done = true;
    next.streaming = false;
    if (next.thoughtStarted && !next.thoughtMs) {
      next.thoughtMs = Date.now() - next.thoughtStarted;
    }
    for (const n of Object.keys(next.nodes) as NodeName[]) {
      if (next.nodes[n]!.status === "running") next.nodes[n]!.status = "complete";
    }
  }
  return next;
}

interface Props {
  thread: string;
  onRunDone: () => void;
  preset?: string | null;
}

export default function ChatPanel({ thread, onRunDone, preset }: Props) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const abort = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTimer = () => {
    const t0 = Date.now();
    setElapsed(0);
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
  };
  const stopTimer = () => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  };

  useEffect(() => {
    getModels()
      .then((m) => {
        setModels(m.models);
        const def = m.models.find((x) => x.default) || m.models[0];
        setModel(def ? def.id : null);
      })
      .catch(() => setModels([]));
  }, []);

  useEffect(() => {
    abort.current?.abort();
    setMessages([]);
    setInput("");
    setBusy(false);
    stopTimer();
  }, [thread]);

  useEffect(() => {
    if (preset) setInput(preset);
  }, [preset]);

  const sendText = async (raw: string) => {
    const q = raw.trim();
    if (!q || busy) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setInput("");
    setBusy(true);
    startTimer();
    let ai: AiMessage = { text: "", nodes: {}, done: false };
    setMessages((m) => [...m, { role: "human", text: q }, { role: "ai", text: "", ai }]);
    const push = () => {
      const snap = ai;
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "ai", text: snap.text, ai: snap };
        return copy;
      });
    };
    await postChatStream(
      q,
      model,
      {
        onEvent: (type, data) => {
          ai = applyEvent(ai, type, data);
          push();
        },
        onDone: () => {
          setBusy(false);
          stopTimer();
          onRunDone();
        },
        onError: (message) => {
          ai = { ...ai, error: message, done: true };
          push();
          setBusy(false);
          stopTimer();
        },
      },
      abort.current.signal,
      thread,
    );
  };

  const stop = () => {
    abort.current?.abort();
    setBusy(false);
    stopTimer();
  };

  return (
    <div>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {!messages.length && (
          <div className="card">
            <div className="display" style={{ fontSize: 32 }}>
              Ask about the <span className="highlight">2025-26 season</span>
            </div>
            <p style={{ color: "#78716c", marginTop: 8 }}>
              Player intel, team hubs, boxscores, standings, leaders. Every answer
              carries its source table.
            </p>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "human" ? (
            <div key={i} style={{ alignSelf: "flex-end", maxWidth: "80%" }}>
              <div
                style={{
                  background: "#1c1917",
                  color: "#ffffff",
                  borderRadius: 10,
                  padding: "8px 16px",
                }}
              >
                {m.text}
              </div>
            </div>
          ) : (
            <div key={i} className="card">
              {m.ai && !m.ai.done && !m.text && (
                <div>
                  <div style={{ fontSize: 12, color: "#a8a29e", marginBottom: 4 }}>
                    Working
                  </div>
                  {[90, 70, 55].map((w, d) => (
                    <div
                      key={d}
                      className="shimmer skeleton-row"
                      style={{ width: `${w}%` }}
                    />
                  ))}
                </div>
              )}
              {m.ai?.error && (
                <div style={{ color: "#78716c" }}>Error: {m.ai.error}</div>
              )}
              {m.ai?.caution && m.ai.caution.length > 0 && (
                <div style={{ fontSize: 12, color: "#78716c", marginBottom: 8 }}>
                  Check these numbers against the tables: {m.ai.caution.join(", ")}
                </div>
              )}
              <AnswerText text={m.text} />
              {m.ai?.streaming && !m.ai.done && (
                <span className="caret" aria-hidden />
              )}
              {m.ai && <NodeCards ai={m.ai} />}
              {m.text && (
                <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 12 }}
                    onClick={() => navigator.clipboard.writeText(m.text)}
                  >
                    Copy
                  </button>
                  {m.ai?.nodes.analytics?.tables.map((t, j) => (
                    <span key={j} style={{ fontSize: 11, color: "#a8a29e" }}>
                      [S{j + 1}] {t.tool}
                      {t.meta?.fetched_at
                        ? ` ${String(t.meta.fetched_at).slice(0, 10)}`
                        : ""}
                    </span>
                  ))}
                </div>
              )}
              {m.ai?.suggestions && m.ai.suggestions.length > 0 && m.ai.done && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                  {m.ai.suggestions.map((s) => (
                    <button
                      key={s}
                      className="pill-ghost"
                      style={{ fontSize: 12 }}
                      onClick={() => sendText(s)}
                      disabled={busy}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ),
        )}
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 16,
          alignItems: "center",
          border: "1px solid #e8e6e5",
          borderRadius: 12,
          padding: "8px 8px 8px 12px",
          background: "#ffffff",
        }}
      >
        <select
          value={model || ""}
          onChange={(e) => setModel(e.target.value || null)}
          style={{
            border: "none",
            background: "transparent",
            fontSize: 12,
            color: "#78716c",
            outline: "none",
            cursor: "pointer",
            maxWidth: 200,
          }}
          aria-label="Model"
        >
          {!models.length && <option value="">Offline</option>}
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id.replace("openrouter:", "").replace(":free", "")}
            </option>
          ))}
        </select>
        <input
          style={{ flex: 1, border: "none", outline: "none", fontSize: 14 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendText(input)}
          placeholder="Compare Luka and SGA by efficiency..."
        />
        {busy ? (
          <button className="pill-ghost" onClick={stop}>
            Stop {elapsed}s
          </button>
        ) : (
          <button className="pill-cta" onClick={() => sendText(input)}>
            Ask
          </button>
        )}
      </div>
    </div>
  );
}
