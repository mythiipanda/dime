"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from "iconoir-react";
import { Button } from "@/components/ds/Button";

export type ArtifactColumn = { key: string; label: string; numeric?: boolean };

export default function ArtifactTable<T extends (string | number | null)[]>({
  columns,
  rows,
  renderCell,
  title = "Evidence table",
  footnote,
}: {
  columns: ArtifactColumn[];
  rows: T[];
  renderCell?: (row: T, col: number) => ReactNode;
  title?: string;
  footnote?: string;
}) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null);
  const regionRef = useRef<HTMLDivElement>(null);
  const hintId = useId();
  const [scroll, setScroll] = useState({ left: false, right: false });
  const measureScroll = useCallback(() => {
    const region = regionRef.current;
    if (region) setScroll({ left: region.scrollLeft > 1, right: region.scrollLeft + region.clientWidth < region.scrollWidth - 1 });
  }, []);
  useEffect(() => {
    measureScroll();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measureScroll);
    if (regionRef.current) {
      observer?.observe(regionRef.current);
      const table = regionRef.current.querySelector("table");
      if (table) observer?.observe(table);
    }
    window.addEventListener("resize", measureScroll);
    return () => { observer?.disconnect(); window.removeEventListener("resize", measureScroll); };
  }, [measureScroll, columns, rows]);
  const scrollColumns = (direction: number) => {
    const region = regionRef.current;
    region?.scrollBy({ left: direction * region.clientWidth * 0.75, behavior: "auto" });
  };

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
    <div className="relative min-w-0">
    {(scroll.left || scroll.right) && <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
      <p id={hintId} className="text-xs text-ink-2">Scroll for all columns</p>
      <div className="flex gap-1">
        <Button size="icon" variant="quiet" aria-label="Scroll table left" disabled={!scroll.left} onClick={() => scrollColumns(-1)}><ArrowLeft width={14} height={14} aria-hidden="true" /></Button>
        <Button size="icon" variant="quiet" aria-label="Scroll table right" disabled={!scroll.right} onClick={() => scrollColumns(1)}><ArrowRight width={14} height={14} aria-hidden="true" /></Button>
      </div>
    </div>}
    <div ref={regionRef} onScroll={measureScroll} role="region" aria-label={`${title} records`} aria-describedby={scroll.left || scroll.right ? hintId : undefined} tabIndex={0} className="max-h-[420px] overflow-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-ink">
    <table className="w-full text-[13px]">
      <caption className="sr-only">{title}</caption>
      <thead className="sticky top-0 z-10 bg-surface">
        <tr className="border-b border-line">
          {columns.map((c, i) => (
            <th key={c.key} scope="col" aria-sort={sort?.col === i ? sort.dir === 1 ? "ascending" : "descending" : "none"} className={`p-0 text-[13px] font-medium ${i === 0 ? "pl-4" : "pl-3"} ${i === columns.length - 1 ? "pr-4" : "pr-3"}`}>
              <Button
                variant="quiet" size="sm"
                onClick={() => toggle(i)}
                className={`h-auto min-h-9 w-full gap-1 whitespace-normal rounded-none px-0 py-2 ${
                  c.numeric ? "justify-end tabular-nums" : "justify-start"
                } ${sort?.col === i ? "text-ink" : "text-ink-2"}`}
              >
                <span className="min-w-0 break-words">{c.label}</span>
                {sort?.col === i && (sort.dir === 1 ? <ArrowUp width={12} height={12} aria-hidden="true" /> : <ArrowDown width={12} height={12} aria-hidden="true" />)}
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
                style={{ overflowWrap: "break-word", minWidth: 64 }}
              >
                {cell(row, i)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table></div>
    <div className="border-t border-line px-4 py-2 text-xs text-ink-3">
      {footnote && <p className="break-words leading-relaxed">{footnote}</p>}
      <p>{rows.length} {rows.length === 1 ? "record" : "records"}{rows.length === 0 && ". No records available. Adjust the query or choose another season."}</p>
    </div>
    </div>
  );
}
