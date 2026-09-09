"use client";

import { useEffect, useState } from "react";
import AutoChart from "./AutoChart";
import CompareView from "./CompareView";
import CourtHeatmap from "./CourtHeatmap";
import DataTable from "./DataTable";
import WowyCard from "./WowyCard";

export interface ArtifactItem {
  id: string;
  tool: string;
  title?: string;
  rows?: unknown;
  meta?: {
    source?: string;
    fetched_at?: string;
    stat_category?: string;
    sql?: string;
    a?: string;
    b?: string;
    season?: string;
    team?: string;
  };
  verdict?: string;
}

interface ArtifactCanvasProps {
  artifact: ArtifactItem | null;
  onClose: () => void;
  onAsk?: (query: string) => void;
}

export default function ArtifactCanvas({ artifact, onClose, onAsk }: ArtifactCanvasProps) {
  const [viewMode, setViewMode] = useState<"court" | "table" | "chart">("table");
  const [heat, setHeat] = useState(false);

  const isShotTool =
    artifact?.tool === "get_shot_zones" || artifact?.tool === "get_shot_compare";

  useEffect(() => {
    if (isShotTool) {
      setViewMode("court");
    } else {
      setViewMode("table");
    }
  }, [artifact?.tool, isShotTool]);

  if (!artifact) return null;

  const rawTitle =
    artifact.title ||
    artifact.tool.replace("get_", "").replace(/_/g, " ").toUpperCase() +
      (artifact.meta?.stat_category ? ` · ${artifact.meta.stat_category}` : "");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--color-pure-white)",
        borderLeft: "1px solid var(--color-stone-border)",
        boxSizing: "border-box",
      }}
    >
      {/* Artifact Canvas Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          borderBottom: "1px solid var(--color-stone-border)",
          background: "var(--color-pure-white)",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "var(--color-ink-black)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {rawTitle}
          </div>
          <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginTop: 1 }}>
              {artifact.meta?.source ? `Source: ${artifact.meta.source}` : "Source: NBA data"}
            {artifact.meta?.fetched_at ? ` · ${String(artifact.meta.fetched_at).slice(0, 10)}` : ""}
          </div>
        </div>

        {/* View Switchers & Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <div
            style={{
              display: "inline-flex",
              background: "var(--color-stone-canvas)",
              padding: 2,
              borderRadius: 9999,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            {isShotTool && (
              <button
                type="button"
                className={viewMode === "court" ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "3px 12px", border: "none" }}
                onClick={() => setViewMode("court")}
              >
                Court
              </button>
            )}
            <button
              type="button"
              className={viewMode === "table" ? "tab-active" : "pill-ghost"}
              style={{ fontSize: 11, padding: "3px 12px", border: "none" }}
              onClick={() => setViewMode("table")}
            >
              Table
            </button>
            {!isShotTool && artifact.tool !== "get_wowy" && artifact.tool !== "get_compare" && (
              <button
                type="button"
                className={viewMode === "chart" ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "3px 12px", border: "none" }}
                onClick={() => setViewMode("chart")}
              >
                Chart
              </button>
            )}
          </div>

          {viewMode === "table" && (
            <button
              type="button"
              className={heat ? "tab-active" : "pill-ghost"}
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={() => setHeat(!heat)}
              title="Toggle heat map gradient"
            >
              Heat
            </button>
          )}

          {/* Close Canvas Button */}
          <button
            type="button"
            onClick={onClose}
            className="pill-ghost"
            style={{
              padding: "4px 8px",
              fontSize: 12,
              color: "var(--color-warm-gray)",
              display: "flex",
              alignItems: "center",
              cursor: "pointer",
            }}
            title="Close canvas (⌘ Esc)"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Artifact Canvas Body */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "20px" }}>
        {artifact.meta?.sql && (
          <details
            style={{
              fontSize: 11,
              color: "var(--color-warm-gray)",
              marginBottom: 16,
              background: "var(--color-stone-canvas)",
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            <summary style={{ cursor: "pointer", fontWeight: 500 }}>View SQL query</summary>
            <pre style={{ whiteSpace: "pre-wrap", margin: "8px 0 0", fontSize: 11, fontFamily: "monospace" }}>
              {artifact.meta.sql}
            </pre>
          </details>
        )}

        {/* View Mode Rendering */}
        {artifact.tool === "get_compare" || artifact.tool === "get_preview" ? (
          <CompareView rows={artifact.rows} />
        ) : artifact.tool === "get_wowy" ? (
          <WowyCard rows={artifact.rows} meta={artifact.meta} verdict={artifact.verdict} />
        ) : isShotTool && viewMode === "court" ? (
          <CourtHeatmap rows={artifact.rows} meta={artifact.meta} verdict={artifact.verdict} />
        ) : artifact.tool === "run_python" ? (
          <div
            style={{
              background: "var(--color-stone-canvas)",
              border: "1px solid var(--color-stone-border)",
              padding: 16,
              borderRadius: 10,
              fontFamily: "monospace",
              fontSize: 12,
              overflowX: "auto",
            }}
          >
            <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginBottom: 8, fontWeight: 500 }}>
              Python Output
            </div>
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {String(
                (artifact.rows as Record<string, unknown>)?.printed ||
                  (artifact.rows as Record<string, unknown>)?.out ||
                  "Execution completed (no stdout).",
              )}
            </pre>
          </div>
        ) : viewMode === "chart" ? (
          <AutoChart table={artifact as { rows?: unknown }} />
        ) : (
          <DataTable
            rows={(artifact.rows as { rows?: unknown })?.rows ?? artifact.rows}
            heat={heat}
            capRows={100}
            onPlayerSelect={(player) => (onAsk ? onAsk(`Analyze ${player} this season`) : undefined)}
          />
        )}
      </div>
    </div>
  );
}
