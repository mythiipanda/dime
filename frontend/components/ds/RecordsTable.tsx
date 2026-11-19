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
