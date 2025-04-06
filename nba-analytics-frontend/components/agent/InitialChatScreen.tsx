// components/agent/InitialChatScreen.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ZapIcon, MessageSquareIcon, AlertTriangleIcon } from "lucide-react"; // Example icons

interface InitialChatScreenProps {
  onExampleClick: (prompt: string) => void;
}

const examplePrompts = [
  "Compare LeBron James and Michael Jordan's career stats.",
  "Show me Steph Curry's shot chart for the 2023-24 season.",
  "What was the score of the last Lakers vs Celtics game?",
  "Give me the roster for the Denver Nuggets.",
];

const capabilities = [
  "Fetch player stats, game logs, and career info.",
  "Retrieve team rosters and basic information.",
  "Find game results and schedules.",
  "Display player shot charts.",
  "Compare player or team statistics.",
];

const limitations = [
  "Knowledge limited to available NBA API data.",
  "May not understand highly complex or ambiguous queries.",
  "Game finder filters are currently limited.",
  "Analysis capabilities are still under development.",
];

export function InitialChatScreen({ onExampleClick }: InitialChatScreenProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4 lg:p-6">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight">NBA Analytics Agent</h1>
        <p className="text-muted-foreground">Ask me anything about NBA stats!</p>
      </div>

      <div className="grid w-full max-w-4xl grid-cols-1 gap-4 md:grid-cols-3">
        {/* Examples */}
        <div className="flex flex-col items-center gap-2">
          <MessageSquareIcon className="h-6 w-6" />
          <h3 className="font-semibold">Examples</h3>
          <div className="space-y-2 text-center">
            {examplePrompts.map((prompt, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                className="h-auto whitespace-normal text-xs"
                onClick={() => onExampleClick(prompt)}
              >
                "{prompt}"
              </Button>
            ))}
          </div>
        </div>

        {/* Capabilities */}
        <div className="flex flex-col items-center gap-2">
          <ZapIcon className="h-6 w-6" />
          <h3 className="font-semibold">Capabilities</h3>
          <ul className="list-disc space-y-1 pl-5 text-center text-xs text-muted-foreground">
            {capabilities.map((cap, index) => (
              <li key={index}>{cap}</li>
            ))}
          </ul>
        </div>

        {/* Limitations */}
        <div className="flex flex-col items-center gap-2">
          <AlertTriangleIcon className="h-6 w-6" />
          <h3 className="font-semibold">Limitations</h3>
          <ul className="list-disc space-y-1 pl-5 text-center text-xs text-muted-foreground">
            {limitations.map((lim, index) => (
              <li key={index}>{lim}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}