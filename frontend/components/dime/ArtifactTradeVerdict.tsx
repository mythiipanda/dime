"use client";

import { AlertTriangle, ArrowRight } from "lucide-react";
import { StatusPill } from "@/components/ds/StatusPill";
import { formatHeadlineMetric } from "@/lib/metric-format";
import type { TradeVerdictArtifactPayload, TradeVerdictTeamPayload } from "@/lib/dime-stream";

function money(value: number | undefined): string {
  return value === undefined ? "—" : formatHeadlineMetric(value, "usd_dollars");
}

function pickLabel(pick: { year: number; round: number; swap?: boolean; protection?: string }): string {
  const round = pick.round === 1 ? "1st" : pick.round === 2 ? "2nd" : `R${pick.round}`;
  return `${pick.year} ${round}${pick.swap ? " swap" : ""}${pick.protection ? ` (${pick.protection})` : ""}`;
}

function assetLine(players: string[], picks: { year: number; round: number; swap?: boolean; protection?: string }[] | undefined): string {
  const parts = [...players];
  if (picks) parts.push(...picks.map(pickLabel));
  return parts.length ? parts.join(", ") : "—";
}

function TeamPanel({ team }: { team: TradeVerdictTeamPayload }) {
  const flags = [
    team.overApron2 ? "over second apron" : undefined,
    team.overApron1 && !team.overApron2 ? "over first apron" : undefined,
    team.aggregates ? "aggregates" : undefined,
  ].filter(Boolean) as string[];
  return (
    <div className="min-w-0 flex-1 rounded-lg border border-line bg-inset p-3 sm:min-w-[240px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="break-words text-[15px] font-medium tracking-tight text-ink">{team.team}</h4>
        {team.hardCap ? (
          <StatusPill tone="orange" dot={false}>{`hard-cap: ${team.hardCap}`}</StatusPill>
        ) : null}
      </div>
      {flags.length > 0 && <p className="mt-1 text-xs text-ink-3">{flags.join(" · ")}</p>}
      <dl className="mt-3 space-y-2.5 text-[13px]">
        <div>
          <dt className="text-xs text-ink-3">Out</dt>
          <dd className="mt-0.5 break-words text-ink">{assetLine(team.playersOut, team.picksOut)}</dd>
          <dd className="tabular-nums text-ink-2">{money(team.outgoing)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-3">In</dt>
          <dd className="mt-0.5 break-words text-ink">{assetLine(team.playersIn, team.picksIn)}</dd>
          <dd className="tabular-nums text-ink-2">{money(team.incoming)}</dd>
        </div>
        {(team.payrollBefore !== undefined || team.payrollAfter !== undefined) && (
          <div>
            <dt className="text-xs text-ink-3">Payroll</dt>
            <dd className="mt-0.5 flex flex-wrap items-center gap-1.5 tabular-nums text-ink-2">
              {money(team.payrollBefore)}
              {team.payrollAfter !== undefined && team.payrollAfter !== team.payrollBefore && (
                <>
                  <ArrowRight size={12} aria-hidden="true" className="text-ink-3" />
                  {money(team.payrollAfter)}
                </>
              )}
            </dd>
          </div>
        )}
        {team.allowedIncoming !== undefined && (
          <div>
            <dt className="text-xs text-ink-3">Allowed incoming</dt>
            <dd className={`mt-0.5 tabular-nums ${team.matchingFailed ? "text-red" : "text-ink-2"}`}>{money(team.allowedIncoming)}</dd>
          </div>
        )}
      </dl>
      {team.matchRule && <p className="mt-3 border-t border-line pt-2 text-xs leading-relaxed text-ink-3">{team.matchRule}</p>}
      {team.tpeCreation && (
        <p className="mt-2 break-words text-xs leading-relaxed text-accent-ink">
          {`creates a ${money(team.tpeCreation.amount)} trade exception`}{team.tpeCreation.condition ? " if executed non-simultaneously" : ""}
        </p>
      )}
    </div>
  );
}

export default function ArtifactTradeVerdict({ artifact }: { artifact: TradeVerdictArtifactPayload }) {
  return (
    <div className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusPill tone={artifact.legal ? "green" : "red"}>
          {artifact.legal ? "Legal" : "Illegal"}
        </StatusPill>
        <span className="text-xs text-ink-3">
          {artifact.evaluationTool ? `evaluated by ${artifact.evaluationTool}` : "evaluator verdict"}
          {artifact.provenance?.season ? ` · ${artifact.provenance.season}` : ""}
        </span>
      </div>
      {artifact.issues && artifact.issues.length > 0 && (
        <ul className="mb-4 space-y-1.5 border-t border-line pt-3">
          {artifact.issues.map((issue, index) => (
            <li key={index} className="flex items-start gap-2 text-[13px] leading-relaxed text-ink">
              <AlertTriangle size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-red" />
              <span className="min-w-0 break-words">{issue}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {artifact.teams.map((team, index) => (
          <TeamPanel key={`${team.team}-${index}`} team={team} />
        ))}
      </div>
      {artifact.checks && artifact.checks.length > 0 && (
        <dl className="mt-4 space-y-1.5 border-t border-line pt-3">
          {artifact.checks.map((check, index) => (
            <div key={index} className="flex flex-wrap items-baseline gap-x-2 text-xs">
              <dt className="shrink-0 font-medium text-ink-2">{check.rule}</dt>
              {check.note && <dd className="min-w-0 flex-1 break-words text-ink-3">{check.note}</dd>}
            </div>
          ))}
        </dl>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <p className="text-xs text-ink-3">
          The verdict is the evaluator&apos;s, resolved server-side. Estimate only; confirm with a cap specialist.
        </p>
      </div>
    </div>
  );
}
