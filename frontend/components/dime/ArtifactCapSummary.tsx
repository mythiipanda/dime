"use client";

import { AlertTriangle, ArrowRight, Scale } from "lucide-react";
import { StatusPill } from "@/components/ds/StatusPill";
import { formatHeadlineMetric } from "@/lib/metric-format";
import type { CapSummaryArtifactPayload } from "@/lib/dime-stream";

function money(value: number | undefined): string {
  return value === undefined ? "—" : formatHeadlineMetric(value, "usd_dollars");
}

function signedMoney(value: number): string {
  const rendered = formatHeadlineMetric(Math.abs(value), "usd_dollars");
  return value > 0 ? `+${rendered}` : value < 0 ? `-${rendered}` : rendered;
}

function RoomRow({ label, before, after }: { label: string; before?: number; after?: number }) {
  if (after === undefined && before === undefined) return null;
  return (
    <div className="min-w-0 flex-1 rounded-lg border border-line bg-inset p-3 sm:min-w-[150px]">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className={`mt-1 flex flex-wrap items-center gap-1.5 tabular-nums text-[15px] font-medium ${after !== undefined && after < 0 ? "text-red" : "text-ink"}`}>
        {before !== undefined && before !== after ? (
          <>
            <span className="text-ink-3">{money(before)}</span>
            <ArrowRight size={12} aria-hidden="true" className="text-ink-3" />
          </>
        ) : null}
        {money(after)}
      </dd>
    </div>
  );
}

export default function ArtifactCapSummary({ artifact }: { artifact: CapSummaryArtifactPayload }) {
  const flags = [
    artifact.overApron2 ? "over second apron" : undefined,
    artifact.overApron1 && !artifact.overApron2 ? "over first apron" : undefined,
    artifact.overTax ? "over tax" : undefined,
  ].filter(Boolean) as string[];
  const delta = artifact.delta ?? artifact.payrollAfter - artifact.payrollBefore;
  return (
    <div className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h4 className="break-words text-[15px] font-medium tracking-tight text-ink">
          {artifact.team}{artifact.season ? ` · ${artifact.season}` : ""}
        </h4>
        {artifact.hardCap ? (
          <StatusPill tone="orange" dot={false}>{`hard-cap: ${artifact.hardCap}`}</StatusPill>
        ) : null}
        {artifact.rosterBefore !== undefined && artifact.rosterAfter !== undefined && artifact.rosterBefore !== artifact.rosterAfter ? (
          <span className="text-xs tabular-nums text-ink-3">{`roster ${artifact.rosterBefore} → ${artifact.rosterAfter}`}</span>
        ) : null}
      </div>
      {flags.length > 0 && <p className="mb-3 text-xs text-ink-3">{flags.join(" · ")}</p>}
      <div className="mb-4 rounded-lg border border-line bg-inset p-3">
        <p className="text-xs text-ink-3">Payroll</p>
        <p className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1 tabular-nums">
          <span className="text-lg font-medium text-ink">{money(artifact.payrollBefore)}</span>
          {artifact.payrollAfter !== artifact.payrollBefore && (
            <>
              <ArrowRight size={13} aria-hidden="true" className="self-center text-ink-3" />
              <span className="text-lg font-medium text-ink">{money(artifact.payrollAfter)}</span>
              <span className={`text-[13px] ${delta > 0 ? "text-red" : delta < 0 ? "text-green" : "text-ink-3"}`}>{signedMoney(delta)}</span>
            </>
          )}
        </p>
      </div>
      <dl className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <RoomRow label="Cap room" before={artifact.capRoomBefore} after={artifact.capRoom} />
        <RoomRow label="Room under tax" after={artifact.taxRoom} />
        <RoomRow label="Room under first apron" after={artifact.roomApron1} />
        <RoomRow label="Room under second apron" after={artifact.roomApron2} />
      </dl>
      {artifact.issues && artifact.issues.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
          {artifact.issues.map((issue, index) => (
            <li key={index} className="flex items-start gap-2 text-[13px] leading-relaxed text-ink">
              <AlertTriangle size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-red" />
              <span className="min-w-0 break-words">{issue}</span>
            </li>
          ))}
        </ul>
      )}
      {artifact.steps && artifact.steps.length > 0 && (
        <ol className="mt-4 space-y-1.5 border-t border-line pt-3">
          {artifact.steps.map((step, index) => (
            <li key={index} className="flex flex-wrap items-baseline gap-x-2 text-[13px]">
              <span className="min-w-0 flex-1 break-words text-ink">{step.detail}</span>
              {step.delta !== undefined && step.delta !== 0 && (
                <span className={`shrink-0 tabular-nums text-xs ${step.delta > 0 ? "text-red" : "text-green"}`}>{signedMoney(step.delta)}</span>
              )}
              {step.payroll !== undefined && (
                <span className="shrink-0 tabular-nums text-xs text-ink-3">{money(step.payroll)}</span>
              )}
            </li>
          ))}
        </ol>
      )}
      {artifact.restrictions && artifact.restrictions.length > 0 && (
        <dl className="mt-4 space-y-1.5 border-t border-line pt-3">
          {artifact.restrictions.map((restriction, index) => (
            <div key={index} className="flex flex-wrap items-baseline gap-x-2 text-xs">
              <dt className="shrink-0 font-medium text-ink-2">{restriction.threshold}</dt>
              <dd className="min-w-0 flex-1 break-words text-ink-3">{restriction.rule}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        <p className="flex items-center gap-1.5 text-xs text-ink-3">
          <Scale size={12} aria-hidden="true" />
          {artifact.evaluationTool ? `Resolved server-side from ${artifact.evaluationTool}.` : "Resolved server-side."} Estimate only — confirm with a cap specialist.
        </p>
      </div>
    </div>
  );
}
