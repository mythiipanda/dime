"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import { PromptBar } from "../ds/PromptBar";
import { CitationChip } from "../ds/CitationChip";
import { EvidenceTrace } from "../ds/EvidenceTrace";
import { StreamingText } from "../ds/StreamingText";
import { AnswerVerification, OmittedNote, StoppedNote } from "../site/harness/AnswerView";
import { StreamArtifacts } from "../site/harness/ArtifactsView";
import { useDimeChat } from "../site/harness/useDimeChat";
import type { ChatMsg } from "../site/harness/types";
import type { DimeArtifact, ToolState, VerificationCarry } from "../../lib/dime-stream";
import { citationDetails } from "../../lib/citation-details";
import { failureCopy } from "../../lib/stream/labels";
import { clearWorkflowDraft, createWorkflowDraft, loadWorkflowDraft, saveWorkflowDraft, workflowDraftWasSent, type WorkflowDraft } from "../../lib/workflow-drafts";
import { splitViewContext } from "../../lib/view-context";

export const suggestedPrompts = [
  "Can Miami aggregate salaries for Giannis under the apron?",
  "Which five-man units have the best net rating on the Hornets?",
  "Compare Jokić and Kennard on efficiency and usage",
];

export const replayPrompt = "Build a scouting report on Shai Gilgeous-Alexander";

export function UserTurn({ text }: { text: string }) {
  const { context, text: prose } = splitViewContext(text);
  if (!context) return <div className="user-turn">{prose}</div>;
  return <div className="user-turn"><span className="user-turn-context" title="View context attached from the surface you asked this in">{context.summary}</span>{prose}</div>;
}

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

export function FailureNotice({ failure, onRetry }: { failure: { kind: string; message: string }; onRetry?: () => void }) {
  const copy = failureCopy(failure.kind);
  return (
    <div role="alert" className="my-4 flex items-center gap-3 rounded-lg border border-red/25 bg-red-tint px-4 py-3 text-[12px]">
      <div className="flex-1">
        <div className="font-medium text-ink">{copy.title}</div>
        <p className="mt-0.5 leading-relaxed text-ink-2">{copy.body}</p>
      </div>
      {onRetry && <button className="failure-retry" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function CopyAnswerButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <div className="mt-1 flex items-center">
      <button
        className="icon-button -ml-1.5 text-ink-3"
        aria-label={copied ? "Copied" : "Copy answer"}
        onClick={() => {
          void navigator.clipboard.writeText(text).then(() => setCopied(true));
        }}
      >
        {copied ? <Check width={13} height={13} /> : <Copy width={13} height={13} />}
      </button>
    </div>
  );
}

export function AssistantTurn({ message, prefix, thread, onFollowUp, onRetry }: { message: Extract<ChatMsg, { role: "assistant" }>; prefix: string; thread?: string; onFollowUp: (text: string) => void; onRetry?: () => void }) {
  return <article className="assistant-turn">
    <EvidenceTrace busy={false} thinking={message.thinking ?? []} tools={message.tools ?? []} />
    <PiAnswer text={message.text} carry={message.carry} prefix={prefix} />
    {message.carry?.submission?.omitted?.length ? <OmittedNote omitted={message.carry.submission.omitted} /> : null}
    {message.stopped ? <StoppedNote /> : null}
    <StreamArtifacts artifacts={message.artifacts} shareContext={message.carry?.runId && thread ? { run_id: message.carry.runId, thread } : undefined} />
    <AnswerVerification carry={message.carry} artifacts={message.artifacts} prefix={prefix} />
    {message.failure && <FailureNotice failure={message.failure} onRetry={onRetry} />}
    {message.text && <CopyAnswerButton text={message.text} />}
    {message.suggestions.map(suggestion => <button key={suggestion} className="suggestion-row text-[12px]" onClick={() => onFollowUp(suggestion)}>{suggestion}</button>)}
  </article>;
}

export function LiveTurn({ live, thread }: { live: { thinking: { label: string }[]; tools: ToolState[]; text: string; carry: VerificationCarry | null; artifacts: DimeArtifact[] }; thread: string }) {
  return (
    <article className="assistant-turn" aria-label="Dime response">
      <EvidenceTrace busy thinking={live.thinking} tools={live.tools} />
      <StreamingText streaming><PiAnswer text={live.text} carry={live.carry} prefix={`${thread}-live-`} /></StreamingText>
      <StreamArtifacts artifacts={live.artifacts} shareContext={live.carry?.runId ? { run_id: live.carry.runId, thread } : undefined} />
    </article>
  );
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
    if (workflowDraft.request === workflowRequest.text && chat.modelOptions.some(model => model.id === chat.model && model.available !== false)) chat.submit(workflowDraft.text, workflowDraft.context);
    onWorkflowConsumed?.();
  }, [workflowRequest, workflowDraft, workflowSent, thread, chat.draft, chat.historyLoading, chat.modelsLoading, chat.live, chat.modelOptions, chat.model, chat.submit, onWorkflowConsumed]);
  const replayStarted = useRef(false);
  useEffect(() => {
    if (!replay || chat.historyLoading || replayStarted.current) return;
    replayStarted.current = true;
    chat.submit(replayPrompt);
  }, [replay, chat.historyLoading, chat.submit]);
  const busy = !!chat.live;
  const submitWithContext = (text?: string) => chat.submit(text, workflowDraft?.context);
  const pendingContext = workflowDraft?.context ?? null;
  const composer = <>{pendingContext && <div className="composer-context"><span>{pendingContext.summary}</span></div>}<PromptBar value={chat.draft} onChange={changeDraft} onSend={submitWithContext} onStop={chat.stop} busy={busy || chat.historyLoading} models={chat.modelOptions} model={chat.model} onModelChange={chat.setModel} modelError={chat.modelsError} onRetry={chat.retryModels} providers={chat.providers} modelsLoading={chat.modelsLoading} /></>;
  const empty = chat.messages.length === 0 && !chat.live;
  return <div className="chat-view">
    {replay && <div className="border-b border-line bg-inset px-6 py-2 text-center text-[11px] text-ink-2">Development replay · illustrative data, not live analysis</div>}
    {empty ? <section className="chat-empty">
      <h1><span>Your front office, on demand.</span>What are we looking into?</h1>
      {composer}
      <div className="mt-6 space-y-0.5">{suggestedPrompts.map((prompt, index) => <button key={prompt} className="suggestion-row" disabled={chat.historyLoading} onClick={() => changeDraft(prompt)}><span>{prompt}</span></button>)}</div>
      {chat.historyLoading && <p role="status" className="mt-4 text-[12px] text-ink-3">Loading conversation…</p>}
      {chat.historyError && <p role="alert" className="mt-4 text-[12px] text-red">{chat.historyError}</p>}
    </section> : <>
      <div className="conversation" ref={chat.scrollRef} aria-label="Conversation" onScroll={chat.onConversationScroll}>
        {chat.messages.map((message, index) => message.role === "user" ? <UserTurn key={index} text={message.text} /> : <AssistantTurn key={index} message={message} prefix={`${thread}-${index}-`} thread={thread} onFollowUp={chat.submit} onRetry={() => chat.retry(index)} />)}
        {chat.live && <LiveTurn live={chat.live} thread={thread} />}
      </div>
      <div className="composer-dock">{composer}<p className="mt-2 text-center text-[10px] text-ink-3">Dime can make mistakes. Check the evidence before making a decision.</p></div>
    </>}
  </div>;
}
