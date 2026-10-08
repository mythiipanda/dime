"use client";

import type { Form } from "@/lib/dime-data-tonight";

export default function FormChips({ form }: { form: Form }) {
  return (
    <div className="flex gap-1">
      {form.map((r, i) => (
        <span
          key={i}
          className={`flex size-5 items-center justify-center rounded-[5px] text-[10px] font-medium ${
            r === "W" ? "bg-hover-2 text-ink" : "bg-field text-ink-3"
          }`}
        >
          {r}
        </span>
      ))}
    </div>
  );
}
