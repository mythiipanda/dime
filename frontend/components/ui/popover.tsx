"use client";

import { forwardRef, type ComponentPropsWithoutRef, type ComponentProps } from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>>(function PopoverContent({ className, align = "center", sideOffset = 4, collisionPadding = 16, ...props }, ref) {
  return <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content ref={ref} align={align} sideOffset={sideOffset} collisionPadding={collisionPadding} className={cn(
      "z-50 flex max-h-[var(--radix-popover-content-available-height)] w-72 max-w-[calc(100vw-2rem)] origin-[var(--radix-popover-content-transform-origin)] flex-col gap-2.5 overflow-y-auto rounded-lg border border-line bg-surface p-4 text-sm text-ink shadow-overlay outline-none duration-150 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 motion-reduce:animate-none",
      className,
    )} {...props} />
  </PopoverPrimitive.Portal>;
});

export function PopoverHeader({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-0.5 text-sm", className)} {...props} />;
}

export function PopoverTitle({ className, ...props }: ComponentProps<"h3">) {
  return <h3 className={cn("font-medium", className)} {...props} />;
}

export function PopoverDescription({ className, ...props }: ComponentProps<"p">) {
  return <p className={cn("text-ink-2", className)} {...props} />;
}
