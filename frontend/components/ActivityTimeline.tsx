"use client";

import { useEffect, useRef, useState } from "react";
import type { ActivityRecord } from "../lib/chat";
import { rerunSql, type SqlRerunRows } from "../lib/api";

const KIND_STATUS: Record<string, string> = {
  stage_summary: "Understanding the question…",
  plan_update: "Planning the research…",
  node_update: "Working through it…",
  thought_stream: "Working through it…",
  thought_token: "Working through it…",
  tool_call: "Looking up stats…",
  tool_result: "Crunching the numbers…",
  evidence_update: "Checking sources…",
  verification_update: "Verifying the numbers…",
};

const FAMILY_STATUS: Array<[string, string]> = [
  ["player", "Looking up player stats…"],
  ["team", "Looking up team stats…"],
  ["league", "Checking league stats…"],
  ["lineup", "Checking lineups…"],
  ["shot", "Digging into shooting…"],
  ["histor", "Digging into history…"],
  ["today", "Checking today's games…"],
  ["schedule", "Checking today's games…"],
];

export function humanStatus(kind: string, raw?: string): string {
  const name = (raw ?? "").toLowerCase();
  if (kind === "tool_call" || kind === "tool_result" || kind === "evidence_update") {
    for (const [family, line] of FAMILY_STATUS) {
      if (name.includes(family)) return line;
    }
  }
  return KIND_STATUS[kind] ?? "Working through it…";
}

type View = { meta: string; fields: Array<[string, string]> };
const amount = (v: unknown, n: string) => `${Number(v) || 0} ${n}${Number(v) === 1 ? "" : "s"}`;
const words = (v: unknown) => String(v ?? "").replace(/_/g, " ");
const payloadOf = (i: ActivityRecord) =>
  i.data.data && typeof i.data.data === "object" && !Array.isArray(i.data.data)
    ? (i.data.data as Record<string, unknown>)
    : {};
const rawNameOf = (i: ActivityRecord) => {
  const d = payloadOf(i);
  return String(d.name ?? d.capability ?? "");
};
const statusFor = (i: ActivityRecord) => humanStatus(i.kind, rawNameOf(i));

function describe(i: ActivityRecord): View {
  const d = payloadOf(i);
  if (i.kind === "stage_summary")
    return {
      meta: amount(d.requirement_count, "requirement"),
      fields: [
        ["Season", words(d.season || "Current")],
        ["Entities", String(d.entity_count ?? 0)],
      ],
    };
  if (i.kind === "plan_update")
    return { meta: amount(d.node_count, "step"), fields: [] };
  if (i.kind === "tool_call")
    return { meta: "Running", fields: [["Inputs", amount(d.argument_count, "field")]] };
  if (i.kind === "tool_result") {
    const bad = i.transition === "failed" || i.status === "fail" || i.status === "failed";
    return {
      meta: bad ? "Failed" : d.rows == null ? "Complete" : amount(d.rows, "row"),
      fields: [
        ["Status", bad ? "Failed" : "Complete"],
        ...(d.rows == null ? [] : [["Rows", String(d.rows)] as [string, string]]),
      ],
    };
  }
  if (i.kind === "evidence_update") {
    const ok = i.transition === "admitted";
    return {
      meta: ok ? amount(d.rows, "row") : "Set aside",
      fields: [
        ...(d.rows == null ? [] : [["Rows", String(d.rows)] as [string, string]]),
        ["Source date", words(d.as_of || "Not supplied")],
      ],
    };
  }
  if (i.kind === "verification_update")
    return {
      meta:
        Number(d.missing_count) || Number(d.contradiction_count)
          ? amount(d.missing_count, "gap")
          : "Passed",
      fields: [
        ["Checked", `${Number(d.supported_count) || 0} of ${Number(d.claim_count) || 0} claims`],
      ],
    };
  return { meta: i.summary || "", fields: [] };
}

function sqlOf(item: ActivityRecord): string {
  const d = item.data as Record<string, unknown>;
  return typeof d.sql === "string" && d.sql.trim() ? d.sql : "";
}

function fmtMs(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function SqlRerun({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(sql);
  const [rerun, setRerun] = useState<
    null | { loading: true } | { loading: false; data?: SqlRerunRows; error?: string }
  >(null);
  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-cyan-edge)",
        }}
      >
        SQL {open ? "▾" : "▸"}
      </button>
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          marginLeft: 10,
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--color-cyan-edge)",
        }}
      >
        Edit & run
      </button>
      {open && (
        <div style={{ marginTop: 4 }}>
          <textarea
            aria-label="SQL query"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            style={{
              display: "block",
              width: "100%",
              minHeight: 96,
              resize: "vertical",
              fontFamily: "ui-monospace, monospace",
              fontSize: 11,
              lineHeight: 1.5,
              background: "var(--color-pure-white)",
              border: "1px solid var(--color-stone-border)",
              borderRadius: 6,
              padding: 8,
              color: "var(--color-ink-black)",
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
            <button
              type="button"
              className="pill-ghost"
              disabled={rerun?.loading === true || !draft.trim()}
              onClick={() => {
                if (rerun?.loading || !draft.trim()) return;
                setRerun({ loading: true });
                rerunSql(draft).then(
                  (data) => setRerun({ loading: false, data }),
                  (err) =>
                    setRerun({
                      loading: false,
                      error: err instanceof Error ? err.message : "query failed",
                    }),
                );
              }}
              style={{ fontSize: 11, opacity: rerun?.loading || !draft.trim() ? 0.5 : 1 }}
            >
              {rerun?.loading ? "Running…" : "Run query"}
            </button>
            <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
              Read-only · 25 row cap
            </span>
          </div>
        </div>
      )}
      {rerun && !rerun.loading && rerun.error && (
        <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-ember)" }}>
          {rerun.error.slice(0, 160)}
        </div>
      )}
      {rerun && !rerun.loading && rerun.data && (
        <div style={{ marginTop: 4, fontSize: 11 }}>
          <div style={{ marginBottom: 2 }}>
            Re-ran · {rerun.data.rows.length} row{rerun.data.rows.length === 1 ? "" : "s"}
            {rerun.data.capped ? " (capped)" : ""} · {fmtMs(rerun.data.ms)}
          </div>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                borderCollapse: "collapse",
                fontFamily: "ui-monospace, monospace",
                fontSize: 11,
                color: "var(--color-ink-black)",
              }}
            >
              <thead>
                <tr>
                  {rerun.data.columns.map((col) => (
                    <th
                      key={col}
                      style={{
                        textAlign: "left",
                        fontWeight: 600,
                        padding: "3px 8px 3px 0",
                        borderBottom: "1px solid var(--color-stone-border)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rerun.data.rows.map((row, n) => (
                  <tr key={n}>
                    {rerun.data!.columns.map((col) => (
                      <td
                        key={col}
                        style={{
                          padding: "3px 8px 3px 0",
                          borderBottom: "1px solid var(--color-stone-border)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Mark({ item, active }: { item: ActivityRecord; active: boolean }) {
  const bad = item.transition === "failed" || item.status === "fail" || item.status === "failed";
  return (
    <span
      aria-hidden
      style={{
        width: 15,
        display: "inline-grid",
        placeItems: "center",
        color: bad ? "var(--color-ember)" : "var(--color-ash-gray)",
      }}
    >
      {active ? (
        <span className="activity-orbit" />
      ) : bad ? (
        "!"
      ) : item.kind === "verification_update" || item.kind === "evidence_update" ? (
        "✓"
      ) : item.kind === "tool_call" || item.kind === "tool_result" ? (
        "⌕"
      ) : (
        "·"
      )}
    </span>
  );
}

function Step({
  item,
  active,
  index,
}: {
  item: ActivityRecord;
  active: boolean;
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const v = describe(item);
  const sql = sqlOf(item);
  return (
    <div className="activity-step" style={{ animationDelay: `${Math.min(index, 8) * 36}ms` }}>
      <button
        type="button"
        onClick={() => setOpen((x) => !x)}
        aria-expanded={open}
        style={{
          width: "100%",
          display: "grid",
          gridTemplateColumns: "18px minmax(0,1fr) auto",
          gap: 8,
          alignItems: "center",
          padding: "5px 0",
          border: 0,
          background: "none",
          textAlign: "left",
          cursor: "pointer",
        }}
      >
        <Mark item={item} active={active} />
        <span
          style={{
            fontSize: 12,
            color: "var(--color-ink-black)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {statusFor(item)}
        </span>
        <span
          className={active ? "activity-shimmer" : ""}
          style={{
            padding: "3px 7px",
            borderRadius: 6,
            background: "var(--color-stone-canvas)",
            fontSize: 11,
            color: "var(--color-ash-gray)",
            whiteSpace: "nowrap",
          }}
        >
          {v.meta}
        </span>
      </button>
      {open && (
        <div
          className="activity-detail"
          style={{
            margin: "3px 0 7px 26px",
            padding: "9px 10px",
            borderRadius: 8,
            background: "var(--color-stone-canvas)",
          }}
        >
          {v.fields.length > 0 && (
            <dl style={{ display: "flex", gap: 7, flexWrap: "wrap", margin: 0 }}>
              {v.fields.map(([k, x]) => (
                <div
                  key={k}
                  style={{
                    display: "inline-flex",
                    gap: 5,
                    padding: "4px 7px",
                    borderRadius: 6,
                    border: "1px solid var(--color-stone-border)",
                    fontSize: 11,
                  }}
                >
                  <dt style={{ color: "var(--color-ash-gray)" }}>{k}</dt>
                  <dd style={{ margin: 0, color: "var(--color-warm-gray)" }}>{x}</dd>
                </div>
              ))}
            </dl>
          )}
          {sql && <SqlRerun sql={sql} />}
        </div>
      )}
    </div>
  );
}

export default function ActivityTimeline({
  items,
  running,
}: {
  items: ActivityRecord[];
  running: boolean;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open && box.current) box.current.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" });
  }, [items.length, open]);
  const tools = items.filter((i) => i.kind === "tool_call").length;
  const evidence = items.filter((i) => i.kind === "evidence_update" && i.transition === "admitted").length;
  const completed = !running && items.length > 0;
  const doneLabel =
    tools === 0 && evidence === 0
      ? "Work complete"
      : `${tools} step${tools === 1 ? "" : "s"}${evidence > 0 ? ` · ${evidence} source${evidence === 1 ? "" : "s"}` : ""}`;
  return (
    <>
      <style jsx global>{`@keyframes activity-in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}@keyframes activity-orbit{to{transform:rotate(360deg)}}@keyframes activity-shimmer{0%,100%{opacity:.48}50%{opacity:1}}.activity-step{opacity:0;animation:activity-in .28s cubic-bezier(.2,.8,.2,1) forwards}.activity-detail{animation:activity-in .18s ease-out}.activity-orbit{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--color-stone-border);border-top-color:var(--color-cyan-signal);animation:activity-orbit .8s linear infinite}.activity-shimmer{animation:activity-shimmer 1.35s ease-in-out infinite}.activity-timeline{position:relative;padding-top:3px}.activity-progress-rail{position:absolute;top:0;left:0;width:100%;height:2px;overflow:hidden;border-radius:999px;background:var(--color-stone-border)}.activity-progress-rail::after{content:"";position:absolute;inset:0;width:34%;border-radius:inherit;background:var(--color-cyan-signal);opacity:0;transform:translateX(-110%)}.activity-timeline.is-running .activity-progress-rail::after{opacity:1;animation:activity-progress 1.2s cubic-bezier(.4,0,.2,1) infinite}.activity-timeline.is-complete .activity-progress-rail::after{width:100%;opacity:.55;transform:none;transition:width .28s cubic-bezier(.16,1,.3,1),opacity .2s ease}@keyframes activity-progress{to{transform:translateX(395%)}}.activity-status-dot{width:7px;height:7px;flex-shrink:0;border-radius:9999px;background:var(--color-cyan-signal)}.activity-status-dot.is-done{background:var(--color-ash-gray)}@media(prefers-reduced-motion:reduce){.activity-step,.activity-detail,.activity-orbit,.activity-shimmer,.activity-progress-rail::after{animation:none!important;transition:none!important;opacity:1!important}.activity-timeline.is-running .activity-progress-rail::after{width:42%;transform:none}}`}</style>
      <div className={`activity-timeline ${running ? "is-running" : completed ? "is-complete" : ""}`}>
        <span className="activity-progress-rail" aria-hidden="true" />
        <button
          type="button"
          onClick={() => setOpen((x) => !x)}
          aria-expanded={open}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            padding: "5px 9px",
            border: 0,
            borderRadius: 7,
            background: "var(--color-stone-canvas)",
            color: "var(--color-warm-gray)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          <span aria-hidden className={`activity-status-dot${running ? " pulse-dot" : " is-done"}`} />
          <span role={running ? "status" : undefined}>
            {running ? (items.length ? statusFor(items[items.length - 1]) : "Working on it…") : doneLabel}
          </span>
          <span
            aria-hidden
            style={{ transform: open ? "rotate(90deg)" : "none", transition: "transform .16s" }}
          >
            ›
          </span>
        </button>
        {open && (
          <div
            ref={box}
            role="log"
            aria-live="polite"
            aria-label="Tool activity"
            style={{
              marginTop: 8,
              maxHeight: 390,
              overflowY: "auto",
              padding: "0 2px 2px 7px",
              borderLeft: "1px solid var(--color-stone-border)",
            }}
          >
            {items.map((i, n) => (
              <Step key={i.eventId} item={i} index={n} active={running && n === items.length - 1} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
