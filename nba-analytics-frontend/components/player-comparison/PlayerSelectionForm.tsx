`use client`;

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, X, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from "sonner";
import { useDebounce } from '@/hooks/use-debounce';
import { PlayerSearchResults } from '@/components/player-search/PlayerSearchResults'; // Assuming this component exists and is correctly typed

// Define a basic Player type, adjust according to your actual data structure
interface Player {
  id: number | string;
  full_name: string;
  // Add other relevant player fields if needed for display or logic
}

interface PlayerSelectionFormProps {
  selectedPlayers: Player[];
  onAddPlayer: (player: Player) => void;
  onRemovePlayer: (playerId: Player['id']) => void;
  maxPlayers?: number;
}

export function PlayerSelectionForm({
  selectedPlayers,
  onAddPlayer,
  onRemovePlayer,
  maxPlayers = 4, // Default max players
}: PlayerSelectionFormProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Player[]>([]); // Ensure this matches PlayerSearchResults expected type
  const debouncedSearchQuery = useDebounce(searchQuery, 300);

  useEffect(() => {
    const searchPlayers = async () => {
      if (debouncedSearchQuery.length < 2) {
        setSearchResults([]);
        return;
      }
      setIsSearching(true);
      try {
        const response = await fetch(`/api/v1/players/search?query=${encodeURIComponent(debouncedSearchQuery)}`);
        if (!response.ok) {
          throw new Error('Failed to search players');
        }
        const data = await response.json();
        setSearchResults(data.players || []);
      } catch (error) {
        console.error('Error searching players:', error);
        toast.error('Failed to search players. Please try again.');
        setSearchResults([]); // Clear results on error
      } finally {
        setIsSearching(false);
      }
    };
    searchPlayers();
  }, [debouncedSearchQuery]);

  const handleAddPlayer = (player: Player) => {
    if (selectedPlayers.length >= maxPlayers) {
      toast.error(`Maximum players reached. You can compare up to ${maxPlayers} players at a time.`);
      return;
    }
    if (selectedPlayers.some(p => p.id === player.id)) {
      toast.error('Player already added. This player is already in the comparison.');
      return;
    }
    onAddPlayer(player);
    setSearchQuery(''); 
    setSearchResults([]);
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="player-search-input">Search Players</Label>
        <div className="relative">
          <Input
            id="player-search-input" // Changed ID to avoid potential global conflicts
            placeholder="Enter player name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {isSearching ? (
            <Loader2 className="h-4 w-4 animate-spin absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          ) : (
            <Search className="h-4 w-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          )}
        </div>

        {searchResults.length > 0 && (
          <div className="border rounded-md max-h-60 overflow-y-auto mt-1 shadow-sm">
            <PlayerSearchResults
              results={searchResults} // Ensure PlayerSearchResults accepts Player[]
              onSelect={handleAddPlayer}
            />
          </div>
        )}
      </div>

      <div className="space-y-2">
        <Label>Selected Players ({selectedPlayers.length}/{maxPlayers})</Label>
        <div className="flex flex-wrap gap-2 min-h-[30px]">
          {selectedPlayers.map(player => (
            <Badge key={player.id} variant="secondary" className="flex items-center gap-1.5 py-1 px-2.5 text-sm">
              {player.full_name}
              <Button
                variant="ghost"
                size="icon"
                className="h-4 w-4 p-0 rounded-full hover:bg-destructive/20 hover:text-destructive"
                onClick={() => onRemovePlayer(player.id)}
                aria-label={`Remove ${player.full_name}`}
              >
                <X className="h-3 w-3" />
              </Button>
            </Badge>
          ))}
          {selectedPlayers.length === 0 && (
            <p className="text-sm text-muted-foreground italic py-1 px-2.5">No players selected</p>
          )}
        </div>
      </div>
    </div>
  );
} 