"use client";

import type { ReactNode } from "react";
import { QuietDetails } from "@/components/ds/QuietDetails";
import ToolChips, { type ToolStep } from "@/components/primitives/ToolChips";
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
import { FADE_UP, type AssistantFailure, type LiveRun } from "./types";

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

function toolStepFor(tool: ToolState): ToolStep {
  const summary =
    tool.status === "running"
      ? "running"
      : tool.status === "fail"
        ? "failed"
        : [
            tool.rows !== undefined ? `${tool.rows} rows` : null,
            tool.ms !== undefined ? `${tool.ms}ms` : null,
          ]
            .filter(Boolean)
            .join(" \u00b7 ") || "done";
  const detail = [
    ...(tool.args ?? []),
    ...(tool.error ? [tool.error] : []),
  ].map((text) => ({ text }));
  return {
    icon: "read",
    key: tool.key,
    label: tool.label,
    chip: summary,
    mono: true,
    detailMono: true,
    detail: detail.length ? detail : [{ text: summary }],
    args: tool.args,
  };
}

function FailureCard({ failure }: { failure: AssistantFailure }) {
  const copy = failureCopy(failure.kind);
  return (
    <div
      className="mt-4 max-w-[620px] rounded-xl border border-line bg-surface px-3.5 py-3 shadow-hairline"
      style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both" }}
    >
      <div className="text-[13px] font-medium text-ink">{copy.title}</div>
      <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{copy.body}</p>
    </div>
  );
}

export function AnswerBlocks({
  blocks,
  sources,
}: {
  blocks: AnswerBlock[];
  sources?: PiSource[];
}) {
  return (
    <div className="space-y-3">
      {blocks.map((block, i) => (
        <p key={i} className="whitespace-pre-line">
          {block.text}
          {block.anchors.length > 0 && (
            <span className="ml-1.5 inline-flex flex-wrap gap-1 text-[11px] align-baseline">
              {block.anchors.map((anchor, aIdx) => {
                const source = sources?.find((s) => s.ref === anchor.ref);
                const rowData = source?.rows?.[anchor.row];
                const isResolvable =
                  Boolean(rowData) &&
                  anchor.columns.length > 0 &&
                  anchor.columns.every((c) => Object.hasOwn(rowData as object, c));

                const sourceLabel = source?.label || anchor.ref;
                const colSummary = anchor.columns.join(", ");
                const chipText = `${sourceLabel} [r${anchor.row + 1}: ${colSummary}]`;
                const title = `Source: ${sourceLabel} | Row ${anchor.row + 1} | Columns: ${colSummary}`;

                if (isResolvable) {
                  return (
                    <a
                      key={`${anchor.ref}-${anchor.row}-${aIdx}`}
                      href={`#source-${anchor.ref}-row-${anchor.row}`}
                      className="rounded bg-fill-subtle px-1.5 py-0.5 font-mono text-[10.5px] text-ink-2 hover:bg-fill hover:text-ink hover:underline"
                      title={title}
                      data-ref={anchor.ref}
                      data-row={anchor.row}
                      data-columns={colSummary}
                    >
                      {chipText}
                    </a>
                  );
                }

                return (
                  <span
                    key={`${anchor.ref}-${anchor.row}-${aIdx}`}
                    className="rounded bg-fill-subtle px-1.5 py-0.5 font-mono text-[10.5px] text-ink-3 opacity-70"
                    title={`Unresolved source reference: ${anchor.ref}`}
                  >
                    {chipText}
                  </span>
                );
              })}
            </span>
          )}
        </p>
      ))}
    </div>
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
    <QuietDetails label={<>Sources &amp; provenance</>}>
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

function LiveStatus({
  label,
  secs,
  done,
}: {
  label: string;
  secs: number;
  done: boolean;
}) {
  if (done) {
    return (
      <div
        className="text-[13px] font-medium text-ink-2"
        style={{ animation: FADE_UP }}
      >
        {`Thought for ${secs} seconds`}
      </div>
    );
  }
  return (
    <span role="status" className="contents">
      <span
        className="bg-clip-text text-[13px] font-medium whitespace-nowrap text-transparent"
        style={{
          backgroundImage:
            "linear-gradient(90deg, var(--ink-3) 35%, var(--ink) 50%, var(--ink-3) 65%)",
          backgroundSize: "200% 100%",
          animation:
            "shimmer-text 1.4s linear infinite, fade-up 280ms cubic-bezier(0.23,1,0.32,1) both",
        }}
      >
        {label}
      </span>
    </span>
  );
}

function AnswerCopy({
  submission,
  text,
  animate,
}: {
  submission: VerificationCarry["submission"] | undefined;
  text: string;
  animate?: boolean;
}) {
  const style = animate ? { animation: FADE_UP } : undefined;
  if (submission?.blocks?.length) {
    return (
      <div className="mt-4 max-w-[620px] text-[13.5px] leading-[1.65] text-ink-2" style={style}>
        <AnswerBlocks blocks={submission.blocks} />
      </div>
    );
  }
  if (!text) return null;
  return (
    <p
      className="mt-4 max-w-[620px] whitespace-pre-line text-[13.5px] leading-[1.65] text-ink-2"
      style={style}
    >
      {text}
    </p>
  );
}

export function LiveAssistant({ live }: { live: LiveRun }) {
  const steps = live.tools.map(toolStepFor);
  const secs = Math.max(1, Math.round((Date.now() - live.startedAt) / 1000));
  const statusLine = live.thinking.length
    ? live.thinking[live.thinking.length - 1].label
    : "Thinking";
  return (
    <>
      <div className="mt-2">
        <LiveStatus
          key={`${live.id}:${live.thinking.length}`}
          label={statusLine}
          secs={secs}
          done={live.done}
        />
      </div>
      {steps.length > 0 && (
        <div className="mt-3">
          <ToolChips
            steps={steps}
            diffs={[]}
            labels={{
              header: `${steps.length} tool call${steps.length === 1 ? "" : "s"}`,
              more: "",
            }}
          />
        </div>
      )}
      <StreamArtifacts artifacts={live.artifacts} />
      {live.carry?.submission?.blocks?.length ? (
        <div className="mt-4 max-w-[620px] text-[13.5px] leading-[1.65] text-ink-2">
          <AnswerBlocks blocks={live.carry.submission.blocks} sources={live.carry.sources} />
        </div>
      ) : (
        <AnswerCopy submission={undefined} text={live.text} />
      )}
      {live.carry?.submission?.omitted?.length ? (
        <OmittedNote omitted={live.carry.submission.omitted} />
      ) : null}
      <AnswerVerification carry={live.carry} artifacts={live.artifacts} />
      {live.failed && <FailureCard failure={live.failed} />}
    </>
  );
}

export function StoppedNote() {
  return (
    <p className="mt-2 max-w-[620px] text-[12px] text-ink-3">
      Stopped — partial answer shown.
    </p>
  );
}

export function AssistantTurn({
  text,
  artifacts,
  suggestions,
  carry,
  failure,
  stopped,
  onFollowUp,
}: {
  text: string;
  artifacts: DimeArtifact[];
  suggestions: string[];
  carry: VerificationCarry | null;
  failure: AssistantFailure | null;
  stopped?: boolean;
  onFollowUp: (s: string) => void;
}) {
  return (
    <>
      <StreamArtifacts artifacts={artifacts} />
      {carry?.submission?.blocks?.length ? (
        <div
          className="mt-4 max-w-[620px] text-[13.5px] leading-[1.65] text-ink-2"
          style={{ animation: FADE_UP }}
        >
          <AnswerBlocks blocks={carry.submission.blocks} sources={carry.sources} />
        </div>
      ) : (
        <AnswerCopy submission={undefined} text={text} animate />
      )}
      {carry?.submission?.omitted?.length ? (
        <OmittedNote omitted={carry.submission.omitted} />
      ) : null}
      {stopped ? <StoppedNote /> : null}
      <AnswerVerification carry={carry} artifacts={artifacts} />
      {failure && <FailureCard failure={failure} />}
      <FollowUpPills items={suggestions} onPick={onFollowUp} />
    </>
  );
}
