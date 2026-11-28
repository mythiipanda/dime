import type { ReactNode } from "react";
import { describeScenarioMove, deadMoneyBasisWords } from "@/lib/capsheet-fixture";
import type { MoveGroupsMap } from "@/lib/move-groups";
import { ReadOnlyMoveList } from "@/components/dime/ScenarioMoveList";
import type { SharedArtifactEvidence, SharedArtifactObject, SharedObject, SharedThreadObject, SharedTradeLeg, SharedTradeObject, TradeLegsEvaluation, TranscriptEntry } from "@/lib/shared";
import { ArtifactBody, ProvenancePanel } from "@/components/site/harness/ArtifactsView";
import { undeclaredProvenance } from "@/lib/stream/provenance";
import { RecordsTable } from "@/components/ds/RecordsTable";
import { Button } from "@/components/ds/Button";
import { asResolvedArtifacts } from "@/lib/stream/artifacts";
import type { ProjectionResponse } from "@/lib/planner";

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
    <main className="share-frame mx-auto flex min-h-screen w-full max-w-[1060px] flex-col px-5 py-10 sm:px-8">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <a href="/" className="text-[15px] font-semibold tracking-tight text-ink">dime</a>
        <span className="text-[11px] uppercase tracking-[0.08em] text-ink-3">{label ?? "shared cap scenario"}</span>
        <span className="rounded-full border border-line px-2 py-px font-mono text-[9.5px] uppercase tracking-wide text-ink-3">
          read-only
        </span>
      </header>
      <div className="flex-1">{children}</div>
      <section className="mt-10 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-[10px] bg-surface px-5 py-4 shadow-hairline">
        <p className="max-w-[420px] text-[12.5px] leading-[1.55] text-ink-2">
          Explore the full analysis in the workbench. Ask follow-up questions, adjust the moves, run the scenarios yourself.
        </p>
        <Button asChild variant="accent" size="sm">
          <a href="/">Open in Dime</a>
        </Button>
      </section>
      <footer className="mt-6 border-t border-line pt-4 text-[12px] leading-[1.6] text-ink-3">
        <p>dime is an AI analyst workbench for NBA data.</p>
      </footer>
    </main>
  );
}

const kindNoun: Record<string, string> = { cap_scenario: "scenario", trade_scenario: "trade construction", thread_grant: "analysis thread", board: "board" };

export function SharedScenarioNotice({ tone, kind }: { tone: "archived" | "not_found" | "invalid" | "unsupported" | "unavailable"; kind?: string }) {
  const noun = kindNoun[kind ?? ""] ?? "object";
  const copy: Record<typeof tone, { title: string; body: string }> = {
    archived: {
      title: `This ${noun} was taken down`,
      body: `The owner archived this shared ${noun}. The link still resolves so you know what happened to it, but the contents are no longer shared.`,
    },
    not_found: {
      title: `This shared ${noun} no longer exists`,
      body: `The link may have been rotated by its owner (rotating a share link retires the old one), or the ${noun} was never shared at this address.`,
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
      title: `This ${noun} can't be loaded right now`,
      body: "The workbench backend isn't reachable. This is usually temporary; try again in a moment.",
    },
  };
  const { title, body } = copy[tone];
  return (
    <SharedFrame label={`shared ${noun}`}>
      <section className="mx-auto mt-[18vh] max-w-[560px] rounded-[10px] bg-surface p-8 shadow-hairline">
        <h1 className="text-[17px] font-semibold text-ink">{title}</h1>
        <p className="mt-2 text-[13px] leading-[1.6] text-ink-2">{body}</p>
      </section>
    </SharedFrame>
  );
}

export function SharedScenarioView({
  object,
  evaluation,
}: {
  object: SharedObject;
  evaluation: ProjectionResponse | null;
}) {
  const moves = object.payload.moves;
  const groupsMeta = (object.payload as { groups?: MoveGroupsMap }).groups ?? {};
  const errors = (evaluation?.errors ?? []).filter(Boolean);
  const evaluationFailed = evaluation !== null && (evaluation.ok === false || errors.length > 0);
  const seasons = evaluation?.seasons ?? [];
  const baseSeason = seasons[0];

  return (
    <SharedFrame>
      <div className="mt-6">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1 text-[12.5px] text-ink-3">
          {object.payload.team} · {object.payload.season} · shared {sharedDate(object.updated_at)}
        </p>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">Moves</h2>
            <div className="mt-2 space-y-1.5">
              <ReadOnlyMoveList moves={moves} groups={groupsMeta} />
            </div>
            {evaluation === null && (
              <p className="mt-3 border-t border-line pt-2 text-[12px] leading-[1.55] text-ink-3">
                This scenario could not be evaluated live. The stored moves are shown as shared, without computed cap impact.
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

          {seasons.map((season) => (
            <section key={season.season} className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-[13px] font-semibold text-ink">{season.season}</h2>
                <span className="font-mono text-[12px] tabular-nums text-ink">
                  payroll {money(season.pay_after)}
                </span>
              </div>
              <div className="mt-2 space-y-1 font-mono text-[11px] tabular-nums text-ink-3">
                <div className="flex justify-between"><span>cap room</span><span className={season.cap_room < 0 ? "text-red" : ""}>{money(season.cap_room)}</span></div>
                <div className="flex justify-between"><span>cap</span><span>{money(season.lines.cap)}</span></div>
                <div className="flex justify-between"><span>tax line</span><span>{money(season.lines.tax)}</span></div>
                <div className="flex justify-between"><span>first apron</span><span>{money(season.lines.apron1)}</span></div>
                <div className="flex justify-between"><span>second apron</span><span>{money(season.lines.apron2)}</span></div>
                {(season.cap_holds ?? 0) > 0 && (
                  <div className="flex justify-between">
                    <span>cap holds{season.cap_holds_exactness ? ` (${season.cap_holds_exactness})` : ""}</span>
                    <span>{money(season.cap_holds)}</span>
                  </div>
                )}
                {((season.dead_money ?? 0) > 0 || (season.dead_money_players ?? []).some((d) => d.amount_unknown)) && (
                  <div className="flex justify-between">
                    <span title={(season.dead_money_players ?? []).map((d) => d.amount_unknown ? `${d.player}: amount unknown — ${deadMoneyBasisWords(d.basis)}` : `${d.player} ${money(d.salary)}`).join(" · ")}>
                      dead money{(season.dead_money_players ?? []).length > 0 ? ` (${(season.dead_money_players ?? []).map((d) => d.player.split(" ").slice(-1)[0]).join(", ")})` : ""}
                    </span>
                    <span title={(season.dead_money_players ?? []).some((d) => d.amount_unknown) ? "excludes obligations of unknown amount — this figure is a floor, not an exact total" : undefined}>
                      {money(season.dead_money)}{(season.dead_money_players ?? []).some((d) => d.amount_unknown) ? "+" : ""}
                    </span>
                  </div>
                )}
              </div>
              {season.effects.length > 0 && (
                <ol className="mt-2 space-y-1 border-t border-line pt-2">
                  {season.effects.map((effect, i) => (
                    <li key={i} className="flex items-baseline justify-between gap-3 text-[12px]">
                      <span className="min-w-0 text-ink-2">
                        {effect.detail}
                        {effect.exactness !== "exact" && (
                          <span className="ml-1.5 rounded-full border border-line px-1.5 py-px font-mono text-[9px] uppercase tracking-wide text-ink-3">{effect.exactness}</span>
                        )}
                      </span>
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-ink-3">
                        {effect.delta > 0 ? "+" : ""}{money(effect.delta)}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
              {(season.exceptions ?? []).length > 0 && (
                <div className="mt-2 space-y-1 border-t border-line pt-2">
                  {(season.exceptions ?? []).map((ex) => (
                    <div key={ex.exception} className="flex items-baseline justify-between gap-3 text-[11.5px]">
                      <span className="text-ink-2">
                        {ex.exception.toUpperCase()}
                        {ex.hard_caps && <span className="ml-1.5 rounded-full border border-red px-1.5 py-px font-mono text-[9px] uppercase tracking-wide text-red">hard-caps</span>}
                        {ex.unavailable && <span className="ml-1.5 font-mono text-[9.5px] uppercase tracking-wide text-ink-3">unavailable</span>}
                      </span>
                      <span className="font-mono text-[10.5px] tabular-nums text-ink-3">
                        {ex.used > 0 ? `${money(ex.used)} used · ` : ""}{money(ex.remaining)} left
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {((season as { trade_exceptions?: { amount: number; kind: string; exactness: string; status: string; note: string }[] }).trade_exceptions ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5 border-t border-line pt-2">
                  {((season as { trade_exceptions?: { amount: number; kind: string; exactness: string; status: string; note: string }[] }).trade_exceptions ?? []).map((tpe, i) => (
                    <span
                      key={i}
                      title={tpe.note}
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${tpe.status === "active" ? "bg-field text-ink-2" : "bg-field/50 text-ink-3 line-through"}`}
                    >
                      TPE {money(tpe.amount)} · {tpe.exactness.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              )}
              {season.roster_issues.length > 0 && (
                <div className="mt-2 border-t border-line pt-2">
                  {season.roster_issues.map((issue, i) => (
                    <p key={i} className="text-[11.5px] leading-[1.5] text-ink-3">{issue}</p>
                  ))}
                </div>
              )}
              {season.ordering_notes.length > 0 && (
                <div className="mt-2 border-t border-line pt-2">
                  {season.ordering_notes.map((note, i) => (
                    <p key={i} className="text-[11.5px] leading-[1.5] text-ink-3">{note}</p>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          {baseSeason && !evaluationFailed && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Apron state after moves</h2>
              <div className="mt-2 space-y-1.5 text-[12px]">
                {([
                  ["tax", baseSeason.pay_after > baseSeason.lines.tax],
                  ["first apron", baseSeason.pay_after > baseSeason.lines.apron1],
                  ["second apron", baseSeason.pay_after > baseSeason.lines.apron2],
                ] as const).map(([label, over]) => (
                  <div key={label} className="flex items-baseline justify-between">
                    <span className="text-ink-2">{label}</span>
                    <span className={`font-mono text-[10.5px] lowercase ${over ? "text-red" : "text-ink-3"}`}>
                      {over ? "over" : "under"}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
          {(evaluation?.disclosures?.length ?? 0) > 0 && (
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Method disclosures</h2>
              <ul className="mt-2 space-y-2.5">
                {(evaluation?.disclosures ?? []).map((disclosure, i) => (
                  <li key={i} className="relative pl-3.5 text-[11.5px] leading-[1.6] text-ink-3">
                    <span aria-hidden="true" className="absolute left-0 top-[7px] h-px w-2 bg-line-strong" />
                    {disclosure}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">About this link</h2>
            <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
              Evaluated live against the current warehouse snapshot when you opened it. Numbers recompute at open time and can move as the data moves. This is a read-only view; the scenario can't be edited here.
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

      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
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
                This construction could not be evaluated live. The stored legs are shown as shared, without a legality verdict.
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
                          <span className={`font-mono text-[10px] lowercase ${over ? "text-red" : "text-ink-3"}`}>
                            {over ? "over" : "under"}
                          </span>
                        </div>
                      ))}
                      {row.hard_cap && (
                        <div className="flex items-baseline justify-between">
                          <span className="text-ink-3">hard cap</span>
                          <span className="font-mono text-[10px] lowercase text-red">{row.hard_cap}</span>
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
              Evaluated live against the current warehouse snapshot when you opened it. The verdict recomputes at open time and can move as rosters move. This is a read-only view; the construction can't be edited here.
            </p>
          </section>
        </aside>
      </div>
    </SharedFrame>
  );
}
function evidenceLine(table: TranscriptEntry["tables"][number]): string {
  const meta = table.meta ?? {};
  const parts = [
    table.tool ?? "source",
    meta.source ? `source ${meta.source}` : "",
    meta.season ? `season ${meta.season}` : "",
    meta.fetched_at ? `fetched ${String(meta.fetched_at).slice(0, 10)}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

export function SharedThreadView({
  object,
  transcript,
}: {
  object: SharedThreadObject;
  transcript: TranscriptEntry[];
}) {
  const ordered = [...transcript].reverse();
  return (
    <SharedFrame label="shared analysis thread">
      <div className="mt-6">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1 text-[12.5px] text-ink-3">
          {ordered.length} {ordered.length === 1 ? "analysis" : "analyses"} · shared {sharedDate(object.updated_at)}
        </p>
      </div>

      <div className="mt-6 space-y-4">
        {ordered.length === 0 && (
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <p className="text-[12.5px] leading-[1.6] text-ink-2">
              This thread had no analyses to show at the time it was shared.
            </p>
          </section>
        )}
        {ordered.map((entry, i) => (
          <section key={i} className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13.5px] font-semibold leading-[1.45] text-ink">{entry.question}</h2>
            <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-[1.65] text-ink-2">{entry.answer}</p>
            {entry.tables.length > 0 && (
              <div className="mt-3 border-t border-line pt-2">
                {entry.tables.map((table, j) => (
                  <p key={j} className="font-mono text-[10.5px] leading-[1.6] text-ink-3">{evidenceLine(table)}</p>
                ))}
              </div>
            )}
          </section>
        ))}

        <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
          <h2 className="text-[13px] font-semibold text-ink">About this link</h2>
          <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
            This is a snapshot of the thread as it existed when the owner shared it; anything added to the conversation afterwards is not visible here. This is a read-only view; the thread can't be continued or edited here.
          </p>
        </section>
      </div>
    </SharedFrame>
  );
}
function evidenceMetaLine(ev: SharedArtifactEvidence): string {
  const meta = ev.meta ?? {};
  const parts = [
    ev.tool ?? "source",
    typeof meta.source === "string" ? `source ${meta.source}` : "",
    typeof meta.season === "string" ? `season ${meta.season}` : "",
    typeof meta.fetched_at === "string" ? `fetched ${meta.fetched_at.slice(0, 10)}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

export function SharedArtifactView({
  object,
  artifact,
  evidence,
  capturedAt,
  unavailable,
}: {
  object: SharedArtifactObject;
  artifact: Record<string, unknown> | null;
  evidence: SharedArtifactEvidence[];
  capturedAt: string | null;
  unavailable: boolean;
}) {
  const resolved = artifact ? asResolvedArtifacts([artifact]) : [];
  const resolvedArtifact = resolved.length > 0 ? resolved[0] : null;
  return (
    <SharedFrame label="shared artifact">
      <div className="mt-6">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1 text-[12.5px] text-ink-3">
          {capturedAt ? `captured ${sharedDate(capturedAt)}` : `shared ${sharedDate(object.updated_at)}`}
        </p>
      </div>

      <div className="mt-6 space-y-4">
        {unavailable || !artifact || !resolvedArtifact ? (
          <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">This artifact can&apos;t be resolved</h2>
            <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
              The analysis run this artifact points into is no longer available on the server. The link itself is valid; the underlying data is gone.
            </p>
          </section>
        ) : (
          <>
            <section className="rounded-[10px] bg-surface shadow-hairline">
              <ArtifactBody artifact={resolvedArtifact} />
            </section>

            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Provenance</h2>
              <ProvenancePanel provenance={resolvedArtifact.provenance ?? undeclaredProvenance()} />
            </section>

            {evidence.length > 0 && (
              <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
                <h2 className="text-[13px] font-semibold text-ink">Pinned evidence</h2>
                <div className="mt-2 space-y-2">
                  {evidence.map((ev, i) => {
                    const rows = Array.isArray(ev.rows) ? ev.rows : [];
                    const line = ev.missing ? `${ev.ref} — source record no longer resolvable` : evidenceMetaLine(ev);
                    if (ev.missing || rows.length === 0) {
                      return (
                        <p key={i} className="font-mono text-[10.5px] leading-[1.6] text-ink-3">{line}</p>
                      );
                    }
                    return (
                      <details key={i} className="group">
                        <summary className="cursor-pointer font-mono text-[10.5px] leading-[1.6] text-ink-3 underline decoration-line underline-offset-2 hover:text-ink-2">
                          {line} · {rows.length} {rows.length === 1 ? "row" : "rows"}
                        </summary>
                        <div className="mt-2">
                          <RecordsTable rows={rows} title={ev.tool ?? ev.ref ?? "evidence"} />
                        </div>
                      </details>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}

        <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
          <h2 className="text-[13px] font-semibold text-ink">About this link</h2>
          <p className="mt-2 text-[12px] leading-[1.6] text-ink-3">
            This artifact is pinned to the exact evidence rows it was built from, captured when the analysis ran. Where the warehouse has been refreshed since, the numbers reflect the capture-time snapshot; the pinned evidence above shows what the figures rest on. This is a read-only view.
          </p>
        </section>
      </div>
    </SharedFrame>
  );
}
