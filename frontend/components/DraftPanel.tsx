"use client";

import { useEffect, useState } from "react";
import CopyLink from "./CopyLink";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import DataTable from "./DataTable";
import Skeleton from "./Skeleton";
import { BACKEND } from "../lib/chat";
import { apiPath, getQueryParam, setQueryParam } from "../lib/api";

export default function DraftPanel() {
  const [year, setYear] = useState("2025");
  const [rows, setRows] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async (draftYear?: string) => {
    const y = (draftYear ?? year).trim() || "2025";
    setError("");
    setBusy(true);
    setQueryParam("draft_year", y, true);
    try {
      const res = await fetch(
        `${BACKEND}${apiPath(`/datasets/combine?season=${encodeURIComponent(y)}`)}`,
      );
      const data = await res.json();
      if (!data.ok) {
        setError(String(data.error || "failed"));
        return;
      }
      setRows(data.data || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  
  



  useEffect(() => {
    const fromUrl = getQueryParam("draft_year");
    if (fromUrl) setYear(fromUrl);
    load(fromUrl || "2025");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <ExplorePanel id="explore-draft">
      <PanelHeader kicker="Draft" title="Draft combine" action={<CopyLink panel="draft" />} />
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="rounded-lg border border-line bg-field px-3 py-2 text-ink"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          placeholder="draft year"
          style={{ width: 110 }}
          aria-label="Draft year"
        />
        <button className="inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-ink text-page hover:opacity-90 disabled:opacity-50" style={{ fontSize: 12 }} disabled={busy} onClick={() => load()}>
          {busy ? "Loading" : "Show"}
        </button>
      </div>
      {error && <div style={{ color: "var(--ink-2)", marginTop: 8 }}>{error}</div>}
      {rows === null && !error && <Skeleton lines={5} label="Loading combine rows" />}
      {rows !== null && Array.isArray(rows) && rows.length === 0 && !busy && (
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 8 }}>
          No combine rows for {year}. Try another draft year. Measurements land after each combine.
        </div>
      )}
      {rows !== null && !(Array.isArray(rows) && rows.length === 0) && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={rows} storeKey="draft" />
        </div>
      )}
    </ExplorePanel>
  );
}
