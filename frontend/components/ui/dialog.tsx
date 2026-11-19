"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export function DialogContent({ className, ...props }: Omit<DialogPrimitive.Popup.Props, "className"> & { className?: string }) {
  return <DialogPrimitive.Portal>
    <DialogPrimitive.Backdrop className="ds-dialog-backdrop" />
    <DialogPrimitive.Viewport className="ds-dialog-viewport">
      <DialogPrimitive.Popup {...props} className={cn("ds-dialog", className)} />
    </DialogPrimitive.Viewport>
  </DialogPrimitive.Portal>;
}
