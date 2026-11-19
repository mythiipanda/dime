"use client";

import { Radio } from "@base-ui/react/radio";
import { RadioGroup } from "@base-ui/react/radio-group";
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
  return <RadioGroup aria-label={label} value={value} onValueChange={onChange} disabled={disabled} className={cn("ds-segmented", className)}>
    {options.map(option => <Radio.Root key={option} value={option} render={<button type="button" />} nativeButton className="ds-segment">
      {labels?.[option] ?? option}
    </Radio.Root>)}
  </RadioGroup>;
}
