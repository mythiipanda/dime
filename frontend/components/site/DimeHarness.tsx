"use client";

import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import ThinkingState from "@/components/primitives/ThinkingState";
import ToolChips, { type ToolStep } from "@/components/primitives/ToolChips";
import ArtifactShell from "@/components/dime/ArtifactShell";
import ArtifactCompare from "@/components/dime/ArtifactCompare";
import ArtifactChart from "@/components/dime/ArtifactChart";
import ArtifactShotChart from "@/components/dime/ArtifactShotChart";
import ArtifactTable, { type ArtifactColumn } from "@/components/dime/ArtifactTable";
import DimeSidebar from "@/components/site/DimeSidebar";
import DimeCommandPalette, { type PaletteEntry } from "@/components/site/DimeCommandPalette";
import DimeModelPicker, { type PickerModel } from "@/components/site/DimeModelPicker";
import TonightView from "@/components/dime/views/TonightView";
import ExploreView from "@/components/dime/views/ExploreView";
import MatchupsView from "@/components/dime/views/MatchupsView";
import LineupsView from "@/components/dime/views/LineupsView";
import TradesView from "@/components/dime/views/TradesView";
import AwardsView from "@/components/dime/views/AwardsView";
import PropsView from "@/components/dime/views/PropsView";
import SavedView from "@/components/dime/views/SavedView";
import WarehouseView from "@/components/dime/views/WarehouseView";
import {
  answerText,
  compareRows,
  exploreRows,
  followUps,
  lukaTrend,
  sgaTrend,
  sgaZones,
  thinkRows,
  tonightGames,
} from "@/lib/dime-data";
import {
  streamDimeChat,
  failureCopy,
  mergeArtifactProvenance,
  originPhrase,
  undeclaredProvenance,
  verificationDisclosure,
  type DimeArtifact,
  type DimeProvenance,
  type ProvenanceEvidence,
  type StreamSnapshot,
  type ToolState,
  type VerificationCarry,
} from "@/lib/dime-stream";
import { getModels } from "@/lib/api";

function Ico({ d, size = 15 }: { d: React.ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>{d}</svg>
  );
}

const TOOL_STEPS: ToolStep[] = [
  {
    icon: "read", label: "boxscores.query", chip: "per-game scoring · last 30", mono: true, detailMono: true,
    detail: [
      { text: "SELECT player, AVG(pts), AVG(ts_pct)" },
      { text: "FROM player_game_logs · 2 rows · 412ms" },
    ],
  },
  {
    icon: "read", label: "lineups.query", chip: "on/off net rating", mono: true, detailMono: true,
    detail: [
      { text: "SELECT on_court_net, off_court_net" },
      { text: "FROM lineup_data · 2 rows · 388ms" },
    ],
  },
  {
    icon: "write", label: "artifact.build", chip: "scoring trend · last 15", mono: true, detailMono: false,
    detail: [{ text: "2 series rendered · pts by game" }],
  },
];

const TABLE_COLS: ArtifactColumn[] = [
  { key: "player", label: "Player" },
  { key: "team", label: "Team" },
  { key: "gp", label: "GP", numeric: true },
  { key: "ppg", label: "PPG", numeric: true },
  { key: "ts", label: "TS%", numeric: true },
  { key: "usg", label: "USG%", numeric: true },
  { key: "net", label: "Net/100", numeric: true },
];
type PlayerTuple = [string, string, number, number, number, number, number];
const TABLE_ROWS: PlayerTuple[] = exploreRows.map((r) => [r.name, r.team, r.gp, r.ppg, r.ts, r.usg, r.net]);

function renderPlayerCell(row: PlayerTuple, col: number) {
  if (col === 0) return <span className="font-medium text-ink">{row[0]}</span>;
  if (col === 1) return <span className="text-ink-2">{row[1]}</span>;
  if (col === 3) return <span className="text-ink">{row[3].toFixed(1)}</span>;
  if (col === 6)
    return (
      <span className={row[6] >= 9 ? "text-green" : "text-ink-2"}>
        {row[6] > 0 ? "+" : ""}{row[6].toFixed(1)}
      </span>
    );
  const v = row[col];
  return <span className="text-ink-2">{typeof v === "number" ? v.toFixed(col === 2 ? 0 : 1) : v}</span>;
}

function TonightStrip() {
  return (
    <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-3">
      {tonightGames.map((g) => (
        <div key={g.away + g.home} className="min-w-0 bg-surface px-3.5 py-2.5 transition-colors duration-100 hover:bg-hover">
          <div className="flex items-center gap-1.5">
            {g.live && <span className="size-1.5 shrink-0 rounded-full bg-red" />}
            <span className="truncate text-[13px] font-medium text-ink">
              {g.away}<span className="font-normal text-ink-3"> @ </span>{g.home}
            </span>
            <span className="ml-auto shrink-0 font-mono text-[11px] tabular-nums text-ink-3">{g.time}</span>
          </div>
          <div className="mt-1 truncate font-mono text-[11px] tabular-nums text-ink-2">
            {g.line}<span className="text-ink-3"> · {g.ou}</span>
          </div>
          {g.note && <div className="mt-0.5 truncate text-[11px] text-ink-3">{g.note}</div>}
        </div>
      ))}
    </div>
  );
}

function DimeComposer({
  draft,
  setDraft,
  onSubmit,
  inputRef,
  modelOptions,
  model,
  setModel,
}: {
  draft: string;
  setDraft: (v: string) => void;
  onSubmit: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  modelOptions: PickerModel[];
  model: string | null;
  setModel: (v: string | null) => void;
}) {
  const canSend = draft.trim().length > 0;
  return (
    <div className="rounded-control border border-line bg-field p-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.035)] transition-[border-color,box-shadow] duration-150 focus-within:border-line-strong">
      <textarea
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        placeholder="Ask about any team, player, lineup, or market…"
        rows={1}
        className="w-full resize-none bg-transparent px-1 pt-0.5 text-[13.5px] leading-[1.5] text-ink placeholder:text-ink-3 focus:outline-none [@media(pointer:coarse)]:text-base"
      />
      <div className="flex items-center justify-between gap-2 px-1 pb-0.5 pt-1.5">
        <DimeModelPicker
          models={modelOptions}
          value={model}
          onChange={setModel}
          disabled={false}
        />
        <button
          type="button"
          aria-label="Send"
          disabled={!canSend}
          onClick={onSubmit}
           className="flex size-7 items-center justify-center rounded-[8px]
            transition-[background-color,color,transform] duration-150 enabled:active:scale-[0.96]"
          style={{
            background: canSend ? "var(--ink)" : "var(--line-strong)",
            color: canSend ? "var(--surface)" : "var(--ink-2)",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}

type Tab = { id: string; label: string };

const REFERENCE_TAB = "t1";

type ViewKey =
  | "tonight"
  | "explore"
  | "matchups"
  | "lineups"
  | "trades"
  | "awards"
  | "props"
  | "saved"
  | "warehouse";

const VIEWS: Record<ViewKey, ComponentType> = {
  tonight: TonightView,
  explore: ExploreView,
  matchups: MatchupsView,
  lineups: LineupsView,
  trades: TradesView,
  awards: AwardsView,
  props: PropsView,
  saved: SavedView,
  warehouse: WarehouseView,
};

const SHELLED_VIEWS: ReadonlySet<ViewKey> = new Set(["props", "saved", "warehouse"]);
const FLEX_VIEWS: ReadonlySet<ViewKey> = new Set(["lineups", "trades", "awards"]);

function renderView(key: ViewKey) {
  const View = VIEWS[key];
  if (SHELLED_VIEWS.has(key)) return <View key={key} />;
  if (FLEX_VIEWS.has(key))
    return (
      <div
        key={key}
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page"
      >
        <View />
      </div>
    );
  return (
    <div
      key={key}
      className="min-h-0 min-w-0 flex-1 overflow-y-auto rounded-[14px] border border-line bg-page"
    >
      <View />
    </div>
  );
}

type AssistantFailure = { kind: string; message: string };

type ChatMsg =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      artifacts: DimeArtifact[];
      suggestions: string[];
      carry: VerificationCarry | null;
      failure: AssistantFailure | null;
    };

export type LiveRun = StreamSnapshot & { id: number; startedAt: number };

export function assistantMessageFromSnapshot(
  snap: StreamSnapshot,
  message: string,
): Extract<ChatMsg, { role: "assistant" }> {
  return {
    role: "assistant",
    text: snap.text,
    artifacts: snap.artifacts,
    suggestions: snap.suggestions,
    carry: snap.carry,
    failure: snap.failed ?? (message ? { kind: "connection", message } : null),
  };
}

function toolStepFor(tool: ToolState): ToolStep {
  const summary =
    tool.status === "running"
      ? "running"
      : tool.status === "fail"
        ? "failed"
        : [
            tool.rows !== undefined ? `${tool.rows} rows` : null,
            tool.ms !== undefined ? `${tool.ms}ms` : null,
          ]
            .filter(Boolean)
            .join(" · ") || "done";
  const detail = [
    ...(tool.args ?? []),
    ...(tool.error ? [tool.error] : []),
  ].map((text) => ({ text }));
  return {
    icon: "read",
    key: tool.key,
    label: tool.label,
    chip: summary,
    mono: true,
    detailMono: true,
    detail: detail.length ? detail : [{ text: summary }],
    args: tool.args,
  };
}

export function ArtifactBody({ artifact }: { artifact: DimeArtifact }) {
  if (artifact.kind === "table") {
    return <ArtifactTable columns={artifact.columns} rows={artifact.rows} />;
  }
  if (artifact.kind === "compare") {
    return (
      <ArtifactCompare
        rows={artifact.rows.map((r) => ({
          label: r.label,
          a: r.a,
          b: r.b,
          fmt: (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1)),
        }))}
        aName={artifact.aName}
        bName={artifact.bName}
      />
    );
  }
  if (artifact.kind === "chart") {
    const series = artifact.series.filter((s) => s.values.length > 0);
    if (!series.length) return null;
    return (
      <ArtifactChart
        series={series.map((s, i) => ({
          name: s.name,
          values: s.values,
          tone: i === 0 ? "ink" : "muted",
        }))}
        footnote={artifact.footnote}
      />
    );
  }
  if (artifact.kind === "shot_chart") {
    if (!artifact.zones.length) return null;
    return <ArtifactShotChart zones={artifact.zones} />;
  }
  return null;
}

function FailureCard({ failure }: { failure: AssistantFailure }) {
  const copy = failureCopy(failure.kind);
  return (
    <div
      className="mt-4 max-w-[620px] rounded-xl border border-line bg-surface px-3.5 py-3 shadow-hairline"
      style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both" }}
    >
      <div className="text-[13px] font-medium text-ink">{copy.title}</div>
      <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{copy.body}</p>
    </div>
  );
}

function ProvenanceRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-[92px] shrink-0 text-ink-3">{label}</dt>
      <dd className="min-w-0 flex-1 break-words text-ink-2">{children}</dd>
    </div>
  );
}

function ProvenanceFields({ provenance }: { provenance: DimeProvenance }) {
  return (
    <>
      <ProvenanceRow label="Capability">{provenance.capability ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="Origin">{originPhrase(provenance)}</ProvenanceRow>
      {provenance.warehouseId && (
        <ProvenanceRow label="Warehouse">{provenance.warehouseId}</ProvenanceRow>
      )}
      <ProvenanceRow label="Season">{provenance.season ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="As of">{provenance.asOf ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="Live sources">
        {provenance.liveSources.length > 0 || (provenance.liveSourceIds?.length ?? 0) > 0 ? (
          <span className="flex flex-col gap-0.5">
            {provenance.liveSources.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="break-all text-ink underline decoration-line-strong underline-offset-2"
              >
                {url}
              </a>
            ))}
            {(provenance.liveSourceIds ?? []).map((id) => (
              <span key={id} className="break-all text-ink-2">
                {id}
              </span>
            ))}
          </span>
        ) : (
          "none provided"
        )}
      </ProvenanceRow>
    </>
  );
}

export function ProvenancePanel({ provenance }: { provenance: DimeProvenance }) {
  const evidence: ProvenanceEvidence[] = provenance.evidence?.length
    ? provenance.evidence
    : [{ label: "", provenance }];
  return (
    <details className="mt-3 rounded-[10px] border border-line bg-field px-3 py-2">
      <summary className="cursor-pointer text-[12px] font-medium text-ink-2">
        Sources &amp; provenance
      </summary>
      <dl className="mt-2 flex flex-col gap-2.5 text-[12px] leading-relaxed">
        {evidence.map((entry, i) => (
          <div key={i} className="flex flex-col gap-1">
            {entry.label && <div className="font-medium text-ink-2">{entry.label}</div>}
            <ProvenanceFields provenance={entry.provenance} />
          </div>
        ))}
      </dl>
    </details>
  );
}

export function StreamArtifacts({ artifacts }: { artifacts: DimeArtifact[] }) {
  if (artifacts.length === 0) return null;
  return (
    <div className="mt-5 flex flex-col gap-4">
      {artifacts.map((artifact, i) => (
        <ArtifactShell
          key={i}
          title={artifact.title}
          source={artifact.source}
          delay={i * 40}
        >
          <ArtifactBody artifact={artifact} />
          <ProvenancePanel provenance={artifact.provenance ?? undeclaredProvenance()} />
        </ArtifactShell>
      ))}
    </div>
  );
}

export function AnswerVerification({
  carry,
  artifacts,
}: {
  carry: VerificationCarry | null;
  artifacts: DimeArtifact[];
}) {
  const provenance = mergeArtifactProvenance(artifacts);
  if (!carry && !provenance) return null;
  const disclosure = verificationDisclosure(carry, provenance);
  return (
    <div className="mt-3 max-w-[620px] rounded-[10px] border border-line bg-field px-3 py-2.5">
      <div className="text-[12px] font-medium text-ink">{disclosure.headline}</div>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-2">{disclosure.detail}</p>
      {carry && (
        <p className="mt-1 text-[11.5px] text-ink-3">
          {`Verification status: ${carry.verification === "unknown" ? "not reported" : carry.verification}`}
        </p>
      )}
      {disclosure.gaps.length > 0 && (
        <ul className="mt-1.5 flex flex-col gap-0.5">
          {disclosure.gaps.map((gap, i) => (
            <li key={i} className="text-[11.5px] leading-relaxed text-ink-3">
              {`Gap: ${gap.kind}${gap.blocks.length ? ` · blocks ${gap.blocks.join(", ")}` : ""}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const FADE_UP = "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both";

function FollowUpPills({
  items,
  onPick,
}: {
  items: string[];
  onPick: (s: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {items.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onPick(s)}
          className="rounded-full bg-surface px-3 py-1.5 text-left text-[12px] text-ink shadow-btn transition-[background-color,transform] duration-150 hover:bg-hover active:scale-[0.97]"
        >
          {s}
        </button>
      ))}
    </div>
  );
}

function LiveStatus({
  label,
  secs,
  done,
}: {
  label: string;
  secs: number;
  done: boolean;
}) {
  if (done) {
    return (
      <div
        className="text-[13px] font-medium text-ink-2"
        style={{ animation: FADE_UP }}
      >
        {`Thought for ${secs} seconds`}
      </div>
    );
  }
  return (
    <span role="status" className="contents">
      <span
        className="bg-clip-text text-[13px] font-medium whitespace-nowrap text-transparent"
        style={{
          backgroundImage:
            "linear-gradient(90deg, var(--ink-3) 35%, var(--ink) 50%, var(--ink-3) 65%)",
          backgroundSize: "200% 100%",
          animation:
            "shimmer-text 1.4s linear infinite, fade-up 280ms cubic-bezier(0.23,1,0.32,1) both",
        }}
      >
        {label}
      </span>
    </span>
  );
}

export function LiveAssistant({ live }: { live: LiveRun }) {
  const steps = live.tools.map(toolStepFor);
  const secs = Math.max(1, Math.round((Date.now() - live.startedAt) / 1000));
  const statusLine = live.thinking.length
    ? live.thinking[live.thinking.length - 1].label
    : "Thinking";
  return (
    <>
      <div className="mt-2">
        <LiveStatus
          key={`${live.id}:${live.thinking.length}`}
          label={statusLine}
          secs={secs}
          done={live.done}
        />
      </div>
      {steps.length > 0 && (
        <div className="mt-3">
          <ToolChips
            steps={steps}
            diffs={[]}
            labels={{
              header: `${steps.length} tool call${steps.length === 1 ? "" : "s"}`,
              more: "",
            }}
          />
        </div>
      )}
      <StreamArtifacts artifacts={live.artifacts} />
      {live.text && (
        <p className="mt-4 max-w-[620px] whitespace-pre-line text-[13.5px] leading-[1.65] text-ink-2">
          {live.text}
        </p>
      )}
      <AnswerVerification carry={live.carry} artifacts={live.artifacts} />
      {live.failed && <FailureCard failure={live.failed} />}
    </>
  );
}

export function AssistantTurn({
  text,
  artifacts,
  suggestions,
  carry,
  failure,
  onFollowUp,
}: {
  text: string;
  artifacts: DimeArtifact[];
  suggestions: string[];
  carry: VerificationCarry | null;
  failure: AssistantFailure | null;
  onFollowUp: (s: string) => void;
}) {
  return (
    <>
      <StreamArtifacts artifacts={artifacts} />
      {text && (
        <p
          className="mt-4 max-w-[620px] whitespace-pre-line text-[13.5px] leading-[1.65] text-ink-2"
          style={{ animation: FADE_UP }}
        >
          {text}
        </p>
      )}
      <AnswerVerification carry={carry} artifacts={artifacts} />
      {failure && <FailureCard failure={failure} />}
      <FollowUpPills items={suggestions} onPick={onFollowUp} />
    </>
  );
}

export default function DimeHarness() {
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
      const next = remaining.length > 0 ? remaining : [{ id: `t${Date.now()}`, label: "New analysis" }];
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
    let live = true;
    getModels()
      .then((res) => {
        if (live) {
          setModelOptions(
            res.models.map((m) => ({
              id: m.id,
              engine: m.engine,
              label: m.id.split(":").slice(1).join(":").replace(/:free$/, ""),
              default: m.default,
              available: m.available,
            })),
          );
        }
      })
      .catch(() => undefined);
    return () => {
      live = false;
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

  const paletteEntries: PaletteEntry[] = useMemo(
    () => [
      { id: "view-chat", label: "Chat", kind: "view", run: () => setActiveView("chat") },
      { id: "view-tonight", label: "Tonight", kind: "view", run: () => setActiveView("tonight") },
      { id: "view-explore", label: "Explore", kind: "view", run: () => setActiveView("explore") },
      { id: "view-matchups", label: "Matchups", kind: "view", run: () => setActiveView("matchups") },
      { id: "view-lineups", label: "Lineups", kind: "view", run: () => setActiveView("lineups") },
      { id: "view-trades", label: "Trades", kind: "view", run: () => setActiveView("trades") },
      { id: "view-awards", label: "Awards", kind: "view", run: () => setActiveView("awards") },
      { id: "view-props", label: "Props", kind: "view", run: () => setActiveView("props") },
      { id: "view-saved", label: "Saved", kind: "view", run: () => setActiveView("saved") },
      { id: "view-warehouse", label: "Warehouse", kind: "view", run: () => setActiveView("warehouse") },
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
    []
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages, live]);

  const pickFollowUp = (f: string) => {
    submit(f);
  };

  return (
    <main className="flex h-[100dvh] gap-0 overscroll-none bg-canvas p-2.5 text-ink lg:pl-0">
      <DimeSidebar
        activeNav={activeView}
        onNavChange={(key: string) => setActiveView(key as "chat" | ViewKey)}
        onNewAnalysis={() => {
          setActiveView("chat");
          addTab();
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-2.5">
        <div className="flex h-12 shrink-0 items-center gap-1 rounded-[14px] border border-line bg-page px-1 lg:hidden">
          <button
            ref={menuBtnRef}
            type="button"
            aria-label="Open navigation"
            aria-expanded={mobileNavOpen}
            onClick={openMobileNav}
            className="flex size-11 shrink-0 touch-manipulation select-none items-center justify-center rounded-[8px] text-ink-2 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <span className="min-w-0 flex-1 truncate px-1 text-[14px] font-medium text-ink">Dime</span>
          <button
            type="button"
            aria-label="New analysis"
            onClick={() => {
              setActiveView("chat");
              addTab();
            }}
            className="flex size-11 shrink-0 touch-manipulation select-none items-center justify-center rounded-[8px] text-ink-2 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
        </div>
        <div className="flex min-h-0 flex-1 gap-2.5">
          {activeView === "chat" ? (
          <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
            <div className="flex h-11 shrink-0 items-center gap-1 overflow-x-auto border-b border-line px-2">
              {tabs.map((t) => (
                <span
                  key={t.id}
                  className={`flex h-7 shrink-0 items-center gap-1 rounded-[7px] pr-1 transition-[background-color,color] duration-150 ${
                    activeTab === t.id ? "bg-hover text-ink" : "text-ink-3 hover:bg-hover hover:text-ink-2"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setActiveTab(t.id)}
                    className="flex h-full max-w-[180px] items-center truncate px-2 text-[12.5px] font-medium transition-transform duration-150 active:scale-[0.97]"
                  >
                    {t.label}
                  </button>
                  {tabs.length > 1 && (
                    <button
                      type="button"
                      aria-label={`Close ${t.label}`}
                      onClick={() => closeTab(t.id)}
                      className="mr-0.5 flex size-6 shrink-0 items-center justify-center rounded-[5px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-page hover:text-ink active:scale-[0.9]"
                    >
                      <Ico d={<path d="M6 6l12 12M18 6L6 18" />} size={11} />
                    </button>
                  )}
                </span>
              ))}
              <button
                type="button"
                aria-label="New tab"
                onClick={addTab}
                className="flex size-7 shrink-0 items-center justify-center rounded-[7px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.94]"
              >
                <Ico d={<path d="M12 5v14M5 12h14" />} size={14} />
              </button>
            </div>

            <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto w-full max-w-[760px] px-4 py-8 sm:px-8">
                {showReference && (
                  <>
                <div className="mb-3 flex items-center gap-2">
                  <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-ink-3">
                    Sample analysis
                  </span>
                  <span className="text-[11px] text-ink-3">
                    A worked example. Ask anything to start your own.
                  </span>
                </div>
                <div className="flex justify-end pl-10 sm:pl-24" style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both" }}>
                  <div className="rounded-xl bg-field px-3.5 py-2 text-[13px] leading-relaxed text-ink shadow-hairline">
                    Compare SGA and Luka this season — scoring, efficiency, and team impact.
                  </div>
                </div>

                <div className="mt-2">
                  <ThinkingState variant="Steps" rows={thinkRows} done="Thought for 6 seconds" />
                </div>

                <div className="mt-3">
                  <ToolChips
                    steps={TOOL_STEPS}
                    diffs={[]}
                    labels={{ header: "3 warehouse calls", more: "" }}
                  />
                </div>

                <div className="mt-5 flex flex-col gap-4">
                  <ArtifactShell title="Scoring & efficiency — last 30 games" source="silver_boxscores" delay={0}>
                    <ArtifactCompare rows={compareRows} aName="SGA" bName="Dončić" />
                  </ArtifactShell>
                  <ArtifactShell title="Scoring trend — last 15 games" source="silver_boxscores" delay={40}>
                    <ArtifactChart
                      series={[
                        { name: "Gilgeous-Alexander", tone: "ink", values: sgaTrend },
                        { name: "Dončić", tone: "muted", values: lukaTrend },
                      ]}
                      footnote="points per game · last 15"
                    />
                  </ArtifactShell>
                  <ArtifactShell title="Shot chart — Gilgeous-Alexander" source="tracking feed" delay={80}>
                    <ArtifactShotChart zones={sgaZones} />
                  </ArtifactShell>
                </div>

                <p className="mt-5 max-w-[620px] text-[13.5px] leading-[1.65] text-ink-2">{answerText}</p>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {followUps.map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => pickFollowUp(f)}
                      className="rounded-full bg-surface px-3 py-1.5 text-left text-[12px] text-ink shadow-btn transition-[background-color,transform] duration-150 hover:bg-hover active:scale-[0.97]"
                    >
                      {f}
                    </button>
                  ))}
                </div>

                <div className="mt-6">
                  <ArtifactShell title="League scoring" source="silver_boxscores · 8 of 330,485 rows" delay={120}>
                    <ArtifactTable columns={TABLE_COLS} rows={TABLE_ROWS} renderCell={renderPlayerCell} />
                  </ArtifactShell>
                </div>

                <div className="mt-4">
                  <ArtifactShell title="Tonight" source="silver_schedule · 6 games" delay={160}>
                    <TonightStrip />
                  </ArtifactShell>
                </div>
                  </>
                )}
                {messages.map((m, i) =>
                  m.role === "user" ? (
                    <div
                      key={i}
                      className="mt-4 flex justify-end pl-10 sm:pl-24"
                      style={{ animation: FADE_UP }}
                    >
                      <div className="rounded-xl bg-field px-3.5 py-2 text-[13px] leading-relaxed text-ink shadow-hairline">
                        {m.text}
                      </div>
                    </div>
                  ) : (
                    <AssistantTurn
                      key={i}
                      text={m.text}
                      artifacts={m.artifacts}
                      suggestions={m.suggestions}
                      carry={m.carry}
                      failure={m.failure}
                      onFollowUp={pickFollowUp}
                    />
                  )
                )}
                {live && <LiveAssistant live={live} />}
                <div className="h-6" />
              </div>
            </div>

            <div className="shrink-0 px-4 pb-4">
              <div className="mx-auto max-w-[760px]">
                <DimeComposer draft={draft} setDraft={setDraft} onSubmit={() => submit()} inputRef={inputRef}
                  modelOptions={modelOptions} model={model} setModel={setModel} />
              </div>
            </div>
          </section>
          ) : (
            renderView(activeView)
          )}
        </div>
      </div>
      {mobileNavOpen && (
        <div role="dialog" aria-modal="true" aria-label="Dime navigation" className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={closeMobileNav}
            className="absolute inset-0 cursor-default bg-black/45 transition-opacity duration-200 ease-out"
            style={{ opacity: mobileNavShown ? 1 : 0 }}
          />
          <div
            ref={sheetRef}
            className="absolute left-0 top-0 h-[100dvh] w-[300px] max-w-[85vw] border-r border-line bg-page pt-2 shadow-overlay transition-transform duration-200 ease-out [&_[data-row]]:min-h-[44px] [&_.sidebar-collapse-control]:size-11"
            style={{ transform: mobileNavShown ? "translateX(0)" : "translateX(-102%)" }}
          >
            <DimeSidebar
              forceVisible
              activeNav={activeView}
              onRequestClose={closeMobileNav}
              onNavChange={(key: string) => {
                setActiveView(key as "chat" | ViewKey);
                closeMobileNav();
              }}
              onNewAnalysis={() => {
                setActiveView("chat");
                addTab();
                closeMobileNav();
              }}
            />
          </div>
        </div>
      )}
      <DimeCommandPalette open={paletteOpen} entries={paletteEntries} onClose={() => setPaletteOpen(false)} />
    </main>
  );
}
