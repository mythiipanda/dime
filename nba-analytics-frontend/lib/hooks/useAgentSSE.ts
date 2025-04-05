// lib/hooks/useAgentSSE.ts
import { useState, useRef, useCallback } from 'react';

interface UseAgentSSEProps {
  apiUrl: string; // Make API URL configurable
}

// Define ChatMessage interface
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AgentSSEState {
  isLoading: boolean;
  // response: string | null; // Removed: Replaced by chatHistory
  error: string | null;
  progress: string[];
  chatHistory: ChatMessage[]; // Added chat history
  resultData: any; // Keep simple for now, refine later
}

export function useAgentSSE({ apiUrl }: UseAgentSSEProps) {
  const [state, setState] = useState<AgentSSEState>({
    isLoading: false,
    // response: null, // Removed
    error: null,
    progress: [],
    chatHistory: [], // Initialize chat history
    resultData: null,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    console.log("Submitting prompt via hook:", prompt);
    // Add user prompt to history immediately
    const userMessage: ChatMessage = { role: 'user', content: prompt };
    setState(prev => ({
      ...prev,
      isLoading: true,
      // response: null, // Removed
      error: null,
      progress: ["Connecting to agent..."],
      chatHistory: [...prev.chatHistory, userMessage], // Add user message
      resultData: null,
    }));

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
        } else if (data.type === 'agent_step') {
          // Handle streaming content for chat history
          setState(prev => {
            const lastMessage = prev.chatHistory[prev.chatHistory.length - 1];
            let updatedHistory: ChatMessage[];
            if (lastMessage?.role === 'assistant') {
              // Append to last assistant message
              updatedHistory = [
                ...prev.chatHistory.slice(0, -1),
                { ...lastMessage, content: lastMessage.content + data.message }
              ];
            } else {
              // Add new assistant message
              updatedHistory = [...prev.chatHistory, { role: 'assistant', content: data.message }];
            }
            return { ...prev, chatHistory: updatedHistory };
          });
        } else if (data.type === 'status' || data.type === 'tool_start' || data.type === 'tool_end' || data.type === 'thinking' || data.type === 'tool_call' || data.type === 'reasoning') {
           // Update progress for other events
           const progressMessage = data.message || `Processing: ${data.type}`;
           setState(prev => ({ ...prev, progress: [...prev.progress, progressMessage] }));
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
          const finalContent = data.content;
          // Ensure final content is added/appended correctly
          setState(prev => {
             const lastMessage = prev.chatHistory[prev.chatHistory.length - 1];
             let updatedHistory: ChatMessage[];
             // Check if the last message was already the start of this response
             if (lastMessage?.role === 'assistant') {
                 // If the final content is exactly what we already have, do nothing extra
                 // Otherwise, replace or append (depending on streaming implementation)
                 // For simplicity now, assume final event might contain the full message or just the last chunk
                 // Let's ensure it's added if the last message isn't already it.
                 // A more robust solution might involve message IDs if the backend provides them.
                 // Current logic: Add as new message if last wasn't assistant, otherwise assume it was streamed.
                 if (lastMessage.content !== finalContent) {
                    // If last message exists and is assistant, update it (safer than adding duplicate)
                    updatedHistory = [
                       ...prev.chatHistory.slice(0, -1),
                       { ...lastMessage, content: finalContent } // Assume final contains full response
                    ];
                 } else {
                    updatedHistory = prev.chatHistory; // Already streamed correctly
                 }
             } else {
                 // Add final response as a new message
                 updatedHistory = [...prev.chatHistory, { role: 'assistant', content: finalContent }];
             }

             return {
               ...prev,
               // response: null, // Removed
               chatHistory: updatedHistory,
               progress: [...prev.progress, "Final response received."],
               isLoading: false,
               // TODO: Parse final content for structured data and set resultData
               // resultData: parseStructuredData(finalContent),
             };
          });

        } else {
           // Handle cases where 'final' event doesn't have expected structure
           setState(prev => ({
             ...prev,
             // response: null, // Removed
             // Add error message to chat?
             error: "Received final event with unexpected structure.",
             progress: [...prev.progress, "Final event received (unexpected structure)."],
             isLoading: false,
           }));
        }
      } catch (e) {
        console.error("Failed to parse final SSE data (hook):", e);
        setState(prev => ({
          ...prev,
          // response: null, // Removed
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
      // Check if the connection is still expected to be open
      if (eventSourceRef.current && state.isLoading && !state.error) { // Check isLoading instead of response
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

  }, [apiUrl, state.isLoading, state.error]); // Update dependencies

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

  return { ...state, submitPrompt, closeConnection }; // chatHistory is now part of state
}