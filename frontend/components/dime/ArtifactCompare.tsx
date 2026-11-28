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
              {r.a < 0 || r.b < 0 ? (
                <div className="relative mt-1.5 h-1.5 overflow-hidden rounded-full bg-field" aria-hidden>
                  {(() => {
                    const lo = Math.min(0, r.a, r.b);
                    const hi = Math.max(0, r.a, r.b);
                    const span = hi - lo || 1;
                    const zero = (-lo / span) * 100;
                    return (
                      <>
                        <div className="absolute inset-y-0 w-px bg-ink-3" style={{ left: `${zero}%` }} />
                        {[
                          { v: r.a, tone: "bg-ink", player: "a" as const },
                          { v: r.b, tone: "bg-ink-3", player: "b" as const },
                        ].map((bar) => {
                          const magnitude = (Math.abs(bar.v) / span) * 100;
                          const left = bar.v >= 0 ? zero : zero - magnitude;
                          return (
                            <div
                              key={bar.player}
                              className={`absolute inset-y-0 rounded-full ${bar.tone}`}
                              style={{ left: `${left}%`, width: `${magnitude}%` }}
                            />
                          );
                        })}
                      </>
                    );
                  })()}
                </div>
              ) : (
                <div className="relative mt-1.5 h-1.5 overflow-hidden rounded-full bg-field" aria-hidden>
                  {[
                    { v: r.a, tone: "bg-ink", player: "a" as const },
                    { v: r.b, tone: "bg-ink-3", player: "b" as const },
                  ]
                    .sort((x, y) => y.v - x.v || (x.player === "a" ? -1 : 1))
                    .map((bar) => (
                      <div
                        key={bar.player}
                        className={`absolute inset-y-0 left-0 rounded-full ${bar.tone}`}
                        style={{ width: `${(Math.max(bar.v, 0) / max) * 100}%` }}
                      />
                    ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 py-2.5 text-[11px] text-ink-3">
        <span className="inline-block size-2 rounded-[2px] bg-ink" /> {aName}
        <span className="ml-2 inline-block size-2 rounded-[2px] bg-ink-3" /> {bName}
        {rows.some((r) => r.a < 0 || r.b < 0) ? <span className="ml-1">signed rows diverge from the zero line; elsewhere bars share one baseline; the protruding tip is the gap</span> : <span className="ml-1">bars share one baseline; the protruding tip is the gap</span>}
      </div>
    </div>
  );
}
