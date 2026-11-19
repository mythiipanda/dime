"use client";

import { Shimmer } from "./ds/Shimmer";

export default function Skeleton({ lines = 3, widths, label }: { lines?: number; widths?: number[]; label?: string }) {
  const values = widths?.length ? widths : [90, 70, 55, 80];
  return <div role="status" aria-label={label || "Loading"} className="w-full space-y-3 py-1">{label && <div className="mb-3 text-[12px]"><Shimmer>{label}</Shimmer></div>}{Array.from({ length: Math.max(1, Math.min(8, lines)) }, (_, i) => <div key={i} className="h-3 animate-pulse rounded-md bg-hover-2 motion-reduce:animate-none" style={{ width: values[i % values.length] + "%" }} />)}</div>;
}
