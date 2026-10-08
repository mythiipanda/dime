"use client";

import { useMemo, useState, type ReactNode } from "react";

export type ArtifactColumn = { key: string; label: string; numeric?: boolean };

function Chevron({ dir }: { dir: 1 | -1 }) {
  return (
    <svg width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden
      style={{ transform: dir === 1 ? "rotate(180deg)" : "none", transition: "transform 150ms cubic-bezier(0.16,1,0.3,1)" }}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export default function ArtifactTable<T extends (string | number)[]>({
  columns,
  rows,
  renderCell,
}: {
  columns: ArtifactColumn[];
  rows: T[];
  renderCell?: (row: T, col: number) => ReactNode;
}) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const arr = [...rows];
    arr.sort((ra, rb) => {
      const va = ra[sort.col];
      const vb = rb[sort.col];
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
    renderCell ? renderCell(row, i) : String(row[i]);

  return (
    <table className="w-full text-[13px]">
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-line">
          {columns.map((c, i) => (
            <th key={c.key} className={`p-0 text-[13px] font-medium ${i === 0 ? "pl-4" : "pl-3"} ${i === columns.length - 1 ? "pr-4" : "pr-3"}`}>
              <button
                type="button"
                onClick={() => toggle(i)}
                className={`flex h-[32px] w-full items-center gap-1 transition-colors duration-100 hover:text-ink ${
                  c.numeric ? "justify-end tabular-nums" : "justify-start"
                } ${sort?.col === i ? "text-ink" : "text-ink-2"}`}
              >
                {c.label}
                {sort?.col === i && <Chevron dir={sort.dir} />}
              </button>
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
                  c.numeric ? "text-right font-mono tabular-nums" : ""
                }`}
              >
                {cell(row, i)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
