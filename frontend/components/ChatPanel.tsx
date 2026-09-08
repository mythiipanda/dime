"use client";

import { useEffect, useRef, useState } from "react";
import {
  AiMessage,
  ChatMessage,
  ModelOption,
  NodeName,
  ToolResult,
  emptyNode,
} from "../lib/chat";
import { RunInfo, getModels, getRuns, postChatStream } from "../lib/api";
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

function aiFromRun(r: RunInfo): AiMessage {
  const tables: ToolResult[] = [];
  if (Array.isArray(r.tables)) {
    for (const t of r.tables) {
      if (
        typeof t === "object" &&
        t !== null &&
        typeof (t as { tool?: unknown }).tool === "string"
      ) {
        tables.push(t as ToolResult);
      }
    }
  }
  return {
    text: typeof r.answer === "string" ? r.answer : "",
    nodes: tables.length
      ? {
          analytics: {
            status: "complete",
            thoughts: [],
            toolCalls: [],
            toolResults: [],
            tables,
          },
        }
      : {},
    done: true,
    suggestions: Array.isArray(r.suggestions) ? r.suggestions : [],
  };
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="pill-ghost"
      style={{ fontSize: 12 }}
      onClick={() => {
        navigator.clipboard
          .writeText(text)
          .then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          })
          .catch(() => {});
      }}
    >
      {done ? "Copied" : "Copy"}
    </button>
  );
}

function LinkButton({ index }: { index: number }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="pill-ghost"
      style={{ fontSize: 12 }}
      onClick={() => {
        if (typeof window === "undefined") return;
        const url =
          window.location.origin +
          window.location.pathname +
          window.location.search +
          `#m-${index}`;
        navigator.clipboard
          .writeText(url)
          .then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          })
          .catch(() => {});
      }}
    >
      {done ? "Copied" : "Link"}
    </button>
  );
}

export default function ChatPanel({ thread, onRunDone, preset }: Props) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [atBottom, setAtBottom] = useState(true);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
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
    const onScroll = () => {
      const gap =
        document.documentElement.scrollHeight -
        (window.innerHeight + window.scrollY);
      setAtBottom(gap < 120);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const h = typeof window !== "undefined" ? window.location.hash : "";
    if (h) {
      const el = document.getElementById(h.slice(1));
      if (el) {
        el.scrollIntoView({ block: "start" });
        return;
      }
    }
    if (atBottom) {
      endRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages, atBottom]);

  useEffect(() => {
    const toHash = () => {
      const h = window.location.hash;
      if (!h) return;
      document.getElementById(h.slice(1))?.scrollIntoView({ block: "start" });
    };
    window.addEventListener("hashchange", toHash);
    return () => window.removeEventListener("hashchange", toHash);
  }, []);

  useEffect(() => {
    abort.current?.abort();
    setMessages([]);
    setInput("");
    setBusy(false);
    stopTimer();
    let cancelled = false;
    getRuns(thread)
      .then((runs) => {
        if (cancelled || !runs.length) return;
        const seeded: ChatMessage[] = [];
        for (const r of runs) {
          if (typeof r.question !== "string") continue;
          seeded.push({ role: "human", text: r.question });
          seeded.push({ role: "ai", text: r.answer || "", ai: aiFromRun(r) });
        }
        if (seeded.length) {
          setMessages((m) => (m.length ? m : seeded));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [thread]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);

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
    setMessages((m) => {
      if (!m.length) return m;
      const copy = [...m];
      const last = copy[copy.length - 1];
      if (last.role === "ai" && last.ai && !last.ai.done) {
        copy[copy.length - 1] = {
          ...last,
          ai: { ...last.ai, done: true, streaming: false },
        };
      }
      return copy;
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", position: "relative" }}>
      {!messages.length ? (
        /* Empty State: Centered Hero Layout (ChatGPT style) */
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: "40px 20px 80px",
            maxWidth: 760,
            width: "100%",
            margin: "0 auto",
            boxSizing: "border-box",
          }}
        >
          <div className="display" style={{ fontSize: 32, fontWeight: 500, color: "var(--color-ink-black)", marginBottom: 8, textAlign: "center" }}>
            What would you like to know?
          </div>
          <div style={{ fontSize: 13, color: "var(--color-warm-gray)", textAlign: "center", marginBottom: 28 }}>
            NBA stats and analysis · <span className="highlight">2025-26 season</span>
          </div>

          {/* Centered Large Prompt Composer Card */}
          <div
            className="composer-card"
            style={{
              width: "100%",
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 24,
              boxShadow: "0 6px 30px rgba(0, 0, 0, 0.06)",
              padding: "16px 20px 14px",
              boxSizing: "border-box",
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <textarea
              ref={inputRef}
              style={{
                width: "100%",
                border: "none",
                outline: "none",
                fontSize: 15,
                lineHeight: 1.5,
                resize: "none",
                fontFamily: "inherit",
                background: "transparent",
                minHeight: 48,
                maxHeight: 180,
                overflowY: "auto",
                boxSizing: "border-box",
              }}
              value={input}
              rows={2}
              autoFocus
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendText(input);
                }
              }}
                  placeholder="Compare Luka and SGA by efficiency..."
            />

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4, borderTop: "1px solid var(--color-stone-canvas)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, color: "var(--color-ash-gray)", display: "flex", alignItems: "center", gap: 4 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  Model:
                </span>
                <select
                  value={model || ""}
                  onChange={(e) => setModel(e.target.value || null)}
                  style={{
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 8,
                    background: "var(--color-stone-canvas)",
                    fontSize: 12,
                    color: "var(--color-ink-black)",
                    outline: "none",
                    cursor: "pointer",
                    padding: "4px 8px",
                    maxWidth: 180,
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
              </div>

              {busy ? (
                <button
                  className="pill-ghost"
                  onClick={stop}
                  style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
                >
                  Stop {elapsed}s
                </button>
              ) : (
                <button
                  className="pill-cta"
                  style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 20px" }}
                  onClick={() => sendText(input)}
                >
                  Ask
                </button>
              )}
            </div>
          </div>

          {/* Quick Prompt Starters (ChatGPT style) */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", marginTop: 24 }}>
            {[
              {
                text: "Compare Luka Dončić and Shai Gilgeous-Alexander",
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                  </svg>
                ),
              },
              {
                text: "Who leads the league in assists?",
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="8" r="7" />
                    <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88" />
                  </svg>
                ),
              },
              {
                text: "Show OKC Thunder playoff odds and ELO",
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                  </svg>
                ),
              },
              {
                text: "Run a trade check: Zach LaVine for draft picks",
                icon: (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="17 1 21 5 17 9" />
                    <path d="M3 11V9a4 4 0 0 1 4-4h14" />
                    <polyline points="7 23 3 19 7 15" />
                    <path d="M21 13v2a4 4 0 0 1-4 4H3" />
                  </svg>
                ),
              },
            ].map((item) => (
              <button
                key={item.text}
                onClick={() => sendText(item.text)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 14px",
                  borderRadius: 12,
                  background: "transparent",
                  border: "1px solid transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: 14,
                  color: "var(--color-warm-gray)",
                  transition: "all 140ms ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--color-pure-white)";
                  e.currentTarget.style.borderColor = "var(--color-stone-border)";
                  e.currentTarget.style.color = "var(--color-ink-black)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.borderColor = "transparent";
                  e.currentTarget.style.color = "var(--color-warm-gray)";
                }}
              >
                <span style={{ color: "var(--color-ash-gray)", display: "flex", alignItems: "center" }}>
                  {item.icon}
                </span>
                <span>{item.text}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* Active Conversation State: Scrollable Message Stream */
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div
            style={{
              maxWidth: 840,
              width: "100%",
              margin: "0 auto",
              padding: "24px 20px 140px",
              display: "flex",
              flexDirection: "column",
              gap: 20,
              boxSizing: "border-box",
            }}
          >
            {messages.map((m, i) =>
              m.role === "human" ? (
                <div
                  key={i}
                  id={`m-${i}`}
                  style={{ alignSelf: "flex-end", maxWidth: "80%", scrollMarginTop: 16 }}
                >
                  <div
                    style={{
                      background: "var(--color-soot)",
                      color: "#ffffff",
                      borderRadius: "16px 16px 4px 16px",
                      padding: "12px 18px",
                      fontSize: 14,
                      lineHeight: 1.5,
                      boxShadow: "var(--shadow-card)",
                    }}
                  >
                    {m.text}
                  </div>
                </div>
              ) : (
                <div
                  key={i}
                  id={`m-${i}`}
                  style={{
                    alignSelf: "flex-start",
                    width: "100%",
                    background: "var(--color-pure-white)",
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 14,
                    padding: "20px",
                    boxShadow: "var(--shadow-card)",
                    boxSizing: "border-box",
                    scrollMarginTop: 16,
                  }}
                >
                  {m.ai && !m.ai.done && !m.text && (
                    <div>
                      <div style={{ fontSize: 12, color: "var(--color-ash-gray)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--color-cyan-signal)" }} className="shimmer" />
                        Looking up stats...
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
                    <div style={{ color: "#e11d48", fontSize: 13 }}>Error: {m.ai.error}</div>
                  )}

                  {m.ai?.caution && m.ai.caution.length > 0 && (
                    <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 10, background: "var(--color-sky-wash)", padding: "6px 12px", borderRadius: 8 }}>
                      Check these numbers against the tables: {m.ai.caution.join(", ")}
                    </div>
                  )}

                  <AnswerText text={m.text} />

                  {m.ai?.streaming && !m.ai.done && (
                    <span className="caret" aria-hidden />
                  )}

                  {m.ai && <NodeCards ai={m.ai} />}

                  {m.text && (
                    <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center", borderTop: "1px solid var(--color-stone-border)", paddingTop: 12 }}>
                      <CopyButton text={m.text} />
                      <LinkButton index={i} />
                      {m.ai?.nodes.analytics?.tables.map((t, j) => (
                        <span key={j} style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
                          [S{j + 1}] {t.tool}
                          {t.meta?.fetched_at ? ` ${String(t.meta.fetched_at).slice(0, 10)}` : ""}
                        </span>
                      ))}
                    </div>
                  )}

                  {m.ai?.suggestions && m.ai.suggestions.length > 0 && m.ai.done && (
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
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
            <div ref={endRef} />
          </div>

          {/* Fixed Floating Prompt Bar in Active Chat */}
          <div
            style={{
              position: "fixed",
              bottom: 0,
              left: 260,
              right: 0,
              background: "linear-gradient(to top, var(--color-stone-canvas) 85%, transparent)",
              padding: "16px 20px 24px",
              zIndex: 40,
              boxSizing: "border-box",
            }}
          >
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
              {!atBottom && messages.length > 2 && (
                <div style={{ textAlign: "center", marginBottom: 8 }}>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 12, background: "var(--color-pure-white)", boxShadow: "var(--shadow-card)" }}
                    onClick={() => {
                      setAtBottom(true);
                      endRef.current?.scrollIntoView({ block: "end" });
                    }}
                  >
                    ↓ Jump to latest message
                  </button>
                </div>
              )}

              <div
                className="composer-card"
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  border: "1px solid var(--color-stone-border)",
                  borderRadius: 18,
                  padding: "10px 14px 10px 16px",
                  background: "var(--color-pure-white)",
                  boxShadow: "0 4px 20px rgba(0, 0, 0, 0.08)",
                }}
              >
                <select
                  value={model || ""}
                  onChange={(e) => setModel(e.target.value || null)}
                  style={{
                    border: "none",
                    background: "transparent",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    outline: "none",
                    cursor: "pointer",
                    maxWidth: 160,
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

                <textarea
                  ref={inputRef}
                  style={{
                    flex: 1,
                    border: "none",
                    outline: "none",
                    fontSize: 14,
                    resize: "none",
                    fontFamily: "inherit",
                    background: "transparent",
                    maxHeight: 160,
                    overflowY: "auto",
                  }}
                  value={input}
                  rows={1}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendText(input);
                    }
                  }}
              placeholder="Compare Luka and SGA by efficiency..."
                />

                {busy ? (
                  <button
                    className="pill-ghost"
                    onClick={stop}
                    style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
                  >
                    Stop {elapsed}s
                  </button>
                ) : (
                  <button className="pill-cta" onClick={() => sendText(input)}>
                    Ask
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
