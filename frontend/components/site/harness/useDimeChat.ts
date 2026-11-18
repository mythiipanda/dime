"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PaletteEntry } from "@/components/site/DimeCommandPalette";
import type { PickerModel } from "@/components/site/DimeModelPicker";
import { getModels } from "@/lib/api";
import { streamDimeChat } from "@/lib/dime-stream";
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
  { id: "tonight", label: "Tonight" },
  { id: "explore", label: "Explore" },
  { id: "matchups", label: "Matchups" },
  { id: "lineups", label: "Lineups" },
  { id: "trades", label: "Trades" },
  { id: "awards", label: "Awards" },
  { id: "props", label: "Props" },
  { id: "saved", label: "Saved" },
  { id: "warehouse", label: "Warehouse" },
];

export function useDimeChat() {
  const [tabs, setTabs] = useState<Tab[]>([{ id: REFERENCE_TAB, label: "New analysis" }]);
  const [activeTab, setActiveTab] = useState(REFERENCE_TAB);
  const [messagesByTab, setMessagesByTab] = useState<Record<string, ChatMsg[]>>({});
  const [modelOptions, setModelOptions] = useState<PickerModel[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"chat" | ViewKey>("chat");
  const messages = messagesByTab[activeTab] ?? [];
  const showReference = activeTab === REFERENCE_TAB && messages.length === 0;
  const [live, setLive] = useState<LiveRun | null>(null);
  const [draft, setDraft] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [mobileNavShown, setMobileNavShown] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const menuBtnRef = useRef<HTMLButtonElement | null>(null);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const liveId = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

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

  const submit = (raw?: string) => {
    const q = (raw ?? draft).trim();
    if (!q || live) return;
    const tabId = activeTab;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    liveId.current += 1;
    const id = liveId.current;
    const startedAt = Date.now();
    appendMessage(tabId, { role: "user", text: q });
    setDraft("");
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
          setLive((cur) => (cur && cur.id === id ? null : cur));
          appendMessage(tabId, assistantMessageFromSnapshot(snap, ""));
        },
        onError: (snap, message) => {
          setLive((cur) => (cur && cur.id === id ? null : cur));
          appendMessage(tabId, assistantMessageFromSnapshot(snap, message));
        },
      },
      { signal: ctrl.signal, model },
    );
  };

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    let active = true;
    getModels()
      .then((res) => {
        if (!active) return;
        setModelOptions(
          res.models.map((m) => ({
            id: m.id,
            engine: m.engine,
            label: m.id.split(":").slice(1).join(":").replace(/:free$/, ""),
            default: m.default,
            available: m.available,
          })),
        );
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

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

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
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
    tabs,
    activeTab,
    setActiveTab,
    messages,
    showReference,
    live,
    draft,
    setDraft,
    modelOptions,
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
    menuBtnRef,
    sheetRef,
    addTab,
    closeTab,
    submit,
  };
}
