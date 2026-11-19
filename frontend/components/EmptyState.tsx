"use client";

import type { ReactNode } from "react";
import { Button } from "./ds/Button";

interface Props { icon?: ReactNode; title: string; description: string; actionLabel?: string; onAction?: () => void; }

export default function EmptyState({ icon, title, description, actionLabel, onAction }: Props) {
  return <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
    {icon && <div className="mb-1 text-ink-3" aria-hidden>{icon}</div>}
    <p className="text-[13px] font-medium text-ink">{title}</p><p className="max-w-sm text-[12px] leading-relaxed text-ink-3">{description}</p>
    {actionLabel && onAction && <Button size="sm" className="mt-3" onClick={onAction}>{actionLabel}</Button>}
  </div>;
}
