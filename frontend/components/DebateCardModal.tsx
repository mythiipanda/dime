"use client";

import { useEffect, useState } from "react";
import {
  DebateCardRows,
  PlayerHit,
  debateFileUrl,
  getDebateCard,
  resolvePlayers,
} from "../lib/api";

export type ModalState = "idle" | "loading" | "ready" | "error";

export interface DebateCardModalProps {
  initialA?: string;
  initialB?: string;
  season?: string;
  topic?: string;
  onClose: () => void;
}

function useSuggestions(value: string): PlayerHit[] {
  const [hits, setHits] = useState<PlayerHit[]>([]);
  useEffect(() => {
    if (!value.trim()) {
      setHits([]);
      return;
    }
    const t = setTimeout(async () => {
      setHits(await resolvePlayers(value.trim()));
    }, 200);
    return () => clearTimeout(t);
  }, [value]);
  return hits;
}

export default function DebateCardModal({
  initialA = "",
  initialB = "",
  season = "2025-26",
  topic = "",
  onClose,
}: DebateCardModalProps) {
  const [a, setA] = useState(initialA);
  const [b, setB] = useState(initialB);
  const debateTopic = topic.trim();
  const [status, setStatus] = useState<ModalState>("idle");
  const [error, setError] = useState("");
  const [rows, setRows] = useState<DebateCardRows | null>(null);
  const [copied, setCopied] = useState(false);
  const [openList, setOpenList] = useState<"a" | "b" | null>(null);
  const suggA = useSuggestions(a);
  const suggB = useSuggestions(b);

  async function generate() {
    if (!a.trim() || !b.trim() || status === "loading") return;
    setStatus("loading");
    setError("");
    setCopied(false);
    try {
      const r = await getDebateCard(a.trim(), b.trim(), season, debateTopic || undefined);
      setRows(r);
      setStatus("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "debate card failed");
      setStatus("error");
    }
  }

  const fileUrl = rows ? debateFileUrl(rows.url || rows.path) : "";

  async function copyLink() {
    if (!fileUrl) return;
    try {
      await navigator.clipboard.writeText(fileUrl);
      setCopied(true);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = fileUrl;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
    }
  }

  function renderSuggest(
    hits: PlayerHit[],
    which: "a" | "b",
    set: (v: string) => void,
  ) {
    if (openList !== which || hits.length === 0) return null;
    return (
      <ul
        style={{
          position: "absolute",
          top: "100%",
          left: 0,
          right: 0,
          zIndex: 5,
          background: "#ffffff",
          border: "1px solid #e8e6e5",
          borderRadius: 8,
          margin: "4px 0 0",
          padding: 4,
          listStyle: "none",
        }}
      >
        {hits.map((h) => (
          <li key={h.id}>
            <button
              type="button"
              style={{
                width: "100%",
                textAlign: "left",
                background: "transparent",
                border: "none",
                padding: "6px 10px",
                fontSize: 13,
                lineHeight: 1.5,
                minHeight: 40,
                color: "#0c0a09",
                cursor: "pointer",
              }}
              onClick={() => {
                set(h.name);
                setOpenList(null);
              }}
            >
              {h.name}
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Debate card"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(12,10,9,0.4)",
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        overflowY: "auto",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e8e6e5",
          borderRadius: 10,
          padding: 20,
          maxWidth: 640,
          width: "100%",
          maxHeight: "calc(100dvh - 32px)",
          overflowY: "auto",
          boxSizing: "border-box",
          margin: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="display" style={{ fontSize: 20, color: "#0c0a09", marginBottom: 4 }}>
          Debate card
        </div>
        {debateTopic ? (
          <div style={{ marginBottom: 16, maxWidth: "100%" }}>
            <span
              style={{
                display: "inline-block",
                fontSize: 11,
                fontWeight: 500,
                borderRadius: 9999,
                padding: "2px 10px",
                border: "1px solid #e8e6e5",
                background: "var(--color-sky-wash)",
                color: "var(--color-cyan-edge)",
                whiteSpace: "nowrap",
                maxWidth: "100%",
                overflow: "hidden",
                textOverflow: "ellipsis",
                verticalAlign: "top",
              }}
            >
              {debateTopic}
            </span>
          </div>
        ) : (
          <div style={{ fontSize: 14, color: "#78716c", marginBottom: 16 }}>
            Pick two players and settle it with data.
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <div style={{ position: "relative", flex: "1 1 160px", minWidth: 0 }}>
            <input
              className="field"
              style={{ width: "100%" }}
              value={a}
              placeholder="Player A"
              aria-label="Player A"
              onChange={(e) => {
                setA(e.target.value);
                setOpenList("a");
              }}
            />
            {renderSuggest(suggA, "a", setA)}
          </div>
          <div style={{ position: "relative", flex: "1 1 160px", minWidth: 0 }}>
            <input
              className="field"
              style={{ width: "100%" }}
              value={b}
              placeholder="Player B"
              aria-label="Player B"
              onChange={(e) => {
                setB(e.target.value);
                setOpenList("b");
              }}
            />
            {renderSuggest(suggB, "b", setB)}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
          <button
            type="button"
            className="pill-cta"
            style={{ minHeight: 40 }}
            disabled={!a.trim() || !b.trim() || status === "loading"}
            onClick={generate}
          >
            {status === "loading" ? "Building…" : "Generate"}
          </button>
          <button type="button" className="pill-ghost" style={{ minHeight: 40 }} onClick={onClose}>
            Close
          </button>
        </div>
        {status === "error" && (
          <div style={{ fontSize: 14, color: "#78716c", marginBottom: 12 }}>
            {error || "Something went wrong."}
          </div>
        )}
        {status === "ready" && rows && (
          <div>
            <iframe
              title="Debate card"
              src={fileUrl}
              style={{
                width: "100%",
                height: 360,
                maxHeight: "50dvh",
                display: "block",
                background: "#fafaf9",
                border: "1px solid #e8e6e5",
                borderRadius: 10,
              }}
            />
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button type="button" className="pill-ghost" style={{ minHeight: 40 }} onClick={copyLink}>
                {copied ? "Copied" : "Copy Link"}
              </button>
              <a
                className="pill-ghost"
                style={{ textDecoration: "none", fontSize: 13, minHeight: 40, display: "inline-flex", alignItems: "center" }}
                href={fileUrl}
                download={rows.path}
              >
                Download
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
