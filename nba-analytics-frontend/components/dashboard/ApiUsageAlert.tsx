import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

export function ApiUsageAlert() {
  return (
    <Alert>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Heads up!</AlertTitle>
      <AlertDescription>
        NBA API usage limits may apply. Monitor your requests.
      </AlertDescription>
    </Alert>
  );
} 