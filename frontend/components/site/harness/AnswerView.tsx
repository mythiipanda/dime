"use client";

import type { ReactNode } from "react";
import { QuietDetails } from "@/components/ds/QuietDetails";
import {
  failureCopy,
  gapSentence,
  mergeArtifactProvenance,
  verificationDisclosure,
  type DimeArtifact,
  type ToolState,
  type VerificationCarry,
} from "@/lib/dime-stream";
import type { AnswerBlock, PiSource } from "@/lib/evidence";
import { StreamArtifacts } from "./ArtifactsView";


export function Ico({ d, size = 15 }: { d: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {d}
    </svg>
  );
}

export function OmittedNote({ omitted }: { omitted: string[] }) {
  return (
    <p className="mt-2 max-w-[620px] text-[12px] text-orange">
      Partial answer — not covered: {omitted.join("; ")}
    </p>
  );
}

export function SourceRefDetails({ carry, prefix = "" }: { carry: VerificationCarry; prefix?: string }) {
  return (
    <QuietDetails label={<>Sources</>}>
      {carry.sources?.map((source) => (
        <details key={source.ref} id={`${prefix}source-${source.ref}`} className="mt-2 text-[12px]">
          <summary>{source.label}</summary>
          {source.rows.length > 0 && (
            <div className="overflow-auto">
              <table className="mt-2 w-full text-left">
                <thead>
                  <tr>
                    {Object.keys(source.rows[0]).map((column) => (
                      <th key={column} className="pr-4">
                        {column}
                        {source.units[column] ? ` (${source.units[column]})` : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {source.rows.map((row, index) => (
                    <tr key={index} id={`${prefix}source-${source.ref}-row-${index}`} tabIndex={-1}>
                      {Object.keys(source.rows[0]).map((column) => (
                        <td key={column} className="pr-4" data-col={column}>
                          {typeof row[column] === "object"
                            ? JSON.stringify(row[column])
                            : String(row[column] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <details className="mt-2">
            <summary>Provenance</summary>
            <pre className="overflow-auto whitespace-pre-wrap">
              {JSON.stringify(source.data, null, 2)}
            </pre>
          </details>
        </details>
      ))}
    </QuietDetails>
  );
}

export function AnswerVerification({
  carry,
  artifacts,
  prefix = "",
}: {
  carry: VerificationCarry | null;
  artifacts: DimeArtifact[];
  prefix?: string;
}) {
  const provenance = mergeArtifactProvenance(artifacts);
  if (carry?.sourceRefs) return <SourceRefDetails carry={carry} prefix={prefix} />;
  if (!carry && !provenance) return null;
  const disclosure = verificationDisclosure(carry, provenance);
  const emptyCase = disclosure.headline === "No verified claims" && disclosure.gaps.length === 0 && (!carry || carry.verification === "unknown");
  if (emptyCase) {
    return <p className="mt-3 max-w-[620px] text-[11.5px] text-ink-3">{disclosure.headline} · {disclosure.detail.replace(/^0 verified claims?\.\s*/, "")}</p>;
  }
  return (
    <div className="mt-3 max-w-[620px]">
      <div className="text-[12px] font-medium text-ink">{disclosure.headline}</div>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-2">{disclosure.detail}</p>
      {carry && (
        <p className="mt-1 text-[11.5px] text-ink-3">
          {`Verification status: ${carry.verification === "unknown" ? "not reported" : carry.verification}`}
        </p>
      )}
      {disclosure.gaps.length > 0 && (
        <div className="mt-2 flex gap-2 border-t border-line pt-2">
          <span className="mt-px shrink-0 text-orange">
            <Ico
              size={13}
              d={
                <>
                  <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </>
              }
            />
          </span>
          <div className="min-w-0">
            <div className="text-[12px] font-medium text-ink">
              What this answer could not confirm
            </div>
            <ul className="mt-0.5 flex flex-col gap-0.5">
              {disclosure.gaps.map((gap, i) => (
                <li
                  key={i}
                  data-gap-kind={gap.kind}
                  className="text-[11.5px] leading-relaxed text-ink-2"
                >
                  {gapSentence(gap)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function FollowUpPills({
  items,
  onPick,
}: {
  items: string[];
  onPick: (s: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {items.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onPick(s)}
          className="rounded-full bg-surface px-3 py-1.5 text-left text-[12px] text-ink shadow-btn transition-[background-color,transform] duration-150 hover:bg-hover active:scale-[0.97]"
        >
          {s}
        </button>
      ))}
    </div>
  );
}

export function StoppedNote() {
  return (
    <p className="mt-2 max-w-[620px] text-[12px] text-ink-3">
      Stopped — partial answer shown.
    </p>
  );
}

