import type { ReactNode } from "react";
import { describeScenarioMove } from "@/lib/capsheet-fixture";
import type { SharedObject, SharedTradeLeg, SharedTradeObject, TradeLegsEvaluation } from "@/lib/shared";
import type { ScenarioResponse } from "@/lib/capsheet-fixture";

function money(value: number | null | undefined): string {
  if (value == null) return "–";
  const sign = value < 0 ? "−" : "";
  return `${sign}$${(Math.abs(value) / 1e6).toFixed(1)}M`;
}

function sharedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

export function SharedFrame({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <main className="mx-auto min-h-screen w-full max-w-[860px] px-5 py-10 sm:px-8">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <a href="/" className="text-[15px] font-semibold tracking-tight text-ink">dime</a>
        <span className="text-[11px] uppercase tracking-[0.08em] text-ink-3">{label ?? "shared cap scenario"}</span>
        <span className="rounded-full border border-line px-2 py-px font-mono text-[9.5px] uppercase tracking-wide text-ink-3">
          read-only
        </span>
      </header>
      {children}
      <footer className="mt-10 border-t border-line pt-4 text-[12px] leading-[1.6] text-ink-3">
        <p>
          dime is an AI analyst workbench for NBA data.{" "}
          <a href="/" className="text-ink-2 underline underline-offset-2 hover:text-ink">
            Open the workbench
          </a>
        </p>
      </footer>
    </main>
  );
}

export function SharedScenarioNotice({ tone }: { tone: "archived" | "not_found" | "invalid" | "unsupported" | "unavailable" }) {
  const copy: Record<typeof tone, { title: string; body: string }> = {
    archived: {
      title: "This scenario was taken down",
      body: "The owner archived this shared scenario. The link still resolves so you know what happened to it, but the contents are no longer shared.",
    },
    not_found: {
      title: "This shared scenario no longer exists",
      body: "The link may have been rotated by its owner — rotating a share link retires the old one — or the scenario was never shared at this address.",
    },
    invalid: {
      title: "This link is invalid",
      body: "The share token in this link is malformed. Check that the full link was copied.",
    },
    unsupported: {
      title: "This shared object can't be rendered yet",
      body: "The link resolves, but this kind of shared object isn't supported by this version of the workbench.",
    },
    unavailable: {
      title: "This scenario can't be loaded right now",
      body: "The workbench backend isn't reachable. This is usually temporary — try again in a moment.",
    },
  };
  const { title, body } = copy[tone];
  return (
    <SharedFrame>
      <section className="mt-8 rounded-[10px] bg-surface p-6 shadow-hairline">
        <h1 className="text-[17px] font-semibold text-ink">{title}</h1>
        <p className="mt-2 max-w-[520px] text-[13px] leading-[1.6] text-ink-2">{body}</p>
      </section>
    </SharedFrame>
  );
}

export function SharedScenarioView({
  object,
  evaluation,
}: {
  object: SharedObject;
  evaluation: ScenarioResponse | null;
}) {
  const moves = object.payload.moves;
  const steps = evaluation?.steps ?? [];
  const stepForMove = (index: number) => steps.find((step) => step.step === index + 1 && step.kind !== "payroll" && step.kind !== "post_move");
  const errors = (evaluation?.errors ?? []).filter(Boolean);
  const evaluationFailed = evaluation !== null && (evaluation.ok === false || errors.length > 0);

  return (
    <SharedFrame>
      <div className="mt-6">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1 text-[12.5px] text-ink-3">
          {object.payload.team} · {object.payload.season} · shared {sharedDate(object.updated_at)}
        </p>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="space-y-4">
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">Moves</h2>
            <ol className="mt-2 space-y-2">
              {moves.map((move, i) => {
                const step = stepForMove(i);
                return (
                  <li key={i} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                    <span className="min-w-0 text-ink-2">
                      <span className="mr-1.5 font-mono text-[10.5px] text-ink-3">{i + 1}.</span>
                      {describeScenarioMove(move)}
                      {step?.estimate_basis && (
                        <span className="mt-0.5 block pl-5 text-[11px] leading-[1.45] text-ink-3">{step.estimate_basis}</span>
                      )}
                    </span>
                    {step && (
                      <span className={`shrink-0 font-mono text-[11px] tabular-nums ${step.delta !== 0 ? "text-ink-2" : "text-ink-3"}`}>
                        {step.delta > 0 ? "+" : ""}{money(step.delta)}
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
            {evaluation === null && (
              <p className="mt-3 border-t border-line pt-2 text-[12px] leading-[1.55] text-ink-3">
                This scenario could not be evaluated live — the stored moves are shown as shared, without computed cap impact.
              </p>
            )}
            {evaluation !== null && !evaluationFailed && (
              <p className="mt-3 border-t border-line pt-2 font-mono text-[12px] tabular-nums text-ink">
                payroll after: {money(evaluation.pay_after)}
                <span className="ml-2 font-sans text-[11px] text-ink-3">in {evaluation.season}</span>
              </p>
            )}
            {evaluationFailed && (
              <div className="mt-3 border-t border-line pt-2">
                <p className="text-[12px] font-medium text-ink-2">The stored moves no longer evaluate cleanly:</p>
                {errors.map((err, i) => (
                  <p key={i} className="mt-1 text-[11.5px] leading-[1.5] text-red">
                    {typeof err === "string" ? err : `move ${err.move ?? i}: ${err.error ?? "invalid move"}`}
                  </p>
                ))}
              </div>
            )}
          </section>

          {evaluation?.restrictions?.length ? (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">CBA restrictions in play</h2>
              <div className="mt-2 space-y-2.5">
                {evaluation.restrictions.map((r, i) => (
                  <div key={i}>
                    <div className="flex items-baseline gap-1.5">
                      <span className={`rounded-full border px-1.5 py-px font-mono text-[9px] uppercase tracking-wide ${r.status === "active" ? "border-red text-red" : "border-line text-ink-3"}`}>
                        {r.status}
                      </span>
                      <span className="text-[11px] text-ink-3">{r.threshold}</span>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-[1.55] text-ink-2">{r.rule}</p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {evaluation?.roster_issues?.length ? (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Roster issues</h2>
              <div className="mt-2 space-y-1">
                {evaluation.roster_issues.map((issue, i) => (
                  <p key={i} className="text-[12px] leading-[1.55] text-ink-2">{issue}</p>
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          {evaluation !== null && !evaluationFailed && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Apron state after moves</h2>
              <div className="mt-2 space-y-1.5 text-[12px]">
                {([
                  ["tax", evaluation.state.over_tax],
                  ["first apron", evaluation.state.over_apron1],
                  ["second apron", evaluation.state.over_apron2],
                ] as const).map(([label, over]) => (
                  <div key={label} className="flex items-baseline justify-between">
                    <span className="text-ink-2">{label}</span>
                    <span className={`font-mono text-[10.5px] uppercase tracking-wide ${over ? "text-red" : "text-ink-3"}`}>
                      {over ? "over" : "under"}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">About this link</h2>
            <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
              Evaluated live against the current warehouse snapshot when you opened it — numbers recompute at open time and can move as the data moves. This is a read-only view; the scenario can't be edited here.
            </p>
          </section>
        </aside>
      </div>
    </SharedFrame>
  );
}
function legPlayers(players: string | string[] | undefined): string {
  if (players == null) return "";
  return Array.isArray(players) ? players.join(", ") : players;
}

function legPick(pick: Record<string, unknown>): string {
  const year = typeof pick.year === "number" || typeof pick.year === "string" ? String(pick.year) : "";
  const round = typeof pick.round === "number" || typeof pick.round === "string" ? `R${pick.round}` : "";
  return [year, round].filter(Boolean).join(" ") || "pick";
}

function describeLeg(leg: SharedTradeLeg): string {
  const players = legPlayers(leg.players);
  const picks = (leg.picks ?? []).map(legPick);
  const parts = [players, ...picks].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "no assets";
}

export function SharedTradeView({
  object,
  evaluation,
}: {
  object: SharedTradeObject;
  evaluation: TradeLegsEvaluation | null;
}) {
  const legs = object.payload.legs;
  const rows = evaluation?.rows ?? [];
  const legal = rows.length > 0 && rows.every((row) => row.matching_ok !== false);
  const issues = rows.flatMap((row) => (row.issues ?? []).map((issue) => ({ team: row.team, issue })));
  const evaluationFailed = evaluation !== null && (evaluation.ok === false || typeof evaluation.error === "string");

  return (
    <SharedFrame label="shared trade construction">
      <div className="mt-6">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1 text-[12.5px] text-ink-3">
          {legs.map((leg) => leg.from).join(" · ")} · {object.payload.season} · shared {sharedDate(object.updated_at)}
        </p>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_280px]">
        <div className="space-y-4">
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">Trade legs</h2>
            <ol className="mt-2 space-y-2">
              {legs.map((leg, i) => (
                <li key={i} className="text-[12.5px]">
                  <span className="mr-1.5 font-mono text-[10.5px] text-ink-3">{i + 1}.</span>
                  <span className="text-ink-2">
                    <span className="font-medium text-ink">{leg.from}</span>
                    <span className="text-ink-3"> sends </span>
                    {describeLeg(leg)}
                    <span className="text-ink-3"> to </span>
                    <span className="font-medium text-ink">{leg.to}</span>
                  </span>
                </li>
              ))}
            </ol>
            {evaluation === null && (
              <p className="mt-3 border-t border-line pt-2 text-[12px] leading-[1.55] text-ink-3">
                This construction could not be evaluated live — the stored legs are shown as shared, without a legality verdict.
              </p>
            )}
            {evaluation !== null && !evaluationFailed && rows.length > 0 && (
              <p className="mt-3 border-t border-line pt-2 text-[12.5px] font-medium text-ink">
                {legal ? "Legal under current salary-matching rules" : "Not legal as constructed"}
                <span className="ml-2 font-sans text-[11px] font-normal text-ink-3">evaluated live in {object.payload.season}</span>
              </p>
            )}
            {evaluationFailed && (
              <p className="mt-3 border-t border-line pt-2 text-[12px] leading-[1.5] text-red">
                {evaluation?.error ?? "The stored legs no longer evaluate cleanly against the current roster state."}
              </p>
            )}
          </section>

          {rows.length > 0 && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Salary matching by team</h2>
              <div className="mt-2 space-y-3">
                {rows.map((row) => (
                  <div key={row.team} className="border-t border-line pt-2 first:border-t-0 first:pt-0">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[12.5px] font-medium text-ink">{row.team}</span>
                      <span className={`font-mono text-[10.5px] uppercase tracking-wide ${row.matching_ok === false ? "text-red" : "text-ink-3"}`}>
                        {row.matching_ok === false ? "fails" : "matches"}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[11.5px] tabular-nums text-ink-2">
                      <span>out {money(row.outgoing)}</span>
                      <span>in {money(row.incoming)}</span>
                      {row.allowed_incoming != null && <span className="text-ink-3">max in {money(row.allowed_incoming)}</span>}
                    </div>
                    {row.match_rule && (
                      <p className="mt-0.5 text-[11px] leading-[1.45] text-ink-3">{row.match_rule}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {issues.length > 0 && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Legality issues</h2>
              <div className="mt-2 space-y-1">
                {issues.map((entry, i) => (
                  <p key={i} className="text-[12px] leading-[1.55] text-ink-2">
                    <span className="font-medium">{entry.team}:</span> {entry.issue}
                  </p>
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          {rows.length > 0 && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Apron state</h2>
              <div className="mt-2 space-y-2">
                {rows.map((row) => (
                  <div key={row.team}>
                    <span className="text-[11.5px] font-medium text-ink-2">{row.team}</span>
                    <div className="mt-0.5 space-y-0.5 text-[11px]">
                      {([
                        ["first apron", row.over_apron1],
                        ["second apron", row.over_apron2],
                      ] as const).map(([label, over]) => (
                        <div key={label} className="flex items-baseline justify-between">
                          <span className="text-ink-3">{label}</span>
                          <span className={`font-mono text-[10px] uppercase tracking-wide ${over ? "text-red" : "text-ink-3"}`}>
                            {over ? "over" : "under"}
                          </span>
                        </div>
                      ))}
                      {row.hard_cap && (
                        <div className="flex items-baseline justify-between">
                          <span className="text-ink-3">hard cap</span>
                          <span className="font-mono text-[10px] uppercase tracking-wide text-red">{row.hard_cap}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
          {evaluation?.meta?.disclaimer && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <p className="text-[11.5px] leading-[1.6] text-ink-3">{evaluation.meta.disclaimer}</p>
            </section>
          )}
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">About this link</h2>
            <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
              Evaluated live against the current warehouse snapshot when you opened it — the verdict recomputes at open time and can move as rosters move. This is a read-only view; the construction can't be edited here.
            </p>
          </section>
        </aside>
      </div>
    </SharedFrame>
  );
}
