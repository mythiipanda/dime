"use client"

import * as React from "react"
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"

import { cn } from "@/lib/utils"

function ScrollArea({
  className,
  children,
  ...props
}: React.ComponentProps<typeof ScrollAreaPrimitive.Root>) {
  return (
    <ScrollAreaPrimitive.Root
      data-slot="scroll-area"
      className={cn("relative animate-in fade-in-0 duration-300", className)} // Added entrance animation
      {...props}
    >
      <ScrollAreaPrimitive.Viewport
        data-slot="scroll-area-viewport"
        className="size-full rounded-[inherit]" /* Removed focus styles and transition */
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
}

function ScrollBar({
  className,
  orientation = "vertical",
  ...props
}: React.ComponentProps<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      data-slot="scroll-area-scrollbar"
      orientation={orientation}
      className={cn(
        "flex touch-none p-px transition-colors duration-150 ease-in-out select-none data-[orientation=vertical]:hover:bg-muted/50 data-[orientation=horizontal]:hover:bg-muted/50", // Added hover effect to track
        orientation === "vertical" &&
          "h-full w-2 border-l border-l-transparent", /* Spacing: w-2 (8px) */
        orientation === "horizontal" &&
          "h-2 flex-col border-t border-t-transparent", /* Spacing: h-2 (8px) */
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb
        data-slot="scroll-area-thumb"
        className="bg-muted relative flex-1 rounded-full transition-colors duration-150 ease-in-out hover:bg-primary/60 data-[state=visible]:bg-primary/50" // Added transitions and hover/active state for thumb
      />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  )
}

export { ScrollArea, ScrollBar }
