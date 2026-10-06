export type Grade = "G1" | "G2" | "G3" | "G4";

export interface GradeInput {
  method?: string | null;
  methodKind?: string | null;
  windowN?: number | null;
  windowKind?: "games" | "meetings" | null;
  lineage?: string | null;
  season?: string | null;
}

export interface GradedClaim {
  grade: Grade;
  tag: string;
  scope: string;
  method: string;
  gap: string;
  unknownScope: boolean;
}

export function gradeLimits(grade: Grade, unknownScope: boolean): string {
  if (unknownScope) return "";
  switch (grade) {
    case "G1":
      return "Season totals hide recent form";
    case "G2":
      return "Window only, not the full season";
    case "G3":
      return "Small sample, treat as a hint";
    case "G4":
      return "Not observed results";
  }
}

function cleanLines(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

const ESTIMATE_HINTS = [
  "estimat",
  "deriv",
  "shrink",
  "simulat",
  "monte carlo",
  "project",
  "raptor",
  "regress",
  "imput",
  "synth",
  "forecast",
  "z-score",
  "zscore",
  "weighted sum",
];

export function isEstimateMethod(method: string): boolean {
  const lowered = method.toLowerCase();
  return ESTIMATE_HINTS.some((hint) => lowered.includes(hint));
}

const ESTIMATE_KINDS = ["estimate"];
const NON_ESTIMATE_KINDS = ["official", "derived"];

export function gradeClaim(input: GradeInput): GradedClaim {
  const method = cleanLines(input.method);
  const season = cleanLines(input.season);
  const kind = cleanLines(input.methodKind).toLowerCase();
  const typed = ESTIMATE_KINDS.includes(kind) || NON_ESTIMATE_KINDS.includes(kind);
  const estimated =
    ESTIMATE_KINDS.includes(kind) || (!typed && method !== "" && isEstimateMethod(method));
  if (estimated) {
    return {
      grade: "G4",
      tag: "Model estimate",
      scope: season ? `Estimated · ${season}` : "Estimated",
      method,
      gap: "",
      unknownScope: false,
    };
  }
  const windowN =
    typeof input.windowN === "number" && Number.isFinite(input.windowN) && input.windowN > 0
      ? Math.floor(input.windowN)
      : null;
  if (windowN !== null) {
    if (windowN === 1 || input.windowKind === "meetings") {
      const tag = windowN === 1 ? "Single game" : `${windowN} meetings`;
      return {
        grade: "G3",
        tag,
        scope: season ? `${tag} · ${season}` : tag,
        method,
        gap: "",
        unknownScope: false,
      };
    }
    return {
      grade: "G2",
      tag: `Last ${windowN} games`,
      scope: season ? `Last ${windowN} games · ${season}` : `Last ${windowN} games`,
      method,
      gap: "",
      unknownScope: false,
    };
  }
  if (input.lineage === "live") {
    return {
      grade: "G4",
      tag: "Unconfirmed scope",
      scope: season ? `Live data · ${season}` : "Live data",
      method,
      gap: "couldn't confirm the scope",
      unknownScope: true,
    };
  }
  if (season && input.lineage === "warehouse") {
    return {
      grade: "G1",
      tag: "Full season",
      scope: `Full season · ${season}`,
      method,
      gap: "",
      unknownScope: false,
    };
  }
  return {
    grade: "G4",
    tag: "Unconfirmed scope",
    scope: season ? season : "Scope unconfirmed",
    method,
    gap: "couldn't confirm the scope",
    unknownScope: true,
  };
}
