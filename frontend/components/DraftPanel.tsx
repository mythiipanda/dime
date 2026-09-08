"use client";

import { useState } from "react";
import DataTable from "./DataTable";
import { BACKEND } from "../lib/chat";

export default function DraftPanel() {
  const [year, setYear] = useState("2025");
  const [rows, setRows] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError("");
    setBusy(true);
    try {
      const res = await fetch(
        `${BACKEND}/api/v1/datasets/combine?season=${encodeURIComponent(year)}`,
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

  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Draft combine</div>
      <div style={{ fontSize: 12, color: "#78716c", marginTop: 4 }}>
        Measurements plus spot shooting. Names sort by wingspan scouts love.
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input
          className="field"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          placeholder="draft year"
          style={{ width: 110 }}
        />
        <button className="pill-cta" style={{ fontSize: 12 }} disabled={busy} onClick={load}>
          {busy ? "Loading" : "Show"}
        </button>
      </div>
      {error && <div style={{ color: "#78716c", marginTop: 8 }}>{error}</div>}
      {rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={rows} />
        </div>
      )}
    </div>
  );
}
