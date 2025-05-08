'use client'

import * as React from "react"

import { cn } from "@/lib/utils"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full min-w-0 rounded-lg border px-3 py-2 text-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground outline-none disabled:cursor-not-allowed disabled:opacity-70",
          "bg-background dark:bg-black/20",
          "border-input dark:border-white/20",
          "focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-blue-400/80 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          "aria-[invalid=true]:border-red-500/70 aria-[invalid=true]:ring-red-500/50",
          "disabled:bg-muted/50 disabled:dark:bg-black/30 disabled:border-input disabled:dark:border-white/10 disabled:text-gray-500",
          "selection:bg-primary selection:text-primary-foreground",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
