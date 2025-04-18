import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

export function ProTipAlert() {
  return (
    <Alert>
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Pro Tip</AlertTitle>
      <AlertDescription>
        Use natural language to ask questions about any NBA player, team, or game. Our AI will help you find the insights you need.
      </AlertDescription>
    </Alert>
  );
} 