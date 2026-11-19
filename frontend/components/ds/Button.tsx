"use client";

import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { LoaderCircle } from "lucide-react";
import type { ComponentProps } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "ds-button",
  {
    variants: {
      variant: {
        primary: "bg-ink text-canvas hover:opacity-90",
        secondary: "bg-surface text-ink shadow-btn hover:bg-inset aria-expanded:bg-hover",
        ghost: "bg-hover-2 text-ink hover:bg-line-strong",
        accent: "bg-accent-ink text-page hover:opacity-90",
        success: "bg-green text-page hover:opacity-90",
        destructive: "bg-red text-page hover:opacity-90",

        quiet: "text-ink hover:bg-hover",
      },
      size: {

        xs: "ds-button-xs",

        sm: "ds-button-sm",
        md: "ds-button-md",
        icon: "ds-button-icon",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export type ButtonVariant = NonNullable<VariantProps<typeof buttonVariants>["variant"]>;

export function Button({
  variant,
  size,
  className,
  loading = false,
  disabled,
  children,
  type = "button",
  ...props
}: Omit<ComponentProps<typeof ButtonPrimitive>, "className"> & VariantProps<typeof buttonVariants> & { className?: string; loading?: boolean }) {
  return <ButtonPrimitive {...props} type={type} disabled={disabled || loading} focusableWhenDisabled={loading || props.focusableWhenDisabled} aria-busy={loading || undefined} data-loading={loading || undefined} className={cn(buttonVariants({ variant, size }), className)}>
    <span className={cn("inline-flex items-center justify-center gap-[inherit]", loading && "opacity-0")}>{children}</span>
    {loading && <LoaderCircle aria-hidden="true" className="ds-spinner absolute size-4" />}
  </ButtonPrimitive>;
}
