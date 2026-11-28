"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PaletteEntry } from "@/components/site/DimeCommandPalette";
import type { PickerModel } from "@/components/site/DimeModelPicker";
import { getModels } from "@/lib/api";
import { cacheChatRun, loadChatRuns } from "@/lib/chat-persistence";
import { modelDisplayName } from "@/lib/modelNames";
import { streamDimeChat } from "@/lib/dime-stream";
import { serializeViewContext, splitViewContext } from "@/lib/view-context";
import { clearChatDraft, loadChatDraft, saveChatDraft } from "@/lib/chat-drafts";
import { isAtBottom, scrolledUp } from "@/lib/scroll";
import {
  assistantMessageFromSnapshot,
  REFERENCE_TAB,
  type ChatMsg,
  type LiveRun,
  type Tab,
  type ViewKey,
} from "./types";

const VIEW_LABELS: { id: "chat" | ViewKey; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "matchups", label: "Matchups" },
  { id: "trades", label: "Trades" },
  { id: "awards", label: "Awards" },
  { id: "warehouse", label: "Warehouse" },
];

export function useDimeChat(options?: { thread: string; replay?: string | null; onRunDone?: (question: string) => void; onSubmit?: () => void }) {
  const [tabs, setTabs] = useState<Tab[]>([{ id: REFERENCE_TAB, label: "New analysis" }]);
  const [activeTab, setActiveTab] = useState(REFERENCE_TAB);
  const [messagesByTab, setMessagesByTab] = useState<Record<string, ChatMsg[]>>({});
  const [modelOptions, setModelOptions] = useState<PickerModel[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"chat" | ViewKey>("chat");
  const thread = options?.thread;
  const messages = messagesByTab[thread ?? activeTab] ?? [];
  const [historyLoading, setHistoryLoading] = useState(!!thread);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [providers, setProviders] = useState<string[]>([]);
  const [modelsAttempt, setModelsAttempt] = useState(0);
  const showReference = activeTab === REFERENCE_TAB && messages.length === 0;
  const [live, setLive] = useState<LiveRun | null>(null);
  const [draft, setDraftState] = useState(() => loadChatDraft(options?.thread ?? "") ?? "");
  const setDraft = (text: string) => {
    setDraftState(text);
    saveChatDraft(options?.thread ?? "", text);
  };
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobileNavShown, setMobileNavShown] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const menuBtnRef = useRef<HTMLButtonElement | null>(null);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const liveId = useRef(0);
  const liveQuestion = useRef("");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!thread) return;
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    void loadChatRuns(thread).then(runs => {
      if (!cancelled) setMessagesByTab(current => ({ ...current, [thread]: runs.flatMap(({ question, snapshot }): ChatMsg[] => [
        { role: "user", text: question }, assistantMessageFromSnapshot(snapshot, ""),
      ]) }));
    }).catch(() => { if (!cancelled) setHistoryError("Could not load this conversation."); })
      .finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [thread]);

  const addTab = () => {
    const id = `t${Date.now()}`;
    setTabs((t) => [...t, { id, label: "New analysis" }]);
    setMessagesByTab((m) => ({ ...m, [id]: [] }));
    setActiveTab(id);
  };

  const closeTab = (id: string) => {
    setTabs((current) => {
      const remaining = current.filter((t) => t.id !== id);
      const next =
        remaining.length > 0 ? remaining : [{ id: `t${Date.now()}`, label: "New analysis" }];
      setActiveTab((was) => (was === id ? next[next.length - 1].id : was));
      return next;
    });
    setMessagesByTab((m) => {
      const next = { ...m };
      delete next[id];
      return next;
    });
  };

  const appendMessage = (tabId: string, message: ChatMsg) => {
    setMessagesByTab((m) => ({ ...m, [tabId]: [...(m[tabId] ?? []), message] }));
  };

  const runSubmission = (q: string, context: import("@/lib/view-context").ViewContext | undefined, tabId: string) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    liveId.current += 1;
    const id = liveId.current;
    const startedAt = Date.now();
    liveQuestion.current = q;
    const turnText = context ? serializeViewContext(context, q) : q;
    setLive({
      id,
      startedAt,
      text: "",
      thinking: [],
      tools: [],
      artifacts: [],
      suggestions: [],
      carry: null,
      failed: null,
      done: false,
    });
    streamDimeChat(
      q,
      {
        onUpdate: (snap) =>
          setLive((cur) => (cur && cur.id === id ? { ...cur, ...snap } : cur)),
        onDone: (snap) => {
          if (liveId.current !== id) return;
          setLive((cur) => (cur && cur.id === id ? null : cur));
          appendMessage(tabId, assistantMessageFromSnapshot(snap, ""));
          if (thread && !options?.replay) {
            cacheChatRun(thread, turnText, snap);
            options?.onRunDone?.(q);
          }
        },
        onError: (snap, message) => {
          if (liveId.current !== id) return;
          setLive((cur) => (cur && cur.id === id ? null : cur));
          appendMessage(tabId, assistantMessageFromSnapshot(snap, message));
          if (thread && !options?.replay) { cacheChatRun(thread, turnText, snap); options?.onRunDone?.(q); }
        },
      },
      { signal: ctrl.signal, model, thread, replay: options?.replay, turn: messages.filter(m => m.role === "assistant").length, ...(context ? { context } : {}) },
    );
  };

  const canSubmit = () => !live && !historyLoading && (options?.replay || modelOptions.some(item => item.id === model && item.available !== false));

  const submit = (raw?: string, context?: import("@/lib/view-context").ViewContext) => {
    const q = (raw ?? draft).trim();
    if (!q || !canSubmit()) return;
    options?.onSubmit?.();
    const tabId = thread ?? activeTab;
    const turnText = context ? serializeViewContext(context, q) : q;
    followingRef.current = true;
    appendMessage(tabId, { role: "user", text: turnText });
    setDraftState("");
    clearChatDraft(options?.thread ?? "");
    runSubmission(q, context, tabId);
  };

  const retry = (index: number) => {
    const tabId = thread ?? activeTab;
    const msgs = messagesByTab[tabId] ?? [];
    const failedMsg = msgs[index];
    if (!failedMsg || failedMsg.role !== "assistant" || !failedMsg.failure || !canSubmit()) return;
    let userText: string | null = null;
    for (let i = index - 1; i >= 0; i -= 1) {
      if (msgs[i].role === "user") { userText = msgs[i].text; break; }
    }
    if (!userText) return;
    const { context, text } = splitViewContext(userText);
    setMessagesByTab((m) => ({ ...m, [tabId]: (m[tabId] ?? []).filter((_, i) => i !== index) }));
    runSubmission(text, context ?? undefined, tabId);
  };

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    let active = true;
    setModelsError(false);
    setModelsLoading(true);
    getModels()
      .then((res) => {
        if (!active) return;
        setProviders(Object.keys(res.available ?? {}));
        setModelOptions(
          res.models.map((m) => ({
            id: m.id,
            engine: m.engine,
            label: modelDisplayName(m.id),
            default: m.default,
            available: m.available,
          })),
        );
        const available = res.models.filter(m => m.available !== false);
        setModel(current => current ?? available.find(m => m.default)?.id ?? available[0]?.id ?? null);
      })
      .catch(() => { if (active) setModelsError(true); }).finally(() => { if (active) setModelsLoading(false); });
    return () => {
      active = false;
    };
  }, [modelsAttempt]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openMobileNav = () => {
    setMobileNavOpen(true);
    window.setTimeout(() => setMobileNavShown(true), 0);
  };

  const closeMobileNav = () => {
    setMobileNavShown(false);
    window.setTimeout(() => {
      setMobileNavOpen(false);
      menuBtnRef.current?.focus();
    }, 200);
  };

  useEffect(() => {
    if (!mobileNavOpen) return;
    const t = window.setTimeout(() => {
      sheetRef.current?.querySelector<HTMLElement>("button")?.focus();
    }, 60);
    return () => window.clearTimeout(t);
  }, [mobileNavOpen]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeMobileNav();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  const followingRef = useRef(true);
  const lastScrollTop = useRef(0);

  const onConversationScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    if (scrolledUp(lastScrollTop.current, el.scrollTop)) followingRef.current = false;
    if (isAtBottom(el)) followingRef.current = true;
    lastScrollTop.current = el.scrollTop;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !followingRef.current) return;
    const running = live != null && !live.done;
    el.scrollTo({ top: el.scrollHeight, behavior: running ? "auto" : (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth") });
  }, [messages, live]);

  const paletteEntries: PaletteEntry[] = useMemo(
    () => [
      ...VIEW_LABELS.map((v) => ({
        id: `view-${v.id}`,
        label: v.label,
        kind: "view" as const,
        run: () => setActiveView(v.id),
      })),
      {
        id: "action-new",
        label: "New analysis",
        kind: "action",
        run: () => {
          setActiveView("chat");
          addTab();
        },
      },
      {
        id: "action-collapse",
        label: "Collapse sidebar",
        kind: "action",
        run: () => window.dispatchEvent(new Event("dime:collapse-sidebar")),
      },
      {
        id: "action-clear",
        label: "Clear chat input",
        kind: "action",
        run: () => {
          setActiveView("chat");
          setDraft("");
          inputRef.current?.focus();
        },
      },
    ],
    [],
  );

  return {
    historyLoading,
    historyError,
    modelsError,
    retryModels: () => setModelsAttempt(value => value + 1),
    stop: () => {
      abortRef.current?.abort();
      liveId.current += 1;
      if (live) {
        const snap = { ...live, done: true, halted: true };
        appendMessage(thread ?? activeTab, assistantMessageFromSnapshot(snap, "", true));
        if (thread && !options?.replay) {
          cacheChatRun(thread, liveQuestion.current, snap);
          options?.onRunDone?.(liveQuestion.current);
        }
      }
      setLive(null);
    },
    tabs,
    activeTab,
    setActiveTab,
    messages,
    showReference,
    live,
    draft,
    setDraft,
    modelOptions,
    modelsLoading,
    providers,
    model,
    setModel,
    activeView,
    setActiveView,
    paletteOpen,
    setPaletteOpen,
    paletteEntries,
    mobileNavOpen,
    mobileNavShown,
    openMobileNav,
    closeMobileNav,
    inputRef,
    scrollRef,
    onConversationScroll,
    menuBtnRef,
    sheetRef,
    addTab,
    closeTab,
    submit,
    retry,
  };
}
