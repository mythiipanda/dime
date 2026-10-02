"use client";

import { useEffect, useRef, useState } from "react";
import {
  AiMessage,
  ChatMessage,
  ModelOption,
  NodeName,
  ToolResult,
  emptyNode,
  isFailureFinal,
} from "../lib/chat";
import { RunInfo, appendCachedRun, buildCitation, getModels, getRuns, postChatStream } from "../lib/api";
import { activityRecordFromEvent, mergeActivityRecord } from "../lib/activity";
import AnswerText from "./AnswerText";
import VerificationBadge from "./VerificationBadge";
import EvidenceSection from "./EvidenceSection";
import { StreamText } from "./StreamText";
import { ArtifactItem } from "./ArtifactCanvas";
import DataArtifacts from "./DataArtifacts";
import ModelPicker from "./ModelPicker";
import AgentActivity from "./AgentActivity";
import Skeleton from "./Skeleton";
import CompareTray, { pinToTray, readTray } from "./CompareTray";
import DebateCardModal from "./DebateCardModal";
import { Button } from "@/components/ui/button";

function aiHasTables(ai: AiMessage): boolean {
  return Object.values(ai.nodes).some((n) => n.tables.length > 0);
}

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
  const activity = activityRecordFromEvent(type, d, next.activity?.length || 0);
  if (activity) next.activity = mergeActivityRecord(next.activity || [], activity);
  if (type === "node_update") {
    const node = d.node as NodeName;
    if (node === "entry") return next;
    const status = d.status;
    touch(node).status =
      status === "complete" || status === "error" ? status : "running";
  } else if (type === "thought_token") {
    if (!next.thoughtStarted) next.thoughtStarted = Date.now();
    const node = touch(d.node as NodeName);
    node.liveThought = (node.liveThought || "") + String(d.text || "");
    if (d.agent && !node.liveThoughtAgent) node.liveThoughtAgent = String(d.agent);
  } else if (type === "thought_stream") {
    if (!next.thoughtStarted) next.thoughtStarted = Date.now();
    touch(d.node as NodeName).thoughts.push(String(d.text || ""));
  } else if (type === "tool_call") {
    const node = touch(d.node as NodeName);
    const id =
      typeof d.correlation_id === "string"
        ? d.correlation_id
        : typeof d.event_id === "string"
          ? d.event_id
          : undefined;
    node.toolCalls.push({
      id,
      name: String(d.name || ""),
      args: (d.args as Record<string, unknown>) || {},
      label: d.label as string | undefined,
      summary: d.summary as string | undefined,
      agent: d.agent as string | undefined,
      status: "running",
      startedAt: Date.now(),
    });
  } else if (type === "tool_result") {
    const node = touch(d.node as NodeName);
    const name = String(d.name || "");
    const agent = d.agent as string | undefined;
    const id =
      typeof d.correlation_id === "string"
        ? d.correlation_id
        : typeof d.event_id === "string"
          ? d.event_id
          : undefined;
    for (let i = 0; i < node.toolCalls.length; i++) {
      const c = node.toolCalls[i];
      if (c.status !== "running") continue;
      if (id && c.id) {
        if (c.id !== id) continue;
      } else if (!(c.name === name && c.agent === agent)) {
        continue;
      }
        c.status = d.status === "ok" ? "ok" : "fail";
        c.endedAt = Date.now();
        if (typeof d.rows === "number") c.rows = d.rows;
        if (typeof d.ms === "number") c.ms = d.ms;
        if (d.error) c.error = String(d.error);
        if (d.summary) c.summary = String(d.summary);
        if (typeof d.sql === "string" && d.sql.trim()) c.sql = d.sql;
        break;
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
    if (d.carry && typeof d.carry === "object") {
      next.carry = d.carry as AiMessage["carry"];
    }
    
    
    
    
    
    
    







    if (!isFailureFinal(next.text, d.carry)) {
      next.error = undefined;
    }
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
  onOpenArtifact?: (artifact: ArtifactItem) => void;
  activeArtifactId?: string;
}

function aiFromRun(r: RunInfo): AiMessage {
  const tables: ToolResult[] = [];
  if (Array.isArray(r.tables)) {
    for (const t of r.tables) {
      if (
        typeof t === "object" &&
        t !== null &&
        
        


        (typeof (t as { tool?: unknown }).tool === "string" ||
          typeof (t as { kind?: unknown }).kind === "string" ||
          Array.isArray((t as { rows?: unknown }).rows))
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

function CiteButton({ text, sources }: {
  text: string;
  sources: {
    source?: string; fetched_at?: string; season?: string;
    qualification?: string; coverage?: string; warnings?: string[];
  }[];
}) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="pill-ghost"
      style={{ fontSize: 12 }}
      title="Copy answer with a citable source line"
      onClick={() => {
        const lines = sources.map((meta) => buildCitation({
          source: meta.source,
          fetchedAt: meta.fetched_at,
          season: meta.season,
          qualification: meta.qualification,
          coverage: meta.coverage,
          warnings: meta.warnings,
        }));
        navigator.clipboard
          .writeText(`${text}\n\n${lines.join("\n")}`)
          .then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          })
          .catch(() => {});
      }}
    >
      {done ? "Copied" : "Cite"}
    </button>
  );
}

function tableSources(ai: AiMessage | undefined): {
  source?: string; fetched_at?: string; season?: string;
  qualification?: string; coverage?: string; warnings?: string[];
}[] {
  if (!ai) return [];
  const sources: {
    source?: string; fetched_at?: string; season?: string;
    qualification?: string; coverage?: string; warnings?: string[];
  }[] = [];
  const seen = new Set<string>();
  for (const node of Object.values(ai.nodes)) {
    for (const table of node?.tables ?? []) {
      const meta = table.meta as {
        source?: string; fetched_at?: string; season?: string;
        qualification?: string; coverage?: string; warnings?: string[];
      } | undefined;
      if (!meta?.source) continue;
      const key = JSON.stringify([
        meta.source, meta.fetched_at, meta.season, meta.qualification,
        meta.coverage, meta.warnings,
      ]);
      if (!seen.has(key)) {
        seen.add(key);
        sources.push(meta);
      }
    }
  }
  return sources;
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

export default function ChatPanel({ thread, onRunDone, preset, onOpenArtifact, activeArtifactId }: Props) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [modelStatus, setModelStatus] = useState<"loading" | "ready" | "error">("loading");
  const modelRequest = useRef(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [debateOpen, setDebateOpen] = useState(false);
  const [debateTopic, setDebateTopic] = useState<string | undefined>(undefined);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [atBottom, setAtBottom] = useState(true);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);


  useEffect(() => {
    if (!input && inputRef.current) inputRef.current.style.height = "";
  }, [input]);
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

  const loadModels = async (automatic = false) => {
    const request = ++modelRequest.current;
    setModelStatus("loading");
    const delays = automatic ? [0, 500, 1500] : [0];
    let lastError: unknown;
    for (const delay of delays) {
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
      if (request !== modelRequest.current) return;
      try {
        const response = await getModels();
        if (!Array.isArray(response.models) || response.models.length === 0) {
          throw new Error("models response did not contain a nonempty array");
        }
        if (request !== modelRequest.current) return;
        setModels(response.models);
        const def = response.models.find((x) => x.default) || response.models[0];
        setModel((current) => response.models.some((x) => x.id === current) ? current : def.id);
        setModelStatus("ready");
        return;
      } catch (error) {
        lastError = error;
      }
    }
    if (request !== modelRequest.current) return;
    

    setModelStatus("error");
    if (process.env.NODE_ENV !== "production") {
      console.error("Failed to load model list", lastError);
    }
  };

  useEffect(() => {
    void loadModels(true);
    return () => { modelRequest.current += 1; };
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
    let runId: string | undefined;
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
          if (type === "final_answer") {
            
            
            
            




            const d = data as Record<string, unknown>;
            if (typeof d.run_id === "string" && d.run_id) {
              runId = d.run_id;
            } else {
              const carry = d.carry as Record<string, unknown> | undefined;
              if (carry && typeof carry.run_id === "string" && carry.run_id) {
                runId = carry.run_id;
              }
            }
          }
          ai = applyEvent(ai, type, data);
          push();
        },
        onDone: () => {
          setBusy(false);
          stopTimer();
          
          
          



          appendCachedRun(thread, {
            id: runId,
            question: q,
            answer: ai.text || "",
            tables: Object.values(ai.nodes).flatMap((n) => n.tables ?? []),
            suggestions: ai.suggestions ?? [],
            created_at: new Date().toISOString(),
          });
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
    <div className="chat-workspace">
      {!messages.length ? (

          <div className="chat-welcome">
          <div className="chat-welcome-heading">
            <h1>What do you want to understand?</h1>
            <p>Ask a hard basketball question. Dime will trace the answer back to the data.</p>
          </div>


          <div
            className="composer-card chat-composer chat-composer-hero"
          >
            <textarea
              ref={inputRef}
              style={{
                width: "100%",
                border: "none",
                outline: "none",
                fontSize: 13,
                lineHeight: 1.4,
                resize: "none",
                fontFamily: "inherit",
                background: "transparent",
                minHeight: 48,
                maxHeight: 240,
                overflowY: "auto",
                boxSizing: "border-box",
              }}
              value={input}
              rows={2}
              autoFocus
              onChange={(e) => {
                setInput(e.target.value);
                const el = e.target;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 240) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendText(input);
                }
              }}
              placeholder="Ask about a player, team, lineup, trade, or trend..."
            />

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
              <ModelPicker models={models} value={model} onChange={setModel} status={modelStatus} onRetry={() => void loadModels(false)} />

              {busy ? (
                <Button
                  variant="ghost"
                  size="default"
                  className="pill-ghost interactive-tactile h-auto font-normal"
                  onClick={stop}
                  style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
                >
                  Stop {elapsed}s
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="default"
                  size="icon"
                  aria-label="Send"
                  disabled={!input.trim()}
                  onClick={() => sendText(input)}
                  className="interactive-tactile chat-send disabled:opacity-100 [&_svg:not([class*='size-'])]:size-[15px]"
                  style={{
                    width: 28, height: 28, borderRadius: 8, border: "none", cursor: input.trim() ? "pointer" : "default",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: input.trim() ? "var(--color-ink-black)" : "var(--color-stone-muted)",
                    color: input.trim() ? "var(--color-pure-white)" : "var(--color-warm-gray)",
                    transition: "background 200ms ease, color 200ms ease",
                  }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 19V5M5 12l7-7 7 7" />
                  </svg>
                </Button>
              )}
            </div>
          </div>



          <div className="chat-starters">
            {[
              {
                title: "Compare Luka & Shai",
                prompt: "Compare Luka Dončić and Shai Gilgeous-Alexander",
                icon: <><circle cx="12" cy="12" r="9" /><path d="M12 3v18M3 12h18" /></>,
              },
              {
                title: "League assist leaders",
                prompt: "Who leads the league in assists?",
                icon: <><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" /></>,
              },
              {
                title: "OKC championship odds",
                prompt: "Show OKC Thunder playoff odds and ELO",
                icon: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></>,
              },
              {
                title: "SAC trades LaVine to LAL",
                prompt: "Check if Sacramento can trade Zach LaVine to the Lakers for Austin Reaves and Jarred Vanderbilt",
                icon: <><path d="M17 3l4 4-4 4" /><path d="M21 7H9" /><path d="M7 21l-4-4 4-4" /><path d="M3 17h12" /></>,
              },
            ].map((item) => (
              <button
                key={item.title}
                type="button"
                onClick={() => sendText(item.prompt)}
                disabled={busy}
                className="chat-starter"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--color-ash-gray)", flexShrink: 0 }}>
                  {item.icon}
                </svg>
                <span>{item.title}</span>
                <span className="chat-starter-arrow">↗</span>
              </button>
            ))}
          </div>
        </div>
      ) : (

        <div className="chat-active">
          <div
            style={{
              maxWidth: 880,
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
                    className="chat-human-bubble"
                  >
                    {m.text}
                  </div>
                </div>
              ) : (
                <div
                  key={i}
                  id={`m-${i}`}
                  className="chat-ai-message chat-answer-reveal"
                >

                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: "var(--color-ink-black)" }}>
                      Dime
                    </span>
                    <span style={{ marginLeft: "auto" }}>
                      {m.ai && <VerificationBadge ai={m.ai} />}
                    </span>
                  </div>

                  {m.ai && <AgentActivity ai={m.ai} />}

                    {m.ai?.error && (
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                        <span style={{ color: "var(--color-ember)", fontSize: 13 }}>{m.ai.error} If this keeps happening, switch models and ask again.</span>
                        <button
                          type="button"
                          className="pill-ghost interactive-tactile"
                          style={{ fontSize: 12, padding: "3px 10px" }}
                          disabled={busy}
                          onClick={() => {
                            const q = messages
                              .slice(0, i)
                              .reverse()
                              .find((x) => x.role === "human")?.text;
                            if (q) sendText(q);
                          }}
                        >
                          Retry
                        </button>
                      </div>
                    )}

                    {m.ai?.caution && m.ai.caution.length > 0 && (
                      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 10, background: "var(--color-sky-wash)", padding: "6px 12px", borderRadius: 8 }}>
                        Check numbers against tables: {m.ai.caution.join(", ")}
                      </div>
                    )}

                    {m.ai?.carry &&
                      ((m.ai.carry.players?.length ?? 0) > 0 ||
                        (m.ai.carry.teams?.length ?? 0) > 0) && (
                      <div
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          fontSize: 12,
                          color: "var(--color-warm-gray)",
                          background: "var(--color-sky-wash)",
                          borderRadius: 999,
                          padding: "3px 12px",
                          marginBottom: 8,
                        }}
                      >
                        Picking up from earlier:{" "}

                        {(m.ai.carry.players?.length
                          ? m.ai.carry.players
                          : [...(m.ai.carry.players ?? []), ...(m.ai.carry.teams ?? [])]
                        ).join(", ")}
                      </div>
                    )}

                    {m.ai?.streaming && !m.ai.done ? (
                      <div style={{ fontSize: 14, lineHeight: 1.64, color: "var(--color-ink-black)" }}>
                        <StreamText text={m.text} />
                      </div>
                    ) : (
                      <AnswerText text={m.text} />
                    )}

                    {m.ai && m.ai.done && <EvidenceSection ai={m.ai} />}

                    {m.ai && !m.ai.done && !m.ai.text && !aiHasTables(m.ai) && (
                      <Skeleton lines={3} />
                    )}

                    {m.ai && (
                      <DataArtifacts
                        ai={m.ai}
                        loading={!m.ai.done}
                        onAsk={sendText}
                        onPinPlayer={(p) => pinToTray(p)}
                        onOpenArtifact={onOpenArtifact}
                        activeArtifactId={activeArtifactId}
                      />
                    )}

                    {m.text && (
                      <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
                        <CopyButton text={m.text} />
                        {tableSources(m.ai).length > 0 && (
                          <CiteButton text={m.text} sources={tableSources(m.ai)} />
                        )}
                        <LinkButton index={i} />
                        <button
                          type="button"
                          className="pill-ghost interactive-tactile"
                          style={{ fontSize: 12, padding: "3px 10px" }}
                          title="Open a debate card from this answer"
                          onClick={() => {
                            setDebateTopic(
                              messages.slice(0, i).reverse().find((x) => x.role === "human")?.text
                            );
                            setDebateOpen(true);
                          }}
                        >
                          Debate
                        </button>
                      </div>
                    )}

                    {m.ai?.suggestions && m.ai.suggestions.length > 0 && m.ai.done && (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
                        {m.ai.suggestions.map((s) => (
                          <button
                            key={s}
                            className="pill-ghost interactive-tactile"
                            style={{ fontSize: 12, padding: "3px 10px", background: "var(--color-pure-white)" }}
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

          <CompareTray
            disabled={busy}
            onCompare={(names) => sendText(`Compare ${names.join(" and ")} this season`)}
          />

          {debateOpen && (
            <DebateCardModal
              initialA={readTray()[0] ?? ""}
              initialB={readTray()[1] ?? ""}
              topic={debateTopic}
              onClose={() => setDebateOpen(false)}
            />
          )}


          <div
            className="prompt-bar"
            style={{
              position: "fixed",
              bottom: 0,
              left: 260,
              right: 0,
              background: "linear-gradient(180deg, transparent, var(--color-stone-canvas) 32%)",
              padding: "26px 20px 24px",
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
                className="composer-card chat-composer chat-composer-dock"
              >
                <ModelPicker models={models} value={model} onChange={setModel} status={modelStatus} onRetry={() => void loadModels(false)} />

                <textarea
                  ref={inputRef}
                  style={{
                    flex: 1,
                    border: "none",
                    outline: "none",
                    fontSize: 13,
                    resize: "none",
                    fontFamily: "inherit",
                    background: "transparent",
                    maxHeight: 200,
                    overflowY: "auto",
                  }}
                  value={input}
                  rows={1}
                  onChange={(e) => {
                    setInput(e.target.value);
                    const el = e.target;
                    el.style.height = "auto";
                    el.style.height = Math.min(el.scrollHeight, 200) + "px";
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendText(input);
                    }
                  }}
              placeholder="Ask a follow-up..."
                />

                {busy ? (
                  <Button
                    variant="ghost"
                    size="default"
                    className="pill-ghost h-auto font-normal"
                    onClick={stop}
                    style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
                  >
                    Stop {elapsed}s
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="default"
                    size="icon"
                    aria-label="Send"
                    disabled={!input.trim()}
                    onClick={() => sendText(input)}
                    className="disabled:opacity-100 [&_svg:not([class*='size-'])]:size-[15px]"
                    style={{
                      width: 28, height: 28, borderRadius: 8, border: "none", flexShrink: 0,
                      cursor: input.trim() ? "pointer" : "default",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: input.trim() ? "var(--color-ink-black)" : "var(--color-stone-muted)",
                      color: input.trim() ? "var(--color-pure-white)" : "var(--color-warm-gray)",
                      transition: "background 200ms ease, color 200ms ease",
                    }}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 19V5M5 12l7-7 7 7" />
                  </svg>
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
