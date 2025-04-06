// lib/hooks/useAgentSSE.ts
import { useState, useRef, useCallback } from 'react';

interface UseAgentSSEProps {
  apiUrl: string;
}

// Define a type for structured results (mirroring ResultsDisplay)
interface StructuredResult {
  type: 'table' | 'chart' | string;
  data?: Record<string, unknown>[]; // Use unknown instead of any
}

// Updated state interface
interface AgentSSEState {
  isLoading: boolean;
  response: string | null; // Keep single response
  error: string | null;
  progress: string[];
  resultData: StructuredResult | null; // Use specific type
}

export function useAgentSSE({ apiUrl }: UseAgentSSEProps) {
  const [state, setState] = useState<AgentSSEState>({
    isLoading: false,
    response: null, // Initialize response
    error: null,
    progress: [],
    resultData: null,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    console.log("Submitting prompt via hook:", prompt);
    // Reset state for new request
    setState({
      isLoading: true,
      response: null,
      error: null,
      progress: ["Connecting to agent..."],
      resultData: null,
    });

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Construct the full URL including the /api prefix
    // Construct URL based on environment (apiUrl is base URL)
    const baseUrl = apiUrl; // Assuming apiUrl is the base backend URL
    const endpointPath = baseUrl.includes('localhost') ? '/ask_team' : '/api/ask_team';
    const fullApiUrl = `${baseUrl}${endpointPath}?prompt=${encodeURIComponent(prompt)}`;
    console.log(`SSE connecting to: ${fullApiUrl}`); // Add log
    const eventSource = new EventSource(fullApiUrl);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      console.log("SSE Message (hook):", event.data);
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'error') {
          console.error("Received error from backend stream (hook):", data.message);
          setState(prev => ({
            ...prev,
            error: data.message || "Unknown error from backend stream.",
            progress: [...prev.progress, `Error: ${data.message || "Unknown"}`],
            isLoading: false,
          }));
          eventSourceRef.current?.close();
          eventSourceRef.current = null;
        } else if (data.type === 'status' || data.type === 'tool_start' || data.type === 'tool_end' || data.type === 'agent_step' || data.type === 'thinking' || data.type === 'tool_call' || data.type === 'reasoning') {
           // Only update progress, not response
           const progressMessage = data.message || `Processing: ${data.type}`;
           setState(prev => ({ ...prev, progress: [...prev.progress, progressMessage] }));
        }
      } catch (e) {
        console.error("Failed to parse SSE data (hook):", e);
        setState(prev => ({ ...prev, progress: [...prev.progress, event.data] }));
      }
    };

    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log("SSE Final Event (hook):", event.data);
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'final_response') {
          // Set the single final response
          setState(prev => ({
            ...prev,
            response: data.content, // Set final response string
            progress: [...prev.progress, "Final response received."],
            isLoading: false,
            // TODO: Parse final content for structured data
            // resultData: parseStructuredData(data.content),
          }));
        } else {
           setState(prev => ({
             ...prev,
             error: "Received final event with unexpected structure.",
             progress: [...prev.progress, "Final event received (unexpected structure)."],
             isLoading: false,
           }));
        }
      } catch (e) {
        console.error("Failed to parse final SSE data (hook):", e);
        setState(prev => ({
          ...prev,
          error: "Failed to parse final event content.",
          progress: [...prev.progress, "Error parsing final event."],
          isLoading: false,
        }));
      }
      eventSource.close();
      eventSourceRef.current = null;
    });

    eventSource.onerror = (err) => {
      console.error("EventSource failed (hook):", err);
      if (eventSourceRef.current && state.isLoading && !state.error) {
         setState(prev => ({
           ...prev,
           error: "Connection to agent lost or failed.",
           progress: [...prev.progress, "Error: Connection lost."],
           isLoading: false,
         }));
         eventSourceRef.current = null;
      } else {
         console.log("EventSource closed, likely intentionally (hook).");
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  // Original dependencies (without chatHistory)
  }, [apiUrl, state.isLoading, state.error]);

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log("Manually closing SSE connection (hook).");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Return state including response
  return { ...state, submitPrompt, closeConnection };
}