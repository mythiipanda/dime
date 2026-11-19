"use client";

import * as FormPrimitive from "@radix-ui/react-form";
import { forwardRef, type InputHTMLAttributes, type ReactElement, type ReactNode } from "react";
import { cn } from "../../lib/utils";

export const TextField = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextField({ className, ...props }, ref) {
  return <input ref={ref} className={cn("ds-field", className)} {...props} />;
});

export const Form = FormPrimitive.Root;

export function FormField({ name, label, description, error, children }: {
  name: string;
  label: ReactNode;
  description?: ReactNode;
  error?: string;
  children: ReactElement<InputHTMLAttributes<HTMLInputElement>>;
}) {
  return <FormPrimitive.Field name={name} className="ds-form-field" serverInvalid={Boolean(error)}>
    <FormPrimitive.Label htmlFor={children.props.id} className="ds-field-label">{label}</FormPrimitive.Label>
    <FormPrimitive.Control asChild id={children.props.id}>{children}</FormPrimitive.Control>
    {description && <FormPrimitive.Message className="ds-field-description">{description}</FormPrimitive.Message>}
    {error && <FormPrimitive.Message className="ds-field-error" role="alert">{error}</FormPrimitive.Message>}
  </FormPrimitive.Field>;
}
