"use client";

import * as RadioGroup from "@radix-ui/react-radio-group";
import { cn } from "@/lib/utils";

export function SegmentedControl<T extends string>({ options, value, onChange, className, label = "View", labels, disabled = false }: {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  label?: string;
  labels?: Partial<Record<T, string>>;
  disabled?: boolean;
}) {
  return <RadioGroup.Root aria-label={label} value={value} onValueChange={next => { if (options.includes(next as T)) onChange(next as T); }} disabled={disabled} className={cn("ds-segmented", className)}>
    {options.map(option => <RadioGroup.Item key={option} value={option} onFocus={() => { if (!disabled && value !== option) onChange(option); }} className="ds-segment">
      {labels?.[option] ?? option}
    </RadioGroup.Item>)}
  </RadioGroup.Root>;
}
