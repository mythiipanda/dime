"use client";

import { formatStat } from "@/lib/utils"; // Assuming formatStat is moved to utils

export interface StatBoxProps {
    label: string;
    value: number | null | undefined;
    decimals?: number;
    suffix?: string;
}

export function StatBox({ label, value, decimals = 1, suffix = '' }: StatBoxProps) {
    const formattedValue = formatStat(value, decimals);
    return (
        <div className="p-2 rounded-md border bg-muted/50">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
            <p className="text-xl font-semibold">{formattedValue}{formattedValue !== '-' ? suffix : ''}</p>
        </div>
    );
} 