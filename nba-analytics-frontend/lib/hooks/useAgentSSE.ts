// lib/hooks/useAgentSSE.ts
import { useState, useRef, useCallback } from 'react';

interface UseAgentSSEProps {
  apiUrl: string; // Make API URL configurable
}

interface AgentSSEState {
  isLoading: boolean;
  response: string | null;
  error: string | null;
  progress: string[];
  resultData: any; // Keep simple for now, refine later
}

export function useAgentSSE({ apiUrl }: UseAgentSSEProps) {
  const [state, setState] = useState<AgentSSEState>({
    isLoading: false,
    response: null,
    error: null,
    progress: [],
    resultData: null,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    console.log("Submitting prompt via hook:", prompt);
    setState({
      isLoading: true,
      response: null,
      error: null,
      progress: ["Connecting to agent..."],
      resultData: null,
    });

    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create new EventSource connection
    const fullApiUrl = `${apiUrl}?prompt=${encodeURIComponent(prompt)}`;
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
        } else if (data.type === 'status' || data.type === 'tool_start' || data.type === 'tool_end' || data.type === 'agent_step') {
          setState(prev => ({ ...prev, progress: [...prev.progress, data.message] }));
        }
        // Handle other structured data types if needed
      } catch (e) {
        console.error("Failed to parse SSE data (hook):", e);
        // Treat as plain text message if parsing fails
        setState(prev => ({ ...prev, progress: [...prev.progress, event.data] }));
      }
    };

    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log("SSE Final Event (hook):", event.data);
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'final_response') {
          // TODO: Parse final content for structured data and set resultData
          setState(prev => ({
            ...prev,
            response: data.content,
            progress: [...prev.progress, "Final response received."],
            isLoading: false,
          }));
        } else {
           // Handle cases where 'final' event doesn't have expected structure
           setState(prev => ({
             ...prev,
             response: "Received final event with unexpected structure.",
             progress: [...prev.progress, "Final event received (unexpected structure)."],
             isLoading: false,
           }));
        }
      } catch (e) {
        console.error("Failed to parse final SSE data (hook):", e);
        setState(prev => ({
          ...prev,
          response: "Received final event, but failed to parse content.",
          progress: [...prev.progress, "Error parsing final event."],
          isLoading: false,
        }));
      }
      eventSource.close();
      eventSourceRef.current = null;
    });

    eventSource.onerror = (err) => {
      console.error("EventSource failed (hook):", err);
      // Check if the connection is still expected to be open
      if (eventSourceRef.current && !state.response && !state.error) {
         console.error("EventSource connection error or closed unexpectedly (hook).");
         setState(prev => ({
           ...prev,
           error: "Connection to agent lost or failed.",
           progress: [...prev.progress, "Error: Connection lost."],
           isLoading: false,
         }));
         eventSourceRef.current = null; // Ensure ref is cleared
      } else {
         console.log("EventSource closed, likely intentionally (hook).");
      }
      // Ensure closure regardless
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

  }, [apiUrl, state.isLoading, state.response, state.error]); // Add dependencies

  // Function to manually close connection if needed (e.g., on component unmount)
  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log("Manually closing SSE connection (hook).");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      // Optionally reset state if needed when manually closing
      // setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  return { ...state, submitPrompt, closeConnection };
}