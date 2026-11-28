export function unitEmbeddedInline(unit: string | undefined): boolean {
  return unit === "usd_dollars" || unit === "usd_millions" || Boolean(unit && unit.startsWith("$"));
}

export function formatHeadlineMetric(value: unknown, unit: string | undefined): string {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value);
  if (unit && unit.startsWith("$") && unit.length <= 3) {
    return `$${num}${unit.slice(1)}`;
  }
  if (unit === "usd_dollars" || unit === "usd_millions") {
    const dollars = unit === "usd_millions" ? num * 1_000_000 : num;
    const abs = Math.abs(dollars);
    const sign = dollars < 0 ? "-" : "";
    if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`;
    return `${sign}$${abs.toFixed(0)}`;
  }
  if (Number.isInteger(num)) {
    const abs = Math.abs(num);
    if (abs >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
    if (abs >= 10_000) return num.toLocaleString("en-US");
    return String(value);
  }
  return String(value);
}
