// components/agent/PromptInputForm.tsx
import * as React from 'react';
import { Textarea } from "@/components/ui/textarea"; // Import Textarea
import { Button } from "@/components/ui/button";
import { SendIcon, CornerDownLeftIcon } from "lucide-react"; // Add CornerDownLeftIcon

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
  const textAreaRef = React.useRef<HTMLTextAreaElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault(); // Prevent newline on Enter
      if (!isLoading && inputValue.trim()) {
        onSubmit(); // Trigger submit
      }
    }
    // Allow Shift+Enter for newlines (default behavior)
  };

  // Adjust textarea height dynamically (optional but nice)
  React.useEffect(() => {
    if (textAreaRef.current) {
      textAreaRef.current.style.height = 'auto'; // Reset height
      textAreaRef.current.style.height = `${textAreaRef.current.scrollHeight}px`; // Set to scroll height
    }
  }, [inputValue]);


  return (
    <form onSubmit={onSubmit} className="relative overflow-hidden rounded-lg border bg-background focus-within:ring-1 focus-within:ring-ring">
       <Textarea
          ref={textAreaRef}
          placeholder="Type your NBA query here... (Shift+Enter for newline)"
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)} // Use standard onChange
          onKeyDown={handleKeyDown} // Add keydown handler
          disabled={isLoading}
          rows={1} // Start with 1 row
          className="min-h-[60px] w-full resize-none border-0 p-3 shadow-none focus-visible:ring-0"
        />
      <div className="flex items-center p-3 pt-0">
         {/* Optional: Add other controls like clear button here */}
         <span className="ml-auto text-xs text-muted-foreground">
           Enter to send, Shift+Enter for newline
         </span>
        <Button type="submit" size="sm" className="ml-2" disabled={isLoading || !inputValue.trim()}>
          <SendIcon className="h-4 w-4" />
          <span className="sr-only">Send</span> {/* Accessibility */}
        </Button>
      </div>
    </form>
  );
}