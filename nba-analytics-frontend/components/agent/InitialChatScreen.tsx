// components/agent/InitialChatScreen.tsx
// Removed unused Card components
import { Button } from "@/components/ui/button";
import { ZapIcon, MessageSquareIcon, AlertTriangleIcon } from "lucide-react"; // Example icons

interface InitialChatScreenProps {
  onExampleClick: (prompt: string) => void;
}

const examplePrompts = [
  "What awards has LeBron James won?",
  "Show the box score for the last Lakers game.", // Requires find_games then get_boxscore_traditional
  "What are the current NBA standings?",
  "Who won the games played yesterday?",
  "Who leads the league in points per game this season?",
  "Give me the play-by-play for the Celtics vs Knicks game on 2024-12-25.", // Requires find_games then get_playbyplay
  "Who was the first pick in the 2003 NBA draft?",
  "Get Michael Jordan's career stats.",
];

const capabilities = [
  "Fetch player stats, game logs, career info, and awards.",
  "Retrieve team rosters and basic information.",
  "Find game results, schedules, box scores, and play-by-play.",
  "Get current league standings and league leaders.",
  "Look up historical draft picks.",
  "Analyze and compare retrieved statistics.",
];

const limitations = [
  "Knowledge limited to available NBA stats API data.",
  "May not understand highly complex or ambiguous queries.",
  "Analysis is based solely on retrieved data.",
  "Does not have real-time injury updates or live game commentary beyond scores/PBP.",
  "Some advanced stats (e.g., player tracking details beyond box scores) may require specific tools not yet implemented.",
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
                &quot;{prompt}&quot; {/* Use &quot; for quotes */}
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