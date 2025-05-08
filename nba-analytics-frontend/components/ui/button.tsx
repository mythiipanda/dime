'use client'

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 ease-in-out disabled:pointer-events-none disabled:opacity-80 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-blue-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 " +
          "dark:bg-gradient-to-r dark:from-blue-600 dark:to-cyan-500 dark:text-white dark:font-semibold dark:shadow-md dark:hover:shadow-lg dark:hover:shadow-cyan-500/30 dark:hover:from-blue-500 dark:hover:to-cyan-400 dark:disabled:opacity-60",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90 " +
          "dark:bg-red-600/90 dark:text-white dark:shadow-md dark:hover:bg-red-500/90 dark:hover:shadow-red-500/30 dark:focus-visible:ring-red-500/60 dark:disabled:opacity-60",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground " +
          "dark:border-white/30 dark:bg-white/5 dark:text-gray-200 dark:hover:bg-white/10 dark:hover:border-white/40 dark:hover:text-white dark:disabled:opacity-60 dark:disabled:bg-white/5 dark:disabled:text-gray-400",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 " +
          "dark:bg-gray-700/60 dark:text-gray-200 dark:border dark:border-white/15 dark:hover:bg-gray-600/70 dark:hover:border-white/25 dark:disabled:opacity-60",
        ghost:
          "hover:bg-accent hover:text-accent-foreground " +
          "dark:text-gray-300 dark:hover:bg-white/10 dark:hover:text-white dark:focus-visible:bg-white/10 dark:disabled:opacity-60",
        link:
          "text-primary underline-offset-4 hover:underline " +
          "dark:text-cyan-400 dark:hover:text-cyan-300 dark:focus-visible:text-cyan-300 dark:focus-visible:ring-cyan-400/30 dark:disabled:opacity-60",
      },
      size: {
        default: "h-10 px-4 py-2 has-[>svg]:px-3",
        sm: "h-9 rounded-md gap-1.5 px-3 has-[>svg]:px-2",
        lg: "h-11 rounded-lg px-6 has-[>svg]:px-4",
        icon: "size-10 rounded-lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
