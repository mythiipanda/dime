import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "relative w-full rounded-lg border p-4 text-sm flex items-start gap-x-3 [&>svg]:size-5 [&>svg]:translate-y-px [&>svg]:text-current animate-in fade-in-0 slide-in-from-top-2 duration-300", /* Spacing: rounded-lg, translate-y-px for better icon alignment, Added slide-in */
  {
    variants: {
      variant: {
        default:
          "border-border bg-card text-card-foreground dark:border-white/20 dark:bg-card/70 dark:backdrop-blur-md",
        destructive:
          "border-destructive/50 bg-card text-destructive [&>svg]:text-destructive *:data-[slot=alert-description]:text-destructive/90 " +
          "dark:text-red-300 dark:[&>svg]:text-red-400 dark:*:data-[slot=alert-description]:text-red-300/90 dark:border-red-500/50 dark:bg-card/70 dark:backdrop-blur-md",
        info:
          "border-sky-500/50 bg-card text-sky-700 [&>svg]:text-sky-600 *:data-[slot=alert-description]:text-sky-700/90 " +
          "dark:text-blue-200 dark:[&>svg]:text-blue-300 dark:*:data-[slot=alert-description]:text-blue-200/90 dark:border-blue-500/50 dark:bg-card/70 dark:backdrop-blur-md",
        success:
          "border-emerald-500/50 bg-card text-emerald-700 [&>svg]:text-emerald-600 *:data-[slot=alert-description]:text-emerald-700/90 " +
          "dark:text-green-200 dark:[&>svg]:text-green-300 dark:*:data-[slot=alert-description]:text-green-200/90 dark:border-green-500/50 dark:bg-card/70 dark:backdrop-blur-md",
        warning:
          "border-amber-500/50 bg-card text-amber-700 [&>svg]:text-amber-600 *:data-[slot=alert-description]:text-amber-700/90 " +
          "dark:text-yellow-200 dark:[&>svg]:text-yellow-300 dark:*:data-[slot=alert-description]:text-yellow-200/90 dark:border-yellow-500/50 dark:bg-card/70 dark:backdrop-blur-md",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-semibold tracking-tight text-foreground",
        className
      )}
      {...props}
    />
  )
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "text-sm text-muted-foreground/90 [&_p]:leading-relaxed",
        className
      )}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
