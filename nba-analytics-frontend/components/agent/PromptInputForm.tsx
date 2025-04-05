// components/agent/PromptInputForm.tsx
import * as React from 'react';
import { Command, CommandInput } from "@/components/ui/command";
import { Button } from "@/components/ui/button";
import { SendIcon } from "lucide-react";

interface PromptInputFormProps {
  inputValue: string;
  onInputChange: (value: string) => void;
  onSubmit: (e?: React.FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;
}

export function PromptInputForm({
  inputValue,
  onInputChange,
  onSubmit,
  isLoading,
}: PromptInputFormProps) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col flex-1 gap-2">
      <Command className="rounded-lg border shadow-md flex-1">
        <CommandInput
          placeholder="Type your NBA query here..."
          value={inputValue}
          onValueChange={onInputChange}
          disabled={isLoading} // Disable input while loading
        />
        {/* We can add CommandList suggestions later */}
        {/* <CommandList> <CommandEmpty>No results.</CommandEmpty> ... </CommandList> */}
      </Command>
      <Button type="submit" className="mt-auto" disabled={isLoading || !inputValue.trim()}> {/* Disable if loading or input empty */}
        <SendIcon className="mr-2 h-4 w-4" /> Send Prompt
      </Button>
    </form>
  );
}