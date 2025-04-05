// components/agent/ErrorDisplay.tsx
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { TerminalIcon } from "lucide-react";

interface ErrorDisplayProps {
  error: string | null;
}

export function ErrorDisplay({ error }: ErrorDisplayProps) {
  if (!error) {
    return null; // Don't render if no error
  }

  return (
    <Alert variant="destructive">
      <TerminalIcon className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {error}
      </AlertDescription>
    </Alert>
  );
}