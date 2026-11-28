import { Database } from "lucide-react";
import { cn } from "@/lib/utils";

export function RecordsTable({ rows, title, source }: { rows: Record<string, unknown>[]; title: string; source?: string }) {
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((k) => rows.some((r) => r[k] == null || typeof r[k] !== "object"));
  const numeric = new Set(columns.filter(c => rows.some(row => typeof row[c] === "number") && rows.every(row => row[c] == null || typeof row[c] === "number")));
  return <div className="ds-records">
    <div className="ds-records-heading"><Database size={14} aria-hidden="true" /><span className="min-w-0 break-words">{title}</span><span className="ds-records-count">{rows.length} {rows.length === 1 ? "record" : "records"}</span></div>
    {rows.length > 0 && columns.length > 0 ? <div className="ds-records-scroll" role="region" aria-label={`${title} records`} tabIndex={0}><table className="ds-records-table"><caption className="sr-only">{title}</caption><thead><tr>{columns.map(c => <th key={c} scope="col" className={cn(numeric.has(c) && "is-numeric")}>{c.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{columns.map(c => <td key={c} className={cn(numeric.has(c) && "is-numeric")}>{row[c] == null || typeof row[c] === "object" ? <span className="text-ink-3" aria-label="Not available">—</span> : typeof row[c] === "number" && !Number.isInteger(row[c]) ? String(Number((row[c] as number).toPrecision(4))) : String(row[c])}</td>)}</tr>)}</tbody></table></div> : <p className="ds-records-empty">No records available. Adjust the query or choose a different season.</p>}
    {source && <div className="ds-records-source"><span className="font-medium text-ink-2">Source</span><span>{source}</span></div>}
  </div>;
}
