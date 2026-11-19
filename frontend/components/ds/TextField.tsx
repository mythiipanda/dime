import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export const TextField = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextField({ className, ...props }, ref) {
  return <input ref={ref} className={cn("min-w-0 rounded-lg border border-line-strong bg-field px-3 py-2 text-[12px] text-ink placeholder:text-ink-3 focus:border-ink-3 disabled:opacity-50", className)} {...props} />;
});
