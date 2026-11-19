"use client";

import { Input } from "@base-ui/react/input";
import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export const TextField = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextField({ className, ...props }, ref) {
  return <Input ref={ref} className={cn("ds-field", className)} {...props} />;
});
