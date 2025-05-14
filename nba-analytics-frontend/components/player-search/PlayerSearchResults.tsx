import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Plus } from "lucide-react";

interface PlayerSearchResultsProps {
  results: any[];
  onSelect: (player: any) => void;
}

export function PlayerSearchResults({ results, onSelect }: PlayerSearchResultsProps) {
  if (results.length === 0) {
    return null;
  }

  return (
    <div className="divide-y">
      {results.map((player) => (
        <div
          key={player.id}
          className="flex items-center justify-between p-2 hover:bg-accent/50"
        >
          <div className="flex items-center gap-2">
            <Avatar className="h-8 w-8">
              <AvatarImage
                src={`https://cdn.nba.com/headshots/nba/latest/260x190/${player.id}.png`}
                alt={player.full_name}
              />
              <AvatarFallback>
                {player.full_name
                  .split(" ")
                  .map((n: string) => n[0])
                  .join("")}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium">{player.full_name}</p>
              <p className="text-xs text-muted-foreground">
                {player.team_name || (player.is_active ? "Active" : "Inactive")}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onSelect(player)}
            title="Add to comparison"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}
