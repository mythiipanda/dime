import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function summarizeValue(v: unknown, cap = 60): string {
  if (Array.isArray(v)) {
    const bits = v
      .filter((x) => typeof x !== "object" || x === null)
      .map((x) => String(x));
    return (bits.join(", ") || `${v.length} items`).slice(0, cap);
  }
  if (typeof v === "object" && v !== null) {
    const text = Object.entries(v)
      .filter(([, x]) => typeof x !== "object" || x === null)
      .map(([k, x]) => `${k} ${String(x)}`)
      .join(", ");
    return (text || "details").slice(0, cap);
  }
  return "";
}
