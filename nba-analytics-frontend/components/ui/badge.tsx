import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400/60 focus:ring-offset-1 focus:ring-offset-background animate-in fade-in-0 zoom-in-95 duration-200",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80 " +
          "dark:bg-blue-600/30 dark:text-blue-200 dark:ring-1 dark:ring-inset dark:ring-blue-400/30 dark:hover:bg-blue-600/40",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80 " +
          "dark:bg-gray-700/60 dark:text-gray-300 dark:ring-1 dark:ring-inset dark:ring-gray-500/40 dark:hover:bg-gray-700/70",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80 " +
          "dark:bg-red-600/40 dark:text-red-200 dark:ring-1 dark:ring-inset dark:ring-red-500/40 dark:hover:bg-red-600/50",
        outline:
          "text-foreground border-border hover:bg-accent " +
          "dark:text-gray-300 dark:border-white/30 dark:hover:bg-white/10",
        success:
          "border-transparent bg-emerald-500 text-white hover:bg-emerald-500/90 " +
          "dark:bg-green-600/30 dark:text-green-200 dark:ring-1 dark:ring-inset dark:ring-green-400/30 dark:hover:bg-green-600/40",
        warning:
          "border-transparent bg-amber-500 text-white hover:bg-amber-500/90 " +
          "dark:bg-yellow-500/30 dark:text-yellow-200 dark:ring-1 dark:ring-inset dark:ring-yellow-400/40 dark:hover:bg-yellow-500/40",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants } 