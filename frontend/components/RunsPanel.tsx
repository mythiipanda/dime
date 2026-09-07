"use client";

import { useEffect, useState } from "react";
import AnswerText from "./AnswerText";
import { RunInfo, exportUrl, getRuns } from "../lib/api";

export default function RunsPanel({
  thread,
  refreshKey,
}: {
  thread: string;
  refreshKey: number;
}) {
  const [runs, setRuns] = useState<RunInfo[]>([]);

  useEffect(() => {
    getRuns(thread).then(setRuns).catch(() => setRuns([]));
  }, [thread, refreshKey]);

  if (!runs.length) return null;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontWeight: 500 }}>Past runs in this session</div>
        <a className="pill-ghost" style={{ fontSize: 12 }} href={exportUrl(thread)}>
          Export
        </a>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
        {runs.map((r, i) => (
          <div
            key={i}
            style={{ borderTop: "1px solid #e8e6e5", paddingTop: 8, fontSize: 13 }}
          >
            <div style={{ fontWeight: 500 }}>{r.question}</div>
            <AnswerText text={r.answer.slice(0, 600)} />
            <div style={{ fontSize: 12, color: "#a8a29e" }}>
              {r.tables.length} tables. {String(r.created_at).slice(0, 10)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
