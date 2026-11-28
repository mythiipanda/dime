import { parseAnswerSubmission, parsePiSources } from "../evidence";
import {
  asNumber,
  asRecord,
  trimmedString,
  type DimeArtifact,
  type DimeProvenance,
  type EvidenceGapNote,
  type ProvenanceEvidence,
  type ProvenanceOrigin,
  type VerificationCarry,
  type VerificationDisclosure,
  type VerificationStatus,
} from "./types";

function safeSourceUrl(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return /^https?:\/\/\S+$/i.test(trimmed) ? trimmed : null;
}

const LIVE_SOURCE_IDS = new Set(["nba_api", "basketball_reference", "espn"]);

function validSourceId(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return LIVE_SOURCE_IDS.has(trimmed) ? trimmed : null;
}

function compactProvenance(fields: DimeProvenance): DimeProvenance {
  const provenance: DimeProvenance = {
    origin: fields.origin,
    liveSources: fields.liveSources,
  };
  if (fields.capability) provenance.capability = fields.capability;
  if (fields.warehouseId) provenance.warehouseId = fields.warehouseId;
  if (fields.dataset) provenance.dataset = fields.dataset;
  if (fields.sql) provenance.sql = fields.sql;
  if (fields.season) provenance.season = fields.season;
  if (fields.asOf) provenance.asOf = fields.asOf;
  if (fields.as_of) provenance.as_of = fields.as_of;
  if (fields.liveSourceIds && fields.liveSourceIds.length > 0) {
    provenance.liveSourceIds = fields.liveSourceIds;
  }
  return provenance;
}

export function undeclaredProvenance(): DimeProvenance {
  return { origin: "undeclared", liveSources: [] };
}

function originFromParts(
  live: boolean,
  warehouse: boolean,
  unknown: boolean,
): ProvenanceOrigin {
  if (live && warehouse) return "mixed";
  if ((live || warehouse) && unknown) return "partly-undeclared";
  if (live) return "live";
  if (warehouse) return "warehouse";
  return "undeclared";
}

function originParts(
  origin: ProvenanceOrigin | undefined,
): { live: boolean; warehouse: boolean } {
  if (origin === "live") return { live: true, warehouse: false };
  if (origin === "warehouse") return { live: false, warehouse: true };
  if (origin === "mixed") return { live: true, warehouse: true };
  return { live: false, warehouse: false };
}

export function parseProvenance(raw: unknown): DimeProvenance {
  const record = asRecord(raw);
  const warehouseId = trimmedString(record.warehouse_id);
  const rawSources = Array.isArray(record.live_sources) ? record.live_sources : [];
  const liveSources = [...new Set(
    rawSources
      .map(safeSourceUrl)
      .filter((url): url is string => url !== null),
  )];
  const liveSourceIds = [...new Set(
    rawSources
      .map(validSourceId)
      .filter((id): id is string => id !== null),
  )];
  const producer = record.origin;
  const declaresMixed = producer === "mixed";
  const hasLive = liveSources.length > 0 || liveSourceIds.length > 0;
  const live = producer === "live" || (declaresMixed && hasLive);
  const warehouse =
    (producer === "warehouse" || declaresMixed) && warehouseId !== undefined;
  const asOf = trimmedString(record.as_of);
  return compactProvenance({
    origin: originFromParts(live, warehouse, declaresMixed && !(live && warehouse)),
    capability: trimmedString(record.capability),
    warehouseId,
    dataset: trimmedString(record.dataset),
    sql: trimmedString(record.sql),
    season: trimmedString(record.season),
    asOf,
    ...(asOf ? { as_of: asOf } : {}),
    liveSources,
    liveSourceIds,
  });
}

function agreedValue(values: (string | undefined)[]): string | undefined {
  const [first, ...rest] = values;
  if (first === undefined) return undefined;
  return rest.every((value) => value === first) ? first : undefined;
}

function readableProvenance(raw: unknown): DimeProvenance | null {
  const record = asRecord(raw);
  const origin = trimmedString(record.origin);
  if (origin === undefined || !Array.isArray(record.liveSources)) return null;
  return raw as DimeProvenance;
}

function coalescedEvidence(
  entries: (DimeProvenance | undefined)[],
): ProvenanceEvidence[] | undefined {
  let nested = false;
  const collected: ProvenanceEvidence[] = [];
  for (const entry of entries) {
    const evidence = entry?.evidence;
    if (!Array.isArray(evidence) || evidence.length === 0) continue;
    nested = true;
    for (const item of evidence) {
      const provenance = readableProvenance(item?.provenance);
      const label = trimmedString(item?.label);
      if (label === undefined || provenance === null) return undefined;
      collected.push({ label, provenance });
    }
  }
  if (!nested) return undefined;
  const unique: ProvenanceEvidence[] = [];
  const seen = new Set<string>();
  for (const item of collected) {
    const key = `${item.label}\u0000${JSON.stringify(item.provenance)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }
  return unique.length ? unique : undefined;
}

export function mergeProvenance(
  entries: (DimeProvenance | undefined)[],
): DimeProvenance {
  let live = false;
  let warehouse = false;
  let unknown = false;
  for (const entry of entries) {
    const parts = originParts(entry?.origin);
    live ||= parts.live;
    warehouse ||= parts.warehouse;
    unknown ||= !parts.live && !parts.warehouse;
  }
  const merged = compactProvenance({
    origin: originFromParts(live, warehouse, unknown),
    capability: agreedValue(entries.map((entry) => entry?.capability)),
    warehouseId: agreedValue(entries.map((entry) => entry?.warehouseId)),
    season: agreedValue(entries.map((entry) => entry?.season)),
    asOf: agreedValue(entries.map((entry) => entry?.asOf)),
    liveSources: [
      ...new Set(entries.flatMap((entry) => entry?.liveSources ?? [])),
    ],
    liveSourceIds: [
      ...new Set(entries.flatMap((entry) => entry?.liveSourceIds ?? [])),
    ],
  });
  const evidence = coalescedEvidence(entries);
  if (evidence) merged.evidence = evidence;
  return merged;
}

export function mergeArtifactProvenance(
  artifacts: DimeArtifact[],
): DimeProvenance | undefined {
  if (artifacts.length === 0) return undefined;
  return mergeProvenance(
    artifacts.map((artifact) => artifact.provenance ?? undeclaredProvenance()),
  );
}

export function originPhrase(
  provenance: DimeProvenance | undefined,
): string {
  if (!provenance) return "not declared";
  if (provenance.origin === "warehouse") {
    return provenance.warehouseId
      ? `declared warehouse ${provenance.warehouseId}`
      : "declared warehouse";
  }
  if (provenance.origin === "live") return "live source";
  if (provenance.origin === "mixed") return "mixed live and warehouse sources";
  if (provenance.origin === "partly-undeclared") return "mixed sources, partly undeclared";
  return "not declared";
}

export function provenanceSource(
  provenance: DimeProvenance | undefined,
): string | undefined {
  if (!provenance) return undefined;
  if (provenance.origin === "warehouse") {
    return provenance.warehouseId
      ? `dime warehouse \u00b7 ${provenance.warehouseId}`
      : "dime warehouse";
  }
  if (provenance.origin === "live") return "live sources";
  if (provenance.origin === "mixed") return "mixed sources";
  if (provenance.origin === "partly-undeclared") return "mixed sources, partly undeclared";
  return "source not declared";
}

function parseGap(raw: unknown): EvidenceGapNote | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  const record = raw as Record<string, unknown>;
  const kind = trimmedString(record.kind);
  if (kind === undefined) return null;
  const rawBlocks = record.blocks;
  if (rawBlocks === undefined) return { kind, blocks: [] };
  if (!Array.isArray(rawBlocks)) return null;
  const blocks: string[] = [];
  for (const item of rawBlocks) {
    const block = trimmedString(item);
    if (block === undefined) return null;
    blocks.push(block);
  }
  return { kind, blocks };
}

function checkedClaimCount(raw: unknown): number | null {
  const claims = asNumber(raw);
  return claims !== undefined && Number.isInteger(claims) && claims >= 0 ? claims : null;
}

export function parseCarry(raw: unknown): VerificationCarry | null {
  if (raw === null || raw === undefined) return null;
  const record = asRecord(raw);
  const verification: VerificationStatus =
    record.verification === "pass" || record.verification === "partial"
      ? record.verification
      : "unknown";
  const verifiedClaims = checkedClaimCount(record.verified_claims);
  const rawGaps = record.gaps;
  const parsedGaps = Array.isArray(rawGaps) ? rawGaps.map(parseGap) : [];
  const gaps = parsedGaps.filter((gap): gap is EvidenceGapNote => gap !== null);
  const gapsReadable = Array.isArray(rawGaps) && gaps.length === rawGaps.length;
  const runId = trimmedString(record.run_id);
  const submission = parseAnswerSubmission(record.submission);
  if (verification === "unknown" && verifiedClaims === null && !runId && gaps.length === 0 && !submission) {
    return null;
  }
  const carry: VerificationCarry = { verification, verifiedClaims, gaps, gapsReadable };
  if (runId) carry.runId = runId;
  if (submission) carry.submission = submission;
  if (Array.isArray(record.source_refs)) {
    carry.sourceRefs = record.source_refs.filter((ref): ref is string => typeof ref === "string");
    carry.sources = parsePiSources(record.sources).filter((source) =>
      carry.sourceRefs?.includes(source.ref),
    );
  }
  return carry;
}

const GAP_COPY: Record<string, string> = {
  missing_evidence: "Some of what you asked for isn't backed by data.",
  source_conflict: "The sources behind this disagree with each other.",
  unsupported_claim: "Some of this isn't supported by the data behind it.",
  execution_failure: "Some of the data behind this was unavailable.",
  synthesis_incomplete: "Part of this answer couldn't be finished.",
  "profile/name_resolution_unavailable":
    "Some players or teams couldn't be matched to their profile data.",
  judge_unavailable:
    "This answer couldn't be double-checked, so treat the details with extra care.",
  provider_error: "The model behind the double-check was unavailable.",
};

const UNKNOWN_GAP_SENTENCE = "Part of this answer could not be fully verified.";

export function gapSentence(gap: EvidenceGapNote): string {
  return GAP_COPY[gap.kind] ?? UNKNOWN_GAP_SENTENCE;
}

function originSentence(provenance: DimeProvenance | undefined): string {
  return `Origin: ${originPhrase(provenance)}.`;
}

function unverifiedReason(carry: VerificationCarry): string {
  if (carry.verification === "unknown") {
    return "This run did not report a verification status.";
  }
  if (!carry.gapsReadable) {
    return "The run reported a pass, but its gap report could not be read.";
  }
  if (carry.verifiedClaims === null) {
    return "The run reported a pass, but not how many claims it checked.";
  }
  return "The run reported a pass, but these numbers are not all from a declared warehouse source.";
}

export function verificationDisclosure(
  carry: VerificationCarry | null,
  provenance: DimeProvenance | undefined,
): VerificationDisclosure {
  const origin = originSentence(provenance);
  if (!carry) {
    return {
      state: "unknown",
      headline: "Verification unknown",
      detail: `This run did not report whether its numbers were checked. ${origin}`,
      gaps: [],
    };
  }
  const claims = carry.verifiedClaims;
  const claimText =
    claims === null
      ? "verified claim count not reported"
      : `${claims} verified claim${claims === 1 ? "" : "s"}`;
  const gapCount = carry.gaps.length;
  const unreadableText = carry.gapsReadable ? "" : " The run's gap report could not be read.";
  const gapText = gapCount
    ? ` ${gapCount} gap${gapCount === 1 ? "" : "s"} reported.${unreadableText}`
    : unreadableText;
  const passReported =
    carry.verification === "pass" &&
    claims !== null &&
    claims > 0 &&
    carry.gapsReadable &&
    gapCount === 0;
  if (passReported && provenance?.origin === "warehouse") {
    const where = provenance.warehouseId
      ? `declared warehouse ${provenance.warehouseId}`
      : "declared warehouse";
    return {
      state: "verified",
      headline: "Verified",
      detail: `${claimText} from the ${where}.`,
      gaps: carry.gaps,
    };
  }
  if (carry.verification === "partial" || claims === 0 || gapCount > 0) {
    return {
      state: "partial",
      headline: claims === 0 ? "No verified claims" : "Verification partial",
      detail: `${claimText}.${gapText} ${origin}`,
      gaps: carry.gaps,
    };
  }
  return {
    state: "unverified",
    headline: "Not verified",
    detail: `${unverifiedReason(carry)} This answer is not shown as verified. ${origin}`,
    gaps: carry.gaps,
  };
}
