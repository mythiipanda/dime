"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { forwardRef, type ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export const DialogContent = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof DialogPrimitive.Content>>(function DialogContent({ className, ...props }, ref) {
  return <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="ds-dialog-backdrop ds-dialog-viewport">
      <DialogPrimitive.Content {...props} ref={ref} className={cn("ds-dialog", className)} />
    </DialogPrimitive.Overlay>
  </DialogPrimitive.Portal>;
});
