import { Database } from "iconoir-react";

export function RecordsTable({ rows, title, source }: { rows: Record<string, unknown>[]; title: string; source?: string }) {
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((k) => rows.some((r) => r[k] == null || typeof r[k] !== "object"));
  if (!rows.length) return <p className="text-[12px] text-ink-3">No records available.</p>;
  return <div className="my-5 overflow-hidden rounded-xl border border-line bg-surface">
    <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-[12px] font-medium"><Database width={14} height={14} className="text-ink-3" />{title}<span className="ml-auto text-[11px] font-normal text-ink-3">{rows.length} records</span></div>
    <div className="overflow-x-auto"><table className="w-full border-collapse text-left text-[12px]"><thead><tr>{columns.map((c) => <th key={c} className="whitespace-nowrap border-b border-line bg-inset px-4 py-2 font-normal text-ink-3">{c.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i} className="border-b border-line last:border-0 hover:bg-hover">{columns.map((c) => <td key={c} className="whitespace-nowrap px-4 py-2.5 tabular-nums text-ink-2">{row[c] == null ? "—" : typeof row[c] === "object" ? "—" : String(row[c])}</td>)}</tr>)}</tbody></table></div>
    {source && <div className="border-t border-line px-4 py-2 text-[10px] text-ink-3">{source}</div>}
  </div>;
}
=======
import { Database } from "lucide-react";
import { cn } from "@/lib/utils";

export function RecordsTable({ rows, title, source }: { rows: Record<string, unknown>[]; title: string; source?: string }) {
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter((k) => rows.some((r) => r[k] == null || typeof r[k] !== "object"));
  const numeric = new Set(columns.filter(c => rows.some(row => typeof row[c] === "number") && rows.every(row => row[c] == null || typeof row[c] === "number")));
  return <div className="ds-records">
    <div className="ds-records-heading"><Database size={14} aria-hidden="true" /><span className="min-w-0 break-words">{title}</span><span className="ds-records-count">{rows.length} {rows.length === 1 ? "record" : "records"}</span></div>
    {rows.length > 0 && columns.length > 0 ? <div className="ds-records-scroll" role="region" aria-label={`${title} records`} tabIndex={0}><table className="ds-records-table"><caption className="sr-only">{title}</caption><thead><tr>{columns.map(c => <th key={c} scope="col" className={cn(numeric.has(c) && "is-numeric")}>{c.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{columns.map(c => <td key={c} className={cn(numeric.has(c) && "is-numeric")}>{row[c] == null || typeof row[c] === "object" ? <span className="text-ink-3" aria-label="Not available">—</span> : String(row[c])}</td>)}</tr>)}</tbody></table></div> : <p className="ds-records-empty">No records available. Adjust the query or choose a different season.</p>}
    {source && <div className="ds-records-source"><span className="font-medium text-ink-2">Source</span><span>{source}</span></div>}
  </div>;
}
>>>>>>> origin/dev
