"use client";

import { useState, useCallback } from 'react';

export type ChartDataType = 'scatter' | 'heatmap' | 'hexbin' | 'animated' | 'frequency' | 'distance';

interface UseAdvancedShotChartDataReturn {
  isLoading: boolean;
  error: string | null;
  chartImage: string | null;
  chartType: ChartDataType | null;
  fetchAdvancedShotChart: (playerName: string, season?: string, seasonType?: string, requestedChartType?: ChartDataType, outputFormat?: string) => Promise<void>;
  clearError: () => void;
}

export function useAdvancedShotChartData(): UseAdvancedShotChartDataReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chartImage, setChartImage] = useState<string | null>(null);
  const [chartType, setChartType] = useState<ChartDataType | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const fetchAdvancedShotChart = useCallback(async (
    playerName: string, 
    season?: string, 
    seasonType?: string, 
    requestedChartType: ChartDataType = 'scatter',
    outputFormat: string = 'base64'
  ) => {
    if (!playerName) {
      setError("Player name is required to fetch shot chart.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setChartImage(null); // Clear previous image

    try {
      const params = new URLSearchParams();
      if (season) params.append('season', season);
      if (seasonType) params.append('seasonType', seasonType);
      params.append('chartType', requestedChartType);
      params.append('outputFormat', outputFormat);

      const url = `/api/v1/analyze/player/${encodeURIComponent(playerName)}/advanced-shotchart?${params.toString()}`;
      const response = await fetch(url);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch (e) {
          // If parsing JSON fails, use status text
          throw new Error(`Failed to fetch advanced shot chart: ${response.status} ${response.statusText}`);
        }
        throw new Error(errorData?.detail || errorData?.error || `Failed to fetch advanced shot chart: ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      if (data.image_data) {
        setChartImage(data.image_data);
      } else if (data.animation_data) { // Assuming animation data might also be base64 or URL
        setChartImage(data.animation_data);
      } else {
        throw new Error('No image data returned from the server for the shot chart.');
      }
      
      setChartType(data.chart_type as ChartDataType || requestedChartType);

    } catch (err) {
      console.error('Error fetching advanced shot chart:', err);
      const message = err instanceof Error ? err.message : 'An unknown error occurred while fetching the shot chart.';
      setError(message);
      setChartImage(null); // Ensure no stale image is shown on error
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    isLoading,
    error,
    chartImage,
    chartType,
    fetchAdvancedShotChart,
    clearError,
  };
} 