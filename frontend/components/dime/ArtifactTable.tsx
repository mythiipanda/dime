"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@/components/ds/Button";

export type ArtifactColumn = { key: string; label: string; numeric?: boolean };

export default function ArtifactTable<T extends (string | number | null)[]>({
  columns,
  rows,
  renderCell,
  title = "Evidence table",
}: {
  columns: ArtifactColumn[];
  rows: T[];
  renderCell?: (row: T, col: number) => ReactNode;
  title?: string;
}) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const arr = [...rows];
    arr.sort((ra, rb) => {
      const va = ra[sort.col];
      const vb = rb[sort.col];
      if (va == null || va === "") return vb == null || vb === "" ? 0 : 1;
      if (vb == null || vb === "") return -1;
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return cmp * sort.dir;
    });
    return arr;
  }, [rows, sort]);

  const toggle = (i: number) =>
    setSort((s) =>
      s && s.col === i
        ? { col: i, dir: s.dir === 1 ? -1 : 1 }
        : { col: i, dir: columns[i].numeric ? -1 : 1 }
    );

  const cell = (row: T, i: number): ReactNode =>
    renderCell ? renderCell(row, i) : row[i] == null || row[i] === "" ? <span aria-label="Not available" className="text-ink-3">—</span> : String(row[i]);

  return (
    <div>
    <div role="region" aria-label={`${title} records`} tabIndex={0} className="max-h-[420px] overflow-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-ink">
    <table className="w-full text-[13px]">
      <caption className="sr-only">{title}</caption>
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-line">
          {columns.map((c, i) => (
            <th key={c.key} scope="col" aria-sort={sort?.col === i ? sort.dir === 1 ? "ascending" : "descending" : "none"} className={`p-0 text-[13px] font-medium ${i === 0 ? "pl-4" : "pl-3"} ${i === columns.length - 1 ? "pr-4" : "pr-3"}`}>
              <Button
                variant="quiet" size="sm"
                onClick={() => toggle(i)}
                className={`w-full gap-1 whitespace-nowrap rounded-none px-0 ${
                  c.numeric ? "justify-end tabular-nums" : "justify-start"
                } ${sort?.col === i ? "text-ink" : "text-ink-2"}`}
              >
                {c.label}
                {sort?.col === i && (sort.dir === 1 ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
              </Button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {sorted.map((row, ri) => (
          <tr key={ri} className="h-[35px] transition-colors duration-100 hover:bg-hover">
            {columns.map((c, i) => (
              <td
                key={c.key}
                className={`${i === 0 ? "pl-4" : "pl-3"} ${i === columns.length - 1 ? "pr-4" : "pr-3"} ${
                  c.numeric ? "text-right tabular-nums" : ""
                }`}
                style={{ overflowWrap: "anywhere", minWidth: 88 }}
              >
                {cell(row, i)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table></div>
    <p className="border-t border-line px-4 py-2 text-xs text-ink-3">{rows.length} {rows.length === 1 ? "record" : "records"}{rows.length === 0 && ". No records available. Adjust the query or choose another season."}</p>
    </div>
  );
}
