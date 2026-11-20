"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Basketball, Group, Database, ArrowRight, Copy, Check } from "iconoir-react";
import { appendCachedRun, getModels, getRuns, postChatStream } from "../../lib/api";
import { type AiMessage, type ChatMessage, type ModelOption, createStreamBatcher } from "../../lib/chat";
import { applyEvent, aiFromRun } from "../../lib/stream-event";
import { pairToolItems, planSteps, recordKey } from "../../lib/activity";
import { capabilityLabel } from "../../lib/evidence";
import { replayStream } from "../../lib/replay";
import { takeRerun } from "../../lib/briefs";
import { availableModel, modelLabel } from "../../lib/model-catalog";
import { PromptBar } from "../ds/PromptBar";
import { ThinkingState } from "../ds/ThinkingState";
import { ToolChips } from "../ds/ToolChips";
import { StreamingText } from "../ds/StreamingText";
import { RecordsTable } from "../ds/RecordsTable";
import { StatusPill } from "../ds/StatusPill";
import CitedAnswerText from "../CitedAnswerText";
import DataArtifacts from "../DataArtifacts";
import { notebookFromAnswer } from "../../lib/notebook-seed";
import { OpenNotebookButton } from "../notebooks/OpenNotebookButton";

const suggestions = [
  { icon: Group, text: "Compare Shai Gilgeous-Alexander and Luka Dončić" },
  { icon: Basketball, text: "Where does Oklahoma City have an edge against Denver?" },
  { icon: Database, text: "Find the most effective five-man lineups this season" },
];

function scrollToHash() {
  const id = window.location.hash.slice(1);
  const target = id ? document.getElementById(id) : null;
  target?.scrollIntoView({ block: "start" });
  return !!target;
}

export function AssistantTurn({ ai, question, onAsk, onOpenNotebook }: { ai: AiMessage; question: string; onAsk: (q: string) => void; onOpenNotebook?: (id: string) => void }) {
  const evidencePrefix = useId();
  const [copied, setCopied] = useState(false);
  const items = ai.activity || [];
  const tools = pairToolItems(items).map((pair, i) => {
    const record = pair.call || pair.result!;
    return { id: record.eventId || String(i), label: capabilityLabel(recordKey(record) || record.title), status: (pair.result ? pair.result.transition === "failed" || pair.result.status === "fail" ? "error" : "done" : "running") as "done" | "error" | "running", detail: pair.result?.summary };
  });
  const tables = Object.values(ai.nodes).flatMap((n) => n.tables);
  const grids = tables.filter((t) => t.tool !== "get_comps" && Array.isArray(t.rows) && t.rows.every((r) => r && typeof r === "object" && !Array.isArray(r)));
  const remaining: AiMessage = { ...ai, nodes: Object.fromEntries(Object.entries(ai.nodes).map(([key, node]) => [key, { ...node, tables: node!.tables.filter((t) => !grids.includes(t)) }])) };
  return <article className="assistant-turn" aria-label="Dime response">
    <div className="mb-4 flex items-center gap-2 text-[12px] font-medium"><Basketball width={16} height={16} /><span>Dime</span><span className="ml-1 text-[10px] font-normal text-ink-3">NBA intelligence</span></div>
    {(items.length > 0 || !ai.done) && <ThinkingState busy={!ai.done && !ai.error} steps={planSteps(items).map((s) => ({ label: capabilityLabel(s.capability), state: s.state }))} />}
    <ToolChips tools={tools} />
    {!!ai.caution?.length && <div role="status" className="mb-3 rounded-lg border border-line bg-surface px-3 py-2 text-[12px] text-ink-2">Check numbers against tables: {ai.caution.join(", ")}</div>}
    {ai.text && <StreamingText streaming={ai.streaming}><CitedAnswerText text={ai.text} ai={ai} compact evidencePrefix={evidencePrefix} /></StreamingText>}
    {grids.map((t, i) => <div key={i} id={`${evidencePrefix}evidence-${tables.indexOf(t)}`} tabIndex={-1}><RecordsTable rows={t.rows as Record<string, unknown>[]} title={capabilityLabel(t.tool)} source={[t.meta?.source, t.meta?.season].filter(Boolean).join(" · ")} /></div>)}
    {Object.values(remaining.nodes).some((n) => n.tables.some((t) => t.rows || t.tool === "get_game_prediction")) && <div id={`${evidencePrefix}evidence-artifacts`} tabIndex={-1}><DataArtifacts ai={remaining} question={question} onAsk={onAsk} /></div>}
    {ai.error && <div role="alert" className="mt-4 rounded-xl border border-line bg-surface px-4 py-3"><p className="!m-0 text-[12px] text-red">{ai.error}</p><button className="mt-2 text-[12px] text-ink-2 hover:text-ink" onClick={() => onAsk(question)}>Try again <ArrowRight width={12} height={12} className="inline" /></button></div>}
    {ai.done && ai.text && <div className="mt-4 flex flex-wrap items-center gap-2 text-ink-3"><button className="icon-button" aria-label="Copy answer" onClick={() => navigator.clipboard.writeText(ai.text).then(() => setCopied(true))}>{copied ? <Check width={14} height={14} /> : <Copy width={14} height={14} />}</button>{onOpenNotebook && <OpenNotebookButton seed={() => notebookFromAnswer(ai, question)} onOpen={onOpenNotebook} />}<span className="text-[10px]">Check source coverage before making a decision.</span></div>}
  </article>;
}

export function ChatView({ thread, preset, autoSend, replay, onConsumed, onRunDone, onOpenNotebook }: { thread: string; preset: string | null; autoSend: { thread: string; text: string } | null; replay: string | null; onConsumed: () => void; onRunDone: () => void; onOpenNotebook?: (id: string) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState(preset || "");
  const [models, setModels] = useState<ModelOption[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [modelError, setModelError] = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [workflowBlocked, setWorkflowBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const running = useRef(false);
  const sent = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const hashPending = useRef(true);
  const mounted = useRef(true);
  const loadModels = () => { setModelError(false); setModelsLoaded(false); getModels().then((r) => { if (!mounted.current) return; if (!Array.isArray(r.models)) throw Error("Invalid model catalog"); setModels(r.models); setModel((m) => availableModel(r.models, m)); }).catch(() => { if (mounted.current) { setModel(null); setModelError(true); } }).finally(() => { if (mounted.current) setModelsLoaded(true); }); };
  useEffect(() => {
    mounted.current = true;
    loadModels();
    if (!autoSend && !replay) getRuns(thread).then((runs) => { if (mounted.current) setMessages((current) => current.length ? current : runs.flatMap((r) => [{ role: "human" as const, text: r.question }, { role: "ai" as const, text: r.answer, ai: aiFromRun(r) }])); });
    const rerun = takeRerun();
    if (rerun) setInput(rerun);
    return () => { mounted.current = false; abort.current?.abort(); };
    // A ChatView is keyed by thread; history and model loading happen once per session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { if (preset) setInput(preset); }, [preset]);
  useEffect(() => {
    if (hashPending.current && messages.length) {
      hashPending.current = false;
      if (scrollToHash()) return;
    }
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages]);
  useEffect(() => {
    const onHashChange = () => { hashPending.current = !scrollToHash(); };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const send = async (raw: string, fixture?: string) => {
    const q = raw.trim();
    if (!q || running.current) return;
    if (!fixture && (!model || !models.some((m) => m.id === model && m.available !== false))) return;
    hashPending.current = false;
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
    running.current = true;
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true); setInput("");
    let ai: AiMessage = { text: "", nodes: {}, done: false };
    let runId: string | undefined;
    setMessages((m) => [...m, { role: "human", text: q }, { role: "ai", text: "", ai }]);
    const publish = () => {
      if (!mounted.current || controller.signal.aborted) return;
      setMessages((m) => [...m.slice(0, -1), { role: "ai", text: ai.text, ai }]);
    };
    const batcher = createStreamBatcher((events) => { for (const e of events) { ai = applyEvent(ai, e.type, e.data); runId = ai.carry?.run_id || runId; } publish(); });
    const handlers = {
      onEvent: (type: string, data: unknown) => { if (!controller.signal.aborted) batcher.push(type, data); },
      onDone: () => {
        batcher.flush(); ai = { ...ai, done: true, streaming: false }; publish();
        if (controller.signal.aborted || !mounted.current) return;
        running.current = false; setBusy(false);
        if (!fixture) { appendCachedRun(thread, { id: runId, question: q, answer: ai.text, tables: Object.values(ai.nodes).flatMap((n) => n.tables), suggestions: ai.suggestions || [], created_at: new Date().toISOString() }); onRunDone(); }
      },
      onError: (error: string) => { batcher.flush(); ai = { ...ai, error, done: true, streaming: false }; publish(); if (mounted.current && !controller.signal.aborted) { running.current = false; setBusy(false); } },
    };
    if (fixture) await replayStream(fixture, handlers, controller.signal);
    else await postChatStream(q, model, handlers, controller.signal, thread);
  };
  useEffect(() => {
    if (sent.current || (!replay && !autoSend)) return;
    if (!replay && !modelsLoaded) return;
    const timer = setTimeout(() => {
      sent.current = true;
      if (autoSend?.thread === thread) {
        onConsumed();
        if (model) void send(autoSend.text);
        else { setInput(autoSend.text); setWorkflowBlocked(true); }
      }
      else if (replay) void send("Where does Oklahoma City have an edge against Denver?", replay);
    }, 0);
    return () => clearTimeout(timer);
  });
  const stop = () => { abort.current?.abort(); running.current = false; setBusy(false); setMessages((m) => m.map((message, i) => i === m.length - 1 && message.ai ? { ...message, ai: { ...message.ai, done: true, streaming: false } } : message)); };
  const composer = <><PromptBar value={input} onChange={setInput} onSend={send} onStop={stop} busy={busy} models={models.map((m) => ({ id: m.id, label: modelLabel(m.id), available: m.available }))} model={model} onModelChange={(id) => setModel(availableModel(models, id))} modelError={modelError} onRetry={loadModels} />{workflowBlocked && !model && <p role="status" className="mt-3 px-1 text-[12px] text-ink-2">No model configured — add a provider key to run this workflow. Your request is saved in the composer.</p>}</>;
  return <div className="chat-view">
    {!messages.length ? <div className="chat-empty">
      <h1><span>A clearer view of the game.</span>What are we working on?</h1>
      {composer}
      <div className="mt-6 px-1">{suggestions.map(({ icon: Icon, text }) => <button key={text} className="suggestion-row" onClick={() => send(text)}><Icon width={16} height={16} className="shrink-0 text-ink-3" />{text}</button>)}</div>
      <p className="mt-4 flex items-center gap-2 px-1 text-[11px] text-ink-3"><span className="size-1 rounded-full bg-green" />2025–26 season <span className="mx-1">·</span> Warehouse-grounded answers</p>
    </div> : <>
      <div className="conversation">
        {replay && <div className="mb-6"><StatusPill tone="orange" dot={false}>Development replay · synthetic data</StatusPill></div>}
        {messages.map((message, i) => message.role === "human" ? <div key={i} id={`m-${i}`} className="user-turn">{message.text}</div> : <div key={i} id={`m-${i}`}><AssistantTurn ai={message.ai!} question={messages[i - 1]?.text || ""} onAsk={send} onOpenNotebook={onOpenNotebook} /></div>)}
        <div ref={end} />
      </div>
      <div className="composer-dock">{composer}<p className="mt-2 text-center text-[10px] text-ink-3">Dime can make mistakes. Review the evidence behind every decision.</p></div>
    </>}
  </div>;
}
=======
"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowRight, Basketball, Copy, Database, User } from "iconoir-react";
import { PromptBar } from "../ds/PromptBar";
import { CitationChip } from "../ds/CitationChip";
import { ThinkingState } from "../ds/ThinkingState";
import { ToolChips } from "../ds/ToolChips";
import { StreamingText } from "../ds/StreamingText";
import { AnswerVerification } from "../site/harness/AnswerView";
import { StreamArtifacts } from "../site/harness/ArtifactsView";
import { useDimeChat } from "../site/harness/useDimeChat";
import type { ChatMsg } from "../site/harness/types";
import type { VerificationCarry } from "../../lib/dime-stream";
import { citationDetails } from "../../lib/citation-details";
import { clearWorkflowDraft, createWorkflowDraft, loadWorkflowDraft, saveWorkflowDraft, workflowDraftWasSent, type WorkflowDraft } from "../../lib/workflow-drafts";

export const suggestedPrompts = [
  "Build a scouting report on Shai Gilgeous-Alexander",
  "What changed in the Celtics’ offense this season?",
  "Find undervalued wings who can defend and shoot",
];

export function PiAnswer({ text, carry, prefix }: { text: string; carry: VerificationCarry | null; prefix: string }) {
  const sources = new Map((carry?.sources ?? []).map(source => [source.ref, source]));
  if (!carry?.submission?.blocks.length) return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
  return <>{carry.submission.blocks.map((block, index) => <div key={index} className="my-3">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.text}</ReactMarkdown>
    {block.anchors.map((anchor, anchorIndex) => {
      const source = sources.get(anchor.ref);
      return source ? <CitationChip key={anchorIndex} index={anchorIndex} claim={`${source.label} · row ${anchor.row + 1} · ${anchor.columns.join(", ")}`} detail={citationDetails(source, anchor, prefix)} /> : <span key={anchorIndex} className="text-[11px] text-orange">Source {anchor.ref} unavailable</span>;
    })}
  </div>)}</>;
}

export function AssistantTurn({ message, prefix, onFollowUp }: { message: Extract<ChatMsg, { role: "assistant" }>; prefix: string; onFollowUp: (text: string) => void }) {
  return <article className="assistant-turn">
    <div className="mb-3 flex items-center gap-2 text-[11px] text-ink-3"><Basketball width={14} height={14} /><span>Dime</span></div>
    <PiAnswer text={message.text} carry={message.carry} prefix={prefix} />
    <StreamArtifacts artifacts={message.artifacts} />
    <AnswerVerification carry={message.carry} artifacts={message.artifacts} prefix={prefix} />
    {message.failure && <div role="alert" className="my-4 rounded-lg border border-red/25 bg-red-tint px-4 py-3 text-[12px] text-red">{message.failure.message}</div>}
    {message.text && <button className="icon-button" aria-label="Copy answer" onClick={() => { void navigator.clipboard.writeText(message.text); }}><Copy width={13} height={13} /></button>}
    {message.suggestions.map(suggestion => <button key={suggestion} className="suggestion-row text-[12px]" onClick={() => onFollowUp(suggestion)}><ArrowRight width={13} height={13} />{suggestion}</button>)}
  </article>;
}

export function ChatView({ thread, replay, onRunDone, workflowRequest, onWorkflowConsumed }: { thread: string; replay: string | null; onRunDone: (question: string) => void; workflowRequest?: { thread: string; text: string } | null; onWorkflowConsumed?: () => void }) {
  const [workflowDraft, setWorkflowDraft] = useState<WorkflowDraft | null>(() => replay ? null : loadWorkflowDraft(thread) ?? (workflowRequest?.thread === thread ? createWorkflowDraft(thread, workflowRequest.text) : null));
  const chat = useDimeChat({ thread, replay, onRunDone, onSubmit: () => {
    if (!workflowDraft) return;
    clearWorkflowDraft(thread);
    setWorkflowDraft(null);
    onWorkflowConsumed?.();
  } });
  const workflowSent = workflowDraft !== null && workflowDraftWasSent(workflowDraft, chat.messages);
  useEffect(() => {
    if (workflowDraft) chat.setDraft(workflowDraft.text);
  }, [workflowDraft, chat.setDraft]);
  useEffect(() => {
    if (!workflowSent || !workflowDraft) return;
    clearWorkflowDraft(thread);
    setWorkflowDraft(null);
    if (chat.draft === workflowDraft.text) chat.setDraft("");
    onWorkflowConsumed?.();
  }, [thread, workflowSent, workflowDraft, chat.draft, chat.setDraft, onWorkflowConsumed]);
  const changeDraft = (text: string) => {
    if (workflowDraft) {
      const edited = { ...workflowDraft, text, edited: true };
      saveWorkflowDraft(edited);
      setWorkflowDraft(edited);
      onWorkflowConsumed?.();
    }
    chat.setDraft(text);
  };
  const consumedWorkflow = useRef<typeof workflowRequest>(null);
  useEffect(() => {
    if (!workflowRequest || workflowRequest.thread !== thread || !workflowDraft || workflowSent || consumedWorkflow.current === workflowRequest) return;
    if (workflowDraft.edited || workflowDraft.text !== workflowDraft.request) { onWorkflowConsumed?.(); return; }
    if (chat.historyLoading || chat.modelsLoading || chat.live || chat.draft !== workflowDraft.text) return;
    consumedWorkflow.current = workflowRequest;
    if (workflowDraft.request === workflowRequest.text && chat.modelOptions.some(model => model.id === chat.model && model.available !== false)) chat.submit(workflowDraft.text);
    onWorkflowConsumed?.();
  }, [workflowRequest, workflowDraft, workflowSent, thread, chat.draft, chat.historyLoading, chat.modelsLoading, chat.live, chat.modelOptions, chat.model, chat.submit, onWorkflowConsumed]);
  const replayStarted = useRef(false);
  useEffect(() => {
    if (!replay || chat.historyLoading || replayStarted.current) return;
    replayStarted.current = true;
    chat.submit(suggestedPrompts[0]);
  }, [replay, chat.historyLoading, chat.submit]);
  const busy = !!chat.live;
  const composer = <PromptBar value={chat.draft} onChange={changeDraft} onSend={chat.submit} onStop={chat.stop} busy={busy || chat.historyLoading} models={chat.modelOptions} model={chat.model} onModelChange={chat.setModel} modelError={chat.modelsError} onRetry={chat.retryModels} providers={chat.providers} modelsLoading={chat.modelsLoading} />;
  const empty = chat.messages.length === 0 && !chat.live;
  return <div className="chat-view">
    {replay && <div className="border-b border-line bg-inset px-6 py-2 text-center text-[11px] text-ink-2">Development replay · illustrative data, not live analysis</div>}
    {empty ? <section className="chat-empty">
      <h1><span>Your front office, on demand.</span>What are we looking into?</h1>
      {composer}
      <div className="mt-6 space-y-0.5">{suggestedPrompts.map((prompt, index) => <button key={prompt} className="suggestion-row" disabled={chat.historyLoading} onClick={() => changeDraft(prompt)}>{index === 0 ? <User width={16} height={16} /> : index === 1 ? <Basketball width={16} height={16} /> : <Database width={16} height={16} />}<span>{prompt}</span><ArrowRight width={14} height={14} className="ml-auto" /></button>)}</div>
      {chat.historyLoading && <p role="status" className="mt-4 text-[12px] text-ink-3">Loading conversation…</p>}
      {chat.historyError && <p role="alert" className="mt-4 text-[12px] text-red">{chat.historyError}</p>}
    </section> : <>
      <div className="conversation" ref={chat.scrollRef} aria-label="Conversation">
        {chat.messages.map((message, index) => message.role === "user" ? <div key={index} className="user-turn">{message.text}</div> : <AssistantTurn key={index} message={message} prefix={`${thread}-${index}-`} onFollowUp={chat.submit} />)}
        {chat.live && <article className="assistant-turn" aria-label="Dime response">
          <ThinkingState busy steps={chat.live.thinking.map((step, index, steps) => ({ label: step.label, state: index === steps.length - 1 ? "running" : "done" }))} />
          <ToolChips tools={chat.live.tools.map(tool => ({ id: tool.key, label: tool.label, status: tool.status === "fail" ? "error" : tool.status === "running" ? "running" : "done", detail: tool.error ?? tool.name }))} />
          <StreamingText streaming><PiAnswer text={chat.live.text} carry={chat.live.carry} prefix={`${thread}-live-`} /></StreamingText>
          <StreamArtifacts artifacts={chat.live.artifacts} />
        </article>}
      </div>
      <div className="composer-dock">{composer}<p className="mt-2 text-center text-[10px] text-ink-3">Dime can make mistakes. Check the evidence before making a decision.</p></div>
    </>}
  </div>;
}
>>>>>>> origin/dev
