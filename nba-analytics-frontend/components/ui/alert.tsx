import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "relative w-full rounded-md border px-4 py-3 text-sm flex items-start gap-x-3 [&>svg]:size-4 [&>svg]:translate-y-px [&>svg]:text-current animate-in fade-in-0 slide-in-from-top-2 duration-300", /* Spacing: rounded-md, translate-y-px for better icon alignment, Added slide-in */
  {
    variants: {
      variant: {
        default: "bg-card text-card-foreground",
        destructive:
          "text-destructive border-destructive/50 dark:border-destructive bg-card [&>svg]:text-destructive *:data-[slot=alert-description]:text-destructive/90",
        info:
          "text-sky-700 border-sky-500/50 dark:text-sky-300 dark:border-sky-500 bg-card [&>svg]:text-sky-600 dark:[&>svg]:text-sky-400 *:data-[slot=alert-description]:text-sky-700/90 dark:*:data-[slot=alert-description]:text-sky-300/90",
        success:
          "text-emerald-700 border-emerald-500/50 dark:text-emerald-300 dark:border-emerald-500 bg-card [&>svg]:text-emerald-600 dark:[&>svg]:text-emerald-400 *:data-[slot=alert-description]:text-emerald-700/90 dark:*:data-[slot=alert-description]:text-emerald-300/90",
        warning:
          "text-amber-700 border-amber-500/50 dark:text-amber-300 dark:border-amber-500 bg-card [&>svg]:text-amber-600 dark:[&>svg]:text-amber-400 *:data-[slot=alert-description]:text-amber-700/90 dark:*:data-[slot=alert-description]:text-amber-300/90",
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
        "line-clamp-1 font-semibold tracking-tight", /* Typography: font-semibold, removed col-start-2 */
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
        "text-muted-foreground grid justify-items-start gap-1 text-sm [&_p]:leading-relaxed", /* removed col-start-2 */
        className
      )}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription }
