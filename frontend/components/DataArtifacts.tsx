"use client";

import { useEffect, useState } from "react";
import { AiMessage, NodeName } from "../lib/chat";
import { ArtifactItem } from "./ArtifactCanvas";
import AutoChart from "./AutoChart";
import AwardRaceView, { parseAwardRace } from "./AwardRaceView";
import CompareView from "./CompareView";
import CompsView, { parseCompsRows } from "./CompsView";
import CourtHeatmap from "./CourtHeatmap";
import DataTable from "./DataTable";
import Skeleton from "./Skeleton";
import GameLogView, { parseGameLogs } from "./GameLogView";
import MatchupPreviewView, { parsePreview } from "./MatchupPreviewView";
import PredictionView, { parsePrediction } from "./PredictionView";
import RegressionView, { parseRegression } from "./RegressionView";
import RotationCheckView, { parseRotation } from "./RotationCheckView";
import SplitsView, { parseSplits } from "./SplitsView";
import StreaksView, { parseStreaks } from "./StreaksView";
import TradeValueView, { parseTradeValue } from "./TradeValueView";
import TrendChart, { isRaptorRows } from "./TrendChart";
import { resolveToolName } from "./view-shared";
import WowyCard from "./WowyCard";
import ZoneBars, { isZoneRows } from "./ZoneBars";

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

export default function DataArtifacts({
  ai,
  loading,
  onAsk,
  onOpenArtifact,
  activeArtifactId,
}: {
  ai: AiMessage;
  loading?: boolean;
  onAsk?: (query: string) => void;
  onOpenArtifact?: (artifact: ArtifactItem) => void;
  activeArtifactId?: string;
}) {
  const names = ORDER.filter((n) => ai.nodes[n]);
  const [pageState, setPageState] = useState<number | null>(null);
  const [heat, setHeat] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "chart" | "court">("table");
  const [showInline, setShowInline] = useState(false);

  const tables: {
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
    };
  }[] = [];

  for (const n of names) {
    for (const t of ai.nodes[n]!.tables) tables.push(t);
  }

  const toolOf = (t: { tool?: string; title?: string }) =>
    resolveToolName(t) ?? t.tool;

  const preferred = tables.findIndex((t) => {
    const name = toolOf(t);
    return (
      name === "get_shot_compare" ||
      name === "get_shot_zones" ||
      name === "get_wowy" ||
      name === "get_compare" ||
      name === "get_preview" ||
      name === "get_rapm" ||
      name === "get_finder" ||
      name === "get_comps" ||
      name === "get_award_race" ||
      name === "get_trade_value" ||
      name === "get_matchup_splits" ||
      name === "get_regression_check" ||
      name === "get_matchup_preview" ||
      name === "get_streaks" ||
      name === "get_game_prediction" ||
      name === "search_game_logs" ||
      name === "get_rotation_check"
    );
  });
  const fallback = preferred >= 0 ? preferred : tables.length - 1;
  const table = tables[Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0))];
  const page = Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0));
  const setPage = (n: number) => setPageState(Math.max(0, Math.min(n, tables.length - 1)));

  const toolName = toolOf(table ?? {});
  const isShotTool = toolName === "get_shot_zones" || toolName === "get_shot_compare";
  useEffect(() => {
    if (isShotTool) {
      setViewMode("court");
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
    (toolName || table.tool || "dataset").replace("get_", "").replace(/_/g, " ").toUpperCase() +
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
            {rawTitle} is open in Canvas
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowInline(true)}
          className="pill-ghost interactive-tactile"
          style={{ fontSize: 11, padding: "2px 8px" }}
        >
          Show inline
        </button>
      </div>
    );
  }

  return (
    <div
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
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
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
              title="Open in dedicated side canvas"
            >
              <span>Canvas</span>
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
          {tables.length > 1 && (
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
                {page + 1}/{tables.length}
              </span>
              <button
                className="pill-ghost"
                style={{ fontSize: 11, padding: "3px 8px" }}
                disabled={page >= tables.length - 1}
                onClick={() => setPage(page + 1)}
              >
                Next ›
              </button>
            </div>
          )}
        </div>
      </div>

      {table.meta?.sql && (
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

      {toolName === "get_compare" || toolName === "get_preview" ? (
        <CompareView rows={table.rows} />
      ) : toolName === "get_wowy" ? (
        <WowyCard
          rows={table.rows}
          meta={table.meta}
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
        <MatchupPreviewView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_streaks" && parseStreaks(table.rows) ? (
        <StreaksView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_game_prediction" &&
        parsePrediction(table.rows ?? table) ? (
        <PredictionView rows={table.rows ?? table} meta={table.meta} />
      ) : toolName === "search_game_logs" && parseGameLogs(table.rows) ? (
        <GameLogView rows={table.rows} meta={table.meta} />
      ) : toolName === "get_rotation_check" && parseRotation(table.rows) ? (
        <RotationCheckView rows={table.rows} meta={table.meta} />
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
            {String(
              (table.rows as Record<string, unknown>)?.printed ||
                (table.rows as Record<string, unknown>)?.out ||
                "Execution completed (no stdout).",
            )}
          </pre>
        </div>
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
          />
        </>
      )}
    </div>
  );
}
