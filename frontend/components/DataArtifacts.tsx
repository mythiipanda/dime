"use client";

import { useEffect, useState } from "react";
import { AiMessage, NodeName } from "../lib/chat";
import { ArtifactItem } from "./ArtifactCanvas";
import AutoChart from "./AutoChart";
import { buildCitation } from "../lib/api";
import AwardRaceView, { parseAwardRace } from "./AwardRaceView";
import CompareView from "./CompareView";
import CompsView, { parseCompsRows } from "./CompsView";
import CourtHeatmap from "./CourtHeatmap";
import DataTable from "./DataTable";
import Skeleton from "./Skeleton";
import GameLogView, { parseGameLogs } from "./GameLogView";
import HeadToHeadView, { parseHeadToHead } from "./HeadToHeadView";
import ImpactView, { parseImpact } from "./ImpactView";
import LineupMatrixView, { parseLineupMatrix } from "./LineupMatrixView";
import LineupStatsView, { parseLineupStats } from "./LineupStatsView";
import MatchupPreviewView, { parsePreview } from "./MatchupPreviewView";
import { saveBrief } from "../lib/briefs";
import PredictionView, { parsePrediction } from "./PredictionView";
import RegressionView, { parseRegression } from "./RegressionView";
import RestAdvantageView, { parseRestAdvantage } from "./RestAdvantageView";
import RotationCheckView, { parseRotation } from "./RotationCheckView";
import SplitsView, { parseSplits } from "./SplitsView";
import StreaksView, { parseStreaks } from "./StreaksView";
import TradeValueView, { parseTradeValue } from "./TradeValueView";
import TrendChart, { isRaptorRows } from "./TrendChart";
import { Chip, resolveToolName } from "./view-shared";
import WowyCard from "./WowyCard";
import ZoneBars, { isZoneRows } from "./ZoneBars";

const DEBUG_TOOLS = new Set(["run_python", "list_tables", "describe_table"]);
const DEBUG_COLUMNS = new Set(["printed", "out"]);
const DEBUG_NAME_KEYS = new Set(["name", "table", "dataset", "table_name", "tablename"]);

const TOOL_TITLES: Record<string, string> = {
  get_compare: "Player comparison",
  get_preview: "Matchup preview",
  get_wowy: "Wowy",
  get_comps: "Comps",
  get_award_race: "Award race",
  get_trade_value: "Trade value",
  get_matchup_splits: "Matchup splits",
  get_regression_check: "Regression check",
  get_matchup_preview: "Matchup preview",
  get_streaks: "Streaks",
  get_game_prediction: "Game Prediction",
  search_game_logs: "Game Logs",
  get_rotation_check: "Rotation Check",
  get_lineup_stats: "Lineup stats",
  get_rest_advantage: "Rest advantage",
  get_lineup_matchup_matrix: "Lineup matchup matrix",
  get_head_to_head: "Head to head",
  get_impact_estimate: "Impact estimate",
  get_player_ratings: "Player ratings",
  get_leaders: "League leaders",
  get_clutch: "Clutch",
  get_hustle: "Hustle",
  get_rookie_leaders: "Rookie leaders",
  get_lineup_leaders: "Lineup leaders",
  get_shot_compare: "Shot comparison",
  get_shot_zones: "Shot zones",
  get_team_shot_zones: "Team shot zones",
  get_historical_leaders: "Historical leaders",
  get_rapm: "RAPM",
  get_finder: "Finder",
};

type ArtifactTable = {
  tool: string;
  title?: string;
  rows?: unknown;
  verdict?: string;
  meta?: {
    source?: string;
    fetched_at?: string;
    stat_category?: string;
    sql?: string;
    links?: { watch?: string };
    a?: string;
    b?: string;
    season?: string;
    team?: string;
    as_of?: string;
    qualification?: string;
    coverage?: string;
    warnings?: string[];
    estimated?: boolean;
  };
};

function scrubWarehouseNames(value: string): string {
  return value.replace(/\b(?:silver_|bronze_|ext_)[A-Za-z0-9_]+/g, "dataset");
}

function isProduction(): boolean {
  return process.env.NODE_ENV === "production";
}

function humanTitle(tool?: string): string {
  if (tool && TOOL_TITLES[tool]) return TOOL_TITLES[tool];
  if (tool && tool.indexOf("get_") === 0) {
    const words = tool
      .slice(4)
      .split("_")
      .filter((part) => part.length > 0)
      .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1));
    if (words.length > 0) return words.join(" ");
  }
  return "Data";
}

function cleanText(value: unknown): unknown {
  if (typeof value === "string") return scrubWarehouseNames(value);
  if (Array.isArray(value)) return value.map(cleanText);
  if (value !== null && typeof value === "object") {
    const cleaned: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
      if (scrubWarehouseNames(key) !== key) continue;
      cleaned[key] = cleanText(entry);
    }
    return cleaned;
  }
  return value;
}

function innerRows(rows: unknown): unknown {
  if (rows !== null && typeof rows === "object" && !Array.isArray(rows)) {
    const nested = (rows as { rows?: unknown }).rows;
    if (nested !== undefined) return nested;
  }
  return rows;
}

function stripDebugColumns(rows: unknown): unknown {
  const list = innerRows(rows);
  if (!Array.isArray(list)) return rows;
  const kept: unknown[] = [];
  for (const row of list) {
    if (row !== null && typeof row === "object" && !Array.isArray(row)) {
      const stripped: Record<string, unknown> = {};
      for (const [key, entry] of Object.entries(row)) {
        if (!DEBUG_COLUMNS.has(key)) stripped[key] = entry;
      }
      if (Object.keys(stripped).length === 0) continue;
      kept.push(stripped);
    } else {
      kept.push(row);
    }
  }
  if (
    rows !== null &&
    typeof rows === "object" &&
    !Array.isArray(rows) &&
    (rows as { rows?: unknown }).rows !== undefined
  ) {
    return { ...(rows as Record<string, unknown>), rows: kept };
  }
  return kept;
}

function cleanTable(table: ArtifactTable): ArtifactTable {
  return {
    ...table,
    rows: cleanText(stripDebugColumns(table.rows)),
    verdict:
      typeof table.verdict === "string" ? scrubWarehouseNames(table.verdict) : table.verdict,
    meta: cleanText(table.meta) as ArtifactTable["meta"],
  };
}

function parseStringRows(rows: unknown): unknown {
  if (typeof rows !== "string") return rows;
  try {
    const parsed: unknown = JSON.parse(rows);
    if (parsed && typeof parsed === "object") return parsed;
  } catch {
    return rows;
  }
  return rows;
}

function isTableListing(list: unknown[]): boolean {
  if (list.length === 0) return false;
  return list.every((row) => {
    if (row === null || typeof row !== "object" || Array.isArray(row)) return false;
    const keys = Object.keys(row);
    if (keys.length !== 1 || !DEBUG_NAME_KEYS.has(keys[0])) return false;
    const cell = (row as Record<string, unknown>)[keys[0]];
    return (
      typeof cell === "string" &&
      /^[A-Za-z_][A-Za-z0-9_]*$/.test(cell) &&
      cell.indexOf("_") >= 0
    );
  });
}

function isDebugPayload(rows: unknown): boolean {
  const list = innerRows(rows);
  if (typeof list === "string") return isBareRepr(scrubWarehouseNames(list));
  if (!Array.isArray(list) || list.length === 0) return false;
  if (list.every((row) => row === null || typeof row !== "object")) {
    return isBareRepr(scrubWarehouseNames(list.map((row) => String(row)).join(" ")));
  }
  if (
    list.every(
      (row) =>
        row !== null &&
        typeof row === "object" &&
        !Array.isArray(row) &&
        Object.keys(row).length > 0 &&
        Object.keys(row).every((key) => DEBUG_COLUMNS.has(key)),
    )
  ) {
    return true;
  }
  return isTableListing(list);
}

function isBareRepr(value: string): boolean {
  const text = value.trim();
  if (text.length === 0) return true;
  const first = text[0];
  const last = text[text.length - 1];
  const opens = first === "[" || first === "(" || first === "{";
  const closes = last === "]" || last === ")" || last === "}";
  if (!opens || !closes) return false;
  const rest = text.split("dataset").join("");
  const words = rest.match(/[A-Za-z]{3,}/g);
  return !words || words.length < 2;
}

function EvidenceLimitations({ meta }: {
  meta?: { qualification?: string; coverage?: string; warnings?: string[] };
}) {
  const items = [meta?.qualification, meta?.coverage, ...(meta?.warnings ?? [])]
    .filter((item): item is string => Boolean(item));
  if (items.length === 0) return null;
  return (
    <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginTop: 4 }}>
      {items.join(" · ")}
    </div>
  );
}

function CitePill({ title, meta }: {
  title: string;
  meta?: {
    source?: string; fetched_at?: string; season?: string;
    qualification?: string; coverage?: string; warnings?: string[];
  };
}) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="pill-ghost"
      style={{ fontSize: 11, padding: "3px 10px" }}
      title="Copy a source line for this table"
      onClick={() => {
        navigator.clipboard
          .writeText(buildCitation({
            title,
            source: meta?.source,
            fetchedAt: meta?.fetched_at,
            season: meta?.season,
            qualification: meta?.qualification,
            coverage: meta?.coverage,
            warnings: meta?.warnings,
          }))
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

function InlineChart({ rows }: { rows: unknown }) {
  const trend = isRaptorRows(rows);
  const zones = !trend && isZoneRows(rows);
  const [open, setOpen] = useState(trend);
  if (!trend && !zones) return null;
  return (
    <div
      style={{
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "12px 14px",
        marginBottom: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: open ? 8 : 0 }}>
        <button
          type="button"
          className="pill-ghost"
          style={{ fontSize: 11, padding: "2px 10px" }}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide chart" : "Show chart"}
        </button>
      </div>
      {open && (trend ? <TrendChart rows={rows} /> : <ZoneBars rows={rows} />)}
    </div>
  );
}

const ORDER: NodeName[] = ["entry", "data_retrieval", "tools", "analytics", "presentation"];

function flattenHistoricalLeaders(rows: unknown, statLabel?: string): Record<string, unknown>[] | null {
  const source = parseStringRows(rows);
  if (typeof source === "string") return null;
  const root = (source as { rows?: unknown } | null)?.rows ?? source;
  if (!root || typeof root !== "object" || Array.isArray(root)) return null;
  const rec = root as Record<string, unknown>;
  const groups: { season?: unknown; leaders?: unknown }[] = [];
  if (Array.isArray(rec.seasons)) {
    for (const s of rec.seasons) {
      if (!s || typeof s !== "object" || Array.isArray(s)) return null;
      const sr = s as Record<string, unknown>;
      if (!Array.isArray(sr.leaders)) return null;
      groups.push({ season: sr.season_label ?? sr.season, leaders: sr.leaders });
    }
  } else if (Array.isArray(rec.leaders)) {
    groups.push({ leaders: rec.leaders });
  } else {
    return null;
  }
  const valueKey = typeof statLabel === "string" && statLabel ? statLabel : "Value";
  const out: Record<string, unknown>[] = [];
  for (const g of groups) {
    for (const l of g.leaders as unknown[]) {
      if (!l || typeof l !== "object" || Array.isArray(l)) continue;
      const lr = l as Record<string, unknown>;
      out.push({
        Season: g.season ?? lr.season_label ?? lr.season ?? "",
        PLAYER: lr.player ?? "",
        TEAM: lr.team ?? "",
        [valueKey]: typeof lr.value === "number" ? lr.value : (lr.display ?? ""),
        GP: lr.gp ?? "",
      });
    }
  }
  return out.length ? out : null;
}

function SaveBrief({
  table,
  question,
}: {
  table: { rows: unknown; meta?: Record<string, unknown> };
  question?: string;
}) {
  const [savedId, setSavedId] = useState<string | null>(null);
  if (!question) return null;
  if (savedId) {
    return (
      <a
        href="/briefs"
        style={{ fontSize: 12, fontWeight: 500, color: "var(--color-warm-gray)" }}
      >
        Saved · Open briefs
      </a>
    );
  }
  return (
    <button
      type="button"
      className="pill-ghost"
      style={{ fontSize: 12, padding: "3px 10px", marginTop: 8 }}
      onClick={() => {
        const preview = parsePreview(table.rows);
        const title =
          preview && !preview.alreadyPlayed && preview.away && preview.home
            ? `${preview.away} at ${preview.home}`
            : preview && preview.alreadyPlayed && preview.playedMatchup
              ? preview.playedMatchup
              : question.slice(0, 80);
        const doc = saveBrief({ title, question, rows: table.rows, meta: table.meta });
        setSavedId(doc.id);
      }}
    >
      Save brief
    </button>
  );
}

export default function DataArtifacts({
  ai,
  loading,
  onAsk,
  onPinPlayer,
  onOpenArtifact,
  activeArtifactId,
  question,
}: {
  ai: AiMessage;
  loading?: boolean;
  onAsk?: (query: string) => void;
  onPinPlayer?: (playerName: string) => void;
  onOpenArtifact?: (artifact: ArtifactItem) => void;
  activeArtifactId?: string;
  question?: string;
}) {
  const names = ORDER.filter((n) => ai.nodes[n]);
  const [pageState, setPageState] = useState<number | null>(null);
  const [heat, setHeat] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "chart" | "court">("table");
  const [showInline, setShowInline] = useState(false);
  
  


  const [expanded, setExpanded] = useState(true);

  const tables: ArtifactTable[] = [];

  for (const n of names) {
    for (const t of ai.nodes[n]!.tables) {
      const name = resolveToolName(t) ?? t.tool;
      const rows = parseStringRows(t.rows);
      if (isDebugPayload(innerRows(rows))) continue;
      if (isProduction() && DEBUG_TOOLS.has(name ?? "")) continue;
      tables.push(cleanTable({ ...t, rows }));
    }
  }

  const toolOf = (t: { tool?: string; title?: string }) =>
    resolveToolName(t) ?? t.tool;
  
  
  
  
  






  const tableHasContent = (t: {
    rows?: unknown;
    verdict?: string;
    meta?: Record<string, unknown>;
  }) => {
    const rows = (t.rows as { rows?: unknown } | undefined)?.rows ?? t.rows;
    if (Array.isArray(rows))
      return (
        rows.length > 0 && typeof rows[0] === "object" && rows[0] !== null
      );
    if (rows && typeof rows === "object") return Object.keys(rows).length > 0;
    return Boolean(
      t.verdict ||
        (t.meta as { deterministic_answer?: string } | undefined)
          ?.deterministic_answer,
    );
  };
  const contentIdx = tables
    .map((t, i) => (tableHasContent(t) ? i : -1))
    .filter((i) => i >= 0);
  
  
  
  




  const PREFERRED_TOOLS = new Set([
    "get_shot_compare",
    "get_shot_zones",
    "get_team_shot_zones",
    "get_wowy",
    "get_compare",
    "get_preview",
    "get_rapm",
    "get_finder",
    "get_comps",
    "get_award_race",
    "get_trade_value",
    "get_matchup_splits",
    "get_regression_check",
    "get_matchup_preview",
    "get_streaks",
    "get_game_prediction",
    "search_game_logs",
    "get_rotation_check",
    "get_lineup_stats",
    "get_rest_advantage",
    "get_lineup_matchup_matrix",
    "get_head_to_head",
    "get_impact_estimate",
    "get_player_ratings",
    "get_leaders",
    "get_clutch",
    "get_hustle",
    "get_rookie_leaders",
    "get_lineup_leaders",
  ]);
  const preferredPos = contentIdx.findIndex((i) =>
    PREFERRED_TOOLS.has(toolOf(tables[i]) ?? ""),
  );
  const defaultPos =
    preferredPos >= 0 ? preferredPos : contentIdx.length - 1;
  const pos =
    pageState === null
      ? defaultPos
      : Math.max(0, Math.min(pageState, contentIdx.length - 1));
  const table = pos >= 0 ? tables[contentIdx[pos]] : undefined;
  
  


  const emptyState = (
    <div
      style={{
        fontSize: 12,
        color: "var(--color-warm-gray)",
        padding: "12px 4px",
      }}
    >
      No rows returned for this view. Try widening the filters or asking a
      broader question.
    </div>
  );
  const page = pos;
  const setPage = (n: number) =>
    setPageState(Math.max(0, Math.min(n, contentIdx.length - 1)));

  const toolName = toolOf(table ?? {});
  const isShotTool = toolName === "get_shot_zones" || toolName === "get_shot_compare" || toolName === "get_team_shot_zones";
  const historicalRows =
    table && (toolName === "get_historical_leaders" || toolName === undefined)
      ? flattenHistoricalLeaders(
          table.rows,
          (table.meta as { label?: string } | undefined)?.label,
        )
      : null;
  useEffect(() => {
    if (isShotTool) {
      setViewMode("court");
      setExpanded(true);
    } else {
      setViewMode("table");
    }
  }, [toolName, isShotTool]);

  if (!table) {
    if (loading && ai.text) {
      return (
        <div
          style={{
            border: "1px solid var(--color-stone-border)",
            borderRadius: 12,
            padding: "16px",
            background: "var(--color-pure-white)",
            marginTop: 10,
          }}
        >
          <Skeleton lines={3} label="Loading data..." />
        </div>
      );
    }
    return null;
  }

  const artifactId = `${toolName || table.tool || "dataset"}-${page}`;
  const isCanvasOpen = activeArtifactId === artifactId;
  const rawTitle =
    humanTitle(toolName || table.tool).toUpperCase() +
    (table.meta?.stat_category ? ` · ${table.meta.stat_category}` : "");

  if (isCanvasOpen && !showInline) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 8,
          padding: "8px 12px",
          marginTop: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-ink-black)" }}>
            {rawTitle} is open in the data panel
          </span>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowInline(true);
            setExpanded(true);
          }}
          className="pill-ghost interactive-tactile"
          style={{ fontSize: 11, padding: "2px 8px" }}
        >
          Show inline
        </button>
      </div>
    );
  }

  const rowCount = (() => {
    const r: unknown = table.rows;
    if (Array.isArray(r)) return r.length;
    if (r && typeof r === "object") {
      const first = Object.values(r as Record<string, unknown>).find((v) =>
        Array.isArray(v),
      );
      if (Array.isArray(first)) return first.length;
    }
    return null;
  })();

  if (!expanded) {
    return (
      <div
        style={{
          border: "1px solid var(--color-stone-border)",
          borderRadius: 12,
          padding: "10px 14px",
          background: "var(--color-pure-white)",
          marginTop: 10,
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: 1, minWidth: 220 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 13,
              color: "var(--color-ink-black)",
            }}
          >
            {rawTitle}
            {rowCount !== null && (
              <span style={{ fontWeight: 400, color: "var(--color-ash-gray)" }}>
                {" "}
                · {rowCount} rows
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-ash-gray)", marginTop: 2 }}>
            {table.meta?.source ? `Source: ${table.meta.source}` : "Source: NBA data"}
            {table.meta?.fetched_at
              ? ` · ${String(table.meta.fetched_at).slice(0, 10)}`
              : ""}
            {table.meta?.estimated ? (
              <span style={{ marginLeft: 6 }}>
                <Chip tone="accent">Estimated values</Chip>
              </span>
            ) : null}
          </div>
          <EvidenceLimitations meta={table.meta} />
          {table.verdict && (
            <div style={{ fontSize: 12, marginTop: 4, color: "var(--color-ink-black)" }}>
              {table.verdict.length > 160
                ? `${table.verdict.slice(0, 160)}…`
                : table.verdict}
            </div>
          )}
        </div>
        <CitePill title={rawTitle} meta={table.meta} />
        {onOpenArtifact && (
          <button
            type="button"
            className="pill-ghost interactive-tactile"
            style={{
              fontSize: 11,
              padding: "3px 10px",
              borderColor: "var(--color-cyan-edge)",
              color: "var(--color-cyan-edge)",
            }}
            onClick={() => {
              onOpenArtifact({
                id: artifactId,
                tool: toolName || table.tool,
                title: rawTitle,
                rows: table.rows,
                player: (table as { player?: unknown }).player,
                meta: table.meta,
                verdict: table.verdict,
              });
              setShowInline(false);
            }}
            title="Open the full dataset beside the answer"
          >
            Open full data
          </button>
        )}
        <button
          type="button"
          className="pill-ghost interactive-tactile"
          style={{ fontSize: 11, padding: "3px 10px", fontWeight: 600 }}
          onClick={() => setExpanded(true)}
          title="Show the evidence table inline"
        >
          Show data ▸
        </button>
      </div>
    );
  }

  return (

    <div
      className="t-skel-in"
      style={{
        border: "1px solid var(--color-stone-border)",
        borderRadius: 12,
        padding: "16px",
        background: "var(--color-pure-white)",
        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
        marginTop: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
          borderBottom: "1px solid var(--color-stone-border)",
          paddingBottom: 12,
          marginBottom: 12,
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--color-ink-black)" }}>
            {rawTitle}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-ash-gray)", marginTop: 2 }}>
            {table.meta?.source ? `Source: ${table.meta.source}` : "Source: NBA data"}
            {table.meta?.fetched_at ? ` · ${String(table.meta.fetched_at).slice(0, 10)}` : ""}
            {table.meta?.estimated ? (
              <span style={{ marginLeft: 6 }}>
                <Chip tone="accent">Estimated values</Chip>
              </span>
            ) : null}
            {table.meta?.links?.watch && (
              <a
                href={table.meta.links.watch}
                target="_blank"
                rel="noreferrer"
                style={{ marginLeft: 6, color: "var(--color-cyan-edge)" }}
              >
                Watch video
              </a>
            )}
          </div>
          <EvidenceLimitations meta={table.meta} />
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <button
            type="button"
            className="pill-ghost interactive-tactile"
            style={{ fontSize: 11, padding: "3px 10px" }}
            onClick={() => setExpanded(false)}
            title="Collapse this dataset"
          >
            ▸ Collapse
          </button>
          <CitePill title={rawTitle} meta={table.meta} />
          {onOpenArtifact && (
            <button
              type="button"
              className="pill-ghost interactive-tactile"
              style={{
                fontSize: 11,
                padding: "3px 10px",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                borderColor: "var(--color-cyan-edge)",
                color: "var(--color-cyan-edge)",
              }}
              onClick={() => {
                onOpenArtifact({
                  id: artifactId,
                  tool: toolName || table.tool,
                  title: rawTitle,
                  rows: table.rows,
                  player: (table as { player?: unknown }).player,
                  meta: table.meta,
                  verdict: table.verdict,
                });
                setShowInline(false);
              }}
              title="Open the full dataset beside the answer"
            >
              <span>Open full data</span>
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </button>
          )}
          {isShotTool && (
            <button
              className={viewMode === "court" ? "tab-active" : "pill-ghost"}
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={() => setViewMode("court")}
            >
              Court
            </button>
          )}
          <button
            className={viewMode === "table" ? "tab-active" : "pill-ghost"}
            style={{ fontSize: 11, padding: "3px 10px" }}
            onClick={() => setViewMode("table")}
          >
            Table
          </button>
          {!isShotTool && (
            <button
              className={viewMode === "chart" ? "tab-active" : "pill-ghost"}
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={() => setViewMode("chart")}
            >
              Chart
            </button>
          )}
          {viewMode === "table" && (
            <button
              className={heat ? "tab-active" : "pill-ghost"}
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={() => setHeat(!heat)}
              title="Toggle heat map gradient"
            >
              Heat
            </button>
          )}
          {isCanvasOpen && (
            <button
              type="button"
              onClick={() => setShowInline(false)}
              className="pill-ghost interactive-tactile"
              style={{ fontSize: 11, padding: "3px 8px" }}
              title="Hide inline table since canvas is active"
            >
              Minimize
            </button>
          )}
          {contentIdx.length > 1 && (
            <div style={{ display: "flex", gap: 4, marginLeft: 6 }}>
              <button
                className="pill-ghost"
                style={{ fontSize: 11, padding: "3px 8px" }}
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                ‹ Prev
              </button>
              <span
                style={{
                  fontSize: 11,
                  color: "var(--color-warm-gray)",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {page + 1}/{contentIdx.length}
              </span>
              <button
                className="pill-ghost"
                style={{ fontSize: 11, padding: "3px 8px" }}
                disabled={page >= contentIdx.length - 1}
                onClick={() => setPage(page + 1)}
              >
                Next ›
              </button>
            </div>
          )}
        </div>
      </div>

      {!isProduction() && table.meta?.sql && (
        <details
          style={{
            fontSize: 11,
            color: "var(--color-warm-gray)",
            marginBottom: 12,
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 500 }}>
            View SQL
          </summary>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              margin: "6px 0 0",
              background: "var(--color-stone-canvas)",
              padding: 8,
              borderRadius: 6,
              fontSize: 11,
            }}
          >
            {table.meta.sql}
          </pre>
        </details>
      )}

      {!tableHasContent(table) ? (
        emptyState
      ) : toolName === "get_compare" || toolName === "get_preview" ? (
        <CompareView rows={table.rows} />
      ) : toolName === "get_wowy" ? (
        <WowyCard
          rows={table.rows}
          verdict={table.verdict}
        />
      ) : toolName === "get_comps" && parseCompsRows(table.rows) ? (
        <CompsView
          rows={table.rows}
          target={(table as { player?: unknown }).player}
          meta={table.meta as { similarity?: string; season?: string } | undefined}
        />
      ) : toolName === "get_award_race" && parseAwardRace(table.rows) ? (
        <AwardRaceView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_trade_value" && parseTradeValue(table.rows) ? (
        <TradeValueView rows={table.rows} />
      ) : toolName === "get_matchup_splits" && parseSplits(table.rows) ? (
        <SplitsView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_regression_check" && parseRegression(table.rows) ? (
        <RegressionView rows={table.rows} />
      ) : toolName === "get_matchup_preview" && parsePreview(table.rows) ? (
        <>
          <MatchupPreviewView rows={table.rows} meta={table.meta} />
          <SaveBrief
            table={{
              rows: table.rows,
              meta: table.meta as Record<string, unknown> | undefined,
            }}
            question={question}
          />
        </>
      ) : toolName === "get_streaks" && parseStreaks(table.rows) ? (
        <StreaksView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_game_prediction" &&
        parsePrediction(table.rows ?? table) ? (
        <PredictionView rows={table.rows ?? table} meta={table.meta} />
      ) : toolName === "search_game_logs" && parseGameLogs(table.rows) ? (
        <GameLogView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_rotation_check" && parseRotation(table.rows) ? (
        <RotationCheckView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_lineup_stats" && parseLineupStats(table.rows) ? (
        <LineupStatsView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_rest_advantage" && parseRestAdvantage(table.rows) ? (
        <RestAdvantageView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_lineup_matchup_matrix" && parseLineupMatrix(table.rows) ? (
        <LineupMatrixView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_head_to_head" && parseHeadToHead(table.rows) ? (
        <HeadToHeadView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_impact_estimate" &&
        parseImpact(table.rows ?? table) ? (
        <ImpactView rows={table.rows ?? table} meta={table.meta} />
      ) : isShotTool && viewMode === "court" ? (
        <CourtHeatmap
          rows={table.rows}
          meta={table.meta}
          verdict={table.verdict}
        />
      ) : toolName === "run_python" ? (
        <div
          style={{
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            padding: 12,
            borderRadius: 8,
            fontFamily: "monospace",
            fontSize: 12,
            overflowX: "auto",
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: "var(--color-warm-gray)",
              marginBottom: 6,
              fontWeight: 500,
            }}
          >
            Python Execution Output:
          </div>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
            {(() => {
              const raw = String(
                (table.rows as Record<string, unknown>)?.printed ||
                  (table.rows as Record<string, unknown>)?.out ||
                  "",
              );
              if (!raw.trim())
                return "The script ran but produced no readable output.";
              const scrubbed = scrubWarehouseNames(raw);
              if (isBareRepr(scrubbed))
                return "The script ran but produced no readable output.";
              return scrubbed;
            })()}
          </pre>
        </div>
      ) : historicalRows ? (
        <DataTable
          rows={historicalRows}
          heat={heat}
          onPlayerSelect={(player) =>
            onAsk ? onAsk(`Tell me about ${player} this season`) : undefined
          }
          onPinPlayer={onPinPlayer}
        />
      ) : viewMode === "chart" ? (
        <AutoChart table={table as { rows?: unknown }} />
      ) : (
        <>
          <InlineChart
            rows={(table.rows as { rows?: unknown })?.rows ?? table.rows}
          />
          <DataTable
            rows={(table.rows as { rows?: unknown })?.rows ?? table.rows}
            heat={heat}
            onPlayerSelect={(player) =>
              onAsk ? onAsk(`Tell me about ${player} this season`) : undefined
            }
            onPinPlayer={onPinPlayer}
          />
        </>
      )}
    </div>
  );
}
