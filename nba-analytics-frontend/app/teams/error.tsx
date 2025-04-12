'use client';

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCcw } from "lucide-react";

export default function TeamsError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="flex-1 p-4 md:p-8 pt-6 flex items-center justify-center">
      <Alert variant="destructive" className="max-w-2xl">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error Loading Teams</AlertTitle>
        <AlertDescription className="mt-2 flex flex-col gap-3">
          <p>
            {error.message || "An error occurred while loading team data. Please try again later."}
          </p>
          <Button
            variant="destructive"
            className="w-fit"
            onClick={reset}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  );
}