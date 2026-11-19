"use client";

export type CompareRow = {
  label: string;
  a: number;
  b: number;
  fmt: (v: number) => string;
};

export default function ArtifactCompare({
  rows,
  aName,
  bName,
}: {
  rows: CompareRow[];
  aName: string;
  bName: string;
}) {
  return (
    <div className="px-4 py-1">
      <div className="divide-y divide-line">
        {rows.map((r) => {
          const max = Math.max(r.a, r.b) || 1;
          const aLead = r.a >= r.b;
          return (
            <div key={r.label} className="py-2.5">
              <div className="flex items-baseline justify-between text-[12.5px]">
                <span className="text-ink-2">{r.label}</span>
                <span className="font-mono tabular-nums">
                  <span className={aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.a)}</span>
                  <span className="text-ink-3"> · </span>
                  <span className={!aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.b)}</span>
                </span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1.5" aria-hidden>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${aLead ? "bg-ink" : "bg-line-strong"}`}
                    style={{ width: `${(r.a / max) * 100}%` }}
                  />
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${!aLead ? "bg-ink" : "bg-line-strong"}`}
                    style={{ width: `${(r.b / max) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-1.5 py-2.5 text-[11px] text-ink-3">
        <span className="inline-block size-2 rounded-[2px] bg-ink" /> {aName}
        <span className="ml-2 inline-block size-2 rounded-[2px] bg-line-strong" /> {bName}
        <span className="ml-1">solid marks the leader</span>
      </div>
    </div>
  );
}
