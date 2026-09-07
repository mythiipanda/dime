"use client";

import { useEffect, useRef, useState } from "react";
import { BACKEND } from "../lib/chat";

interface Hit {
  kind: string;
  id: number | string;
  name: string;
}

export default function CommandPalette({
  onAsk,
  onTab,
}: {
  onAsk: (q: string) => void;
  onTab: (t: "chat" | "data") => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 30);
  }, [open ]);

  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `${BACKEND}/api/v1/resolve?q=${encodeURIComponent(q.trim())}`,
        );
        const data = await res.json();
        const rows = (data.rows || {}) as {
          players?: { id: number; full_name: string }[];
          teams?: { id: number; full_name: string }[];
        };
        const out: Hit[] = [
          ...(rows.players || []).slice(0, 4).map((p) => ({
            kind: "player",
            id: p.id,
            name: p.full_name,
          })),
          ...(rows.teams || []).slice(0, 4).map((t) => ({
            kind: "team",
            id: t.id,
            name: t.full_name,
          })),
        ];
        setHits(out);
      } catch {
        setHits([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q, open]);

  if (!open) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(12, 10, 9, 0.25)",
        zIndex: 50,
        display: "flex",
        justifyContent: "center",
        paddingTop: 120,
      }}
      onClick={() => setOpen(false)}
    >
      <div
        className="card"
        style={{ width: 520, maxWidth: "90vw", height: "fit-content", padding: 16 }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={input}
          className="field"
          style={{ width: "100%", fontSize: 14 }}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Jump to player, team, or action..."
        />
        <div style={{ display: "flex", flexDirection: "column", marginTop: 8 }}>
          <button
            style={{ textAlign: "left", padding: "8px", fontSize: 13 }}
            onClick={() => {
              onTab("chat");
              setOpen(false);
            }}
          >
            Go to analyst chat
          </button>
          <button
            style={{ textAlign: "left", padding: "8px", fontSize: 13 }}
            onClick={() => {
              onTab("data");
              setOpen(false);
            }}
          >
            Go to datasets
          </button>
          {hits.map((h) => (
            <button
              key={`${h.kind}-${h.id}`}
              style={{ textAlign: "left", padding: "8px", fontSize: 13 }}
              onClick={() => {
                onTab("chat");
                onAsk(`Tell me about ${h.name}`);
                setOpen(false);
              }}
            >
              <span style={{ color: "#a8a29e", fontSize: 11 }}>{h.kind} </span>
              {h.name}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 11, color: "#a8a29e", marginTop: 8 }}>
          Ctrl or Cmd plus K toggles. Esc closes.
        </div>
      </div>
    </div>
  );
}
