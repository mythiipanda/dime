"use client";

import { Toaster } from "sonner";

export default function DimeToaster() {
  return (
    <Toaster
      position="bottom-right"
      gap={8}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast: "dime-toast",
          title: "dime-toast-title",
          description: "dime-toast-description",
        },
      }}
    />
  );
}
