"use client";

import { useState, useCallback, useRef, useEffect } from 'react';

export interface ResearchSSEState {
  reportContent: string | null;
  followUpSuggestions: string[];
  isLoading: boolean;
  error: string | null;
}

interface UseResearchSSEProps {
  initialState?: Partial<ResearchSSEState>;
}

export function useResearchSSE({ initialState }: UseResearchSSEProps = {}) {
  const [sseState, setSseState] = useState<ResearchSSEState>({
    reportContent: initialState?.reportContent ?? null,
    followUpSuggestions: initialState?.followUpSuggestions ?? [],
    isLoading: initialState?.isLoading ?? false,
    error: initialState?.error ?? null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const startResearchStream = useCallback(async (topic: string, selectedSections: string[]) => {
    if (eventSourceRef.current) {
      console.log("Closing previous EventSource connection.");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setSseState({
      reportContent: '', // Reset content for new stream
      followUpSuggestions: [],
      isLoading: true,
      error: null,
    });

    try {
      const queryParams = new URLSearchParams({
        topic: topic,
        selected_sections: JSON.stringify(selectedSections),
      });
      const eventSource = new EventSource(`/api/v1/research/?${queryParams.toString()}`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log("SSE connection opened.");
        // Clear error on successful (re)connection if one existed from previous attempt
        setSseState(prev => prev.error ? {...prev, error: null} : prev);
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'suggestions') {
            setSseState((prev) => ({ ...prev, followUpSuggestions: data.suggestions || [], isLoading: false }));
            console.log("Follow-up suggestions received:", data.suggestions);
            if (eventSourceRef.current) eventSourceRef.current.close(); 
          } else if (data.event === 'error') {
            console.error("SSE Error:", data.content);
            setSseState((prev) => ({ ...prev, error: data.content || 'An unknown error occurred during research.', isLoading: false }));
            if (eventSourceRef.current) eventSourceRef.current.close();
          } else if (data.event === 'final_content_end') {
            console.log("SSE stream indicated end of content.");
            setSseState((prev) => ({ ...prev, isLoading: false }));
            if (eventSourceRef.current) eventSourceRef.current.close();
          } else {
            const contentChunk = data.content;
            if (typeof contentChunk === 'string') {
              setSseState((prev) => ({ ...prev, reportContent: (prev.reportContent || '') + contentChunk }));
            }
          }
        } catch (e) {
          console.error('Error parsing SSE message:', e, 'Raw data:', event.data);
          setSseState((prev) => ({ ...prev, error: 'Error processing research update.', isLoading: false }));
          if (eventSourceRef.current) eventSourceRef.current.close();
        }
      };

      eventSource.onerror = (errorEvent) => {
        console.error('EventSource failed:', errorEvent);
        setSseState((prev) => ({
          ...prev,
          error: 'Connection to research service failed. Please try again.',
          isLoading: false,
        }));
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };

    } catch (err) {
      console.error('Failed to initialize EventSource:', err);
      setSseState({
        reportContent: null,
        followUpSuggestions: [],
        isLoading: false,
        error: 'Failed to start research stream.',
      });
    }
  }, []); // Dependencies: topic and selectedSections are passed as args, so hook itself doesn't depend on them from parent scope

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        console.log("Closing EventSource connection on unmount (from useResearchSSE).");
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  return { ...sseState, startResearchStream };
} 