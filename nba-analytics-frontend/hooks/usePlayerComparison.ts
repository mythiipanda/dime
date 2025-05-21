import { useState, useCallback } from 'react';
import { toast } from "sonner";

interface Player {
  id: number | string; // Can be number or string depending on your API
  full_name: string;
}

interface UsePlayerComparisonOptions {
  selectedPlayers: Player[];
  season: string;
  seasonType: string;
  chartType: string;
}

interface UsePlayerComparisonResult {
  isLoading: boolean;
  comparisonImage: string | null;
  error: string | null;
  generateComparison: (options: UsePlayerComparisonOptions) => Promise<void>;
}

export function usePlayerComparison(): UsePlayerComparisonResult {
  const [isLoading, setIsLoading] = useState(false);
  const [comparisonImage, setComparisonImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generateComparison = useCallback(async (options: UsePlayerComparisonOptions) => {
    const { selectedPlayers, season, seasonType, chartType } = options;

    if (selectedPlayers.length < 2) {
      toast.error('Not enough players. Please select at least 2 players to compare.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setComparisonImage(null); // Clear previous image

    try {
      const params = new URLSearchParams();
      selectedPlayers.forEach(player => {
        params.append('player_names', player.full_name);
      });
      params.append('season', season);
      params.append('seasonType', seasonType);
      params.append('chartType', chartType);
      params.append('outputFormat', 'base64'); // Assuming API expects this

      const response = await fetch(`/api/v1/analyze/players/compare-shots?${params.toString()}`);

      if (!response.ok) {
        let errorData;
        try {
            errorData = await response.json();
        } catch (e) {
            // If response is not JSON, use status text
            throw new Error(`Failed to generate comparison: ${response.statusText} (Status: ${response.status})`);
        }
        throw new Error(errorData.error || `Failed to generate comparison: ${response.statusText} (Status: ${response.status})`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      if (data.image_data) {
        setComparisonImage(data.image_data);
        toast.success("Comparison chart generated successfully!");
      } else {
        throw new Error('No image data returned from the server.');
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred while generating the comparison.';
      console.error('Error generating comparison:', err);
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps 
  }, []); // Dependencies are passed into the function now, so the hook itself doesn't depend on them for memoization.

  // Explicitly return the structure defined in UsePlayerComparisonResult
  return { 
    isLoading, 
    comparisonImage, 
    error, 
    generateComparison: (options: UsePlayerComparisonOptions) => generateComparison(options) 
  };
} 