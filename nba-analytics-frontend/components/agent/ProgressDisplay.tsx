// components/agent/ProgressDisplay.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ProgressDisplayProps {
  progressSteps: string[];
}

export function ProgressDisplay({ progressSteps }: ProgressDisplayProps) {
  if (progressSteps.length === 0) {
    return null; // Don't render if no progress
  }

  return (
    <Card className="mb-4 bg-secondary/50">
      <CardHeader><CardTitle className="text-sm">Progress</CardTitle></CardHeader>
      <CardContent>
        <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1"> {/* Typography: text-sm */}
          {progressSteps.map((step, index) => <li key={index}>{step}</li>)}
        </ul>
      </CardContent>
    </Card>
  );
}