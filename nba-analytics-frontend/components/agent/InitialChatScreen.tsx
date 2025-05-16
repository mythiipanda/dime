"use client";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/layout/Logo";
import { ZapIcon, AlertTriangleIcon, MessageSquareTextIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// Animation delay constants
const INITIAL_SCREEN_BASE_DELAY_MS = 300;
const PROMPT_BUTTON_STAGGER_DELAY_MS = 75;

const SIMPLE_EXAMPLE_PROMPTS = [
  { text: "Identify the player with the most triple-doubles this season. Then, for that player, show their average stats in the games where they achieved a triple-double.", icon: <MessageSquareTextIcon className="h-4 w-4 mr-2 shrink-0" /> },
  { text: "Find a recent game where a team won by more than 10 points. Provide a summary of the key player performances and the advanced box score for that game.", icon: <MessageSquareTextIcon className="h-4 w-4 mr-2 shrink-0" /> },
  { text: "Generate a detailed offensive and defensive report for Victor Wembanyama.", icon: <MessageSquareTextIcon className="h-4 w-4 mr-2 shrink-0" /> },
  { text: "Who were the top 5 picks in the 2011 NBA Draft, and what have their career outcomes been generally?", icon: <MessageSquareTextIcon className="h-4 w-4 mr-2 shrink-0" /> }
];

interface InitialChatScreenProps {
  onExampleClick: (prompt: string) => void;
}

export function InitialChatScreen({ onExampleClick }: InitialChatScreenProps) {
  return (
    <div className={cn(
      "flex flex-col items-center justify-center text-center space-y-6 sm:space-y-8",
      // "animate-in fade-in-0 duration-500" // Animation disabled
    )}>
      {/* <div className="animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-100"> */}
      <div> {/* Animation disabled */}
        <Logo iconSize={10} textSize="xl" />
      </div>

      {/* <p className="text-base sm:text-lg text-muted-foreground max-w-md md:max-w-lg animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-200"> */}
      <p className="text-base sm:text-lg text-muted-foreground max-w-md md:max-w-lg"> {/* Animation disabled */}
        Your AI-powered NBA analytics companion. Ask me anything about players, teams, games, and stats.
      </p>

      {/* <div className="w-full max-w-lg md:max-w-xl space-y-3 animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-300"> */}
      <div className="w-full max-w-lg md:max-w-xl space-y-3"> {/* Animation disabled */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {SIMPLE_EXAMPLE_PROMPTS.map((promptItem, index) => (
            <Button
              key={index}
              variant="outline"
              className={cn(
                "text-left justify-start h-auto py-2.5 px-3.5 text-sm font-normal leading-snug whitespace-normal",
                "hover:bg-accent/70 dark:hover:bg-accent/50 transition-all hover:scale-[1.02] active:scale-[0.98]",
                // "animate-in fade-in-0 zoom-in-95 duration-300" // Animation disabled
              )}
              // style={{ animationDelay: `${INITIAL_SCREEN_BASE_DELAY_MS + index * PROMPT_BUTTON_STAGGER_DELAY_MS}ms` }} // Animation disabled
              onClick={() => onExampleClick(promptItem.text)}
            >
              {promptItem.icon}
              <span>{promptItem.text}</span>
            </Button>
          ))}
        </div>
      </div>
      
      {/* <div className="pt-4 sm:pt-6 space-y-3 text-xs text-muted-foreground max-w-md md:max-w-lg animate-in fade-in-0 slide-in-from-bottom-4 duration-500 delay-400"> */}
      <div className="pt-4 sm:pt-6 space-y-3 text-xs text-muted-foreground max-w-md md:max-w-lg"> {/* Animation disabled */}
        <div className="flex items-center justify-center gap-1.5">
          <ZapIcon className="h-3.5 w-3.5 text-sky-500 shrink-0" /> 
          <span>Capabilities: Real-time stats, player comparisons, game analysis.</span>
        </div>
        <div className="flex items-center justify-center gap-1.5">
          <AlertTriangleIcon className="h-3.5 w-3.5 text-amber-500 shrink-0" /> 
          <span>Limitations: May occasionally produce inaccuracies. Verify critical info.</span>
        </div>
      </div>
    </div>
  );
}