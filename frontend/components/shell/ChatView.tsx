"use client";

import { useEffect, useRef } from "react";
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
import { clearWorkflowDraft, hasPendingWorkflowDraft, loadWorkflowDraft, saveWorkflowDraft } from "../../lib/workflow-drafts";

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
  const chat = useDimeChat({ thread, replay, onRunDone });
  const workflowDraftActive = useRef(false);
  const workflowRestored = useRef(false);
  const workflowEdited = useRef(false);
  useEffect(() => {
    if (replay || workflowRestored.current) return;
    workflowRestored.current = true;
    const saved = loadWorkflowDraft(thread);
    const request = workflowRequest?.thread === thread ? workflowRequest : null;
    if (saved !== null || hasPendingWorkflowDraft(thread) || request) {
      workflowDraftActive.current = true;
      chat.setDraft(saved ?? request?.text ?? "");
    }
  }, [thread, replay, workflowRequest, chat.setDraft]);
  useEffect(() => {
    if (!workflowDraftActive.current || !chat.messages.some(message => message.role === "user")) return;
    clearWorkflowDraft(thread);
    workflowDraftActive.current = false;
  }, [thread, chat.messages]);
  const changeDraft = (text: string) => {
    if (workflowDraftActive.current) {
      workflowEdited.current = true;
      saveWorkflowDraft(thread, text);
    }
    chat.setDraft(text);
  };
  const consumedWorkflow = useRef<typeof workflowRequest>(null);
  useEffect(() => {
    if (!workflowRequest || workflowRequest.thread !== thread || consumedWorkflow.current === workflowRequest || chat.historyLoading || chat.modelsLoading) return;
    consumedWorkflow.current = workflowRequest;
    if (!workflowEdited.current && chat.modelOptions.some(model => model.id === chat.model && model.available !== false)) chat.submit(chat.draft);
    onWorkflowConsumed?.();
  }, [workflowRequest, thread, chat.draft, chat.historyLoading, chat.modelsLoading, chat.modelOptions, chat.model, chat.submit, onWorkflowConsumed]);
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
