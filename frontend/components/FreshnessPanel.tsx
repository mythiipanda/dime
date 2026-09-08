"use client";

import { useEffect, useState } from "react";
import { BACKEND } from "../lib/chat";

interface FreshRow {
  table: string;
  rows: number;
  last_fetch: string | null;
}

export default function FreshnessPanel() {
  const [rows, setRows] = useState<FreshRow[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${BACKEND}/api/v1/datasets/freshness`)
      .then((r) => r.json())
      .then((d) => setRows(d.rows || []))
      .catch(() => setErr("freshness unavailable"));
  }, []);

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        Warehouse freshness
      </div>
      {err && <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>{err}</div>}
      <table style={{ fontSize: 12, width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--color-warm-gray)" }}>
            <th>Table</th>
            <th>Rows</th>
            <th>Last fetch</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.table} style={{ borderTop: "1px solid var(--color-stone-border)" }}>
              <td>{r.table.replace("silver_", "")}</td>
              <td>{r.rows.toLocaleString()}</td>
              <td>{r.last_fetch ? String(r.last_fetch).slice(0, 16).replace("T", " ") : "never"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
