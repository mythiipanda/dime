import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex w-full rounded-lg border px-3 py-2 text-sm field-sizing-content min-h-20 placeholder:text-muted-foreground outline-none transition-colors disabled:cursor-not-allowed disabled:opacity-70",
        "bg-background dark:bg-black/20",
        "border-input dark:border-white/20",
        "focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-blue-400/80 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "aria-[invalid=true]:border-red-500/70 aria-[invalid=true]:ring-red-500/50",
        "disabled:bg-muted/50 disabled:dark:bg-black/30 disabled:border-input disabled:dark:border-white/10 disabled:text-gray-500",
        "selection:bg-primary selection:text-primary-foreground",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
