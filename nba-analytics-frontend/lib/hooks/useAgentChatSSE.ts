// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string;
}

// Define ChatMessage interface (Exported from this file now)
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

// Define a type for structured results (mirroring ResultsDisplay)
interface StructuredResult {
  type: 'table' | 'chart' | string;
  data?: Record<string, unknown>[]; // Use unknown instead of any
}

interface AgentChatSSEState {
  isLoading: boolean;
  error: string | null;
  progress: string[];
  chatHistory: ChatMessage[]; // Manages chat history
  resultData: StructuredResult | null; // Use specific type
}

export function useAgentChatSSE({ apiUrl }: UseAgentChatSSEProps) {
  const [state, setState] = useState<AgentChatSSEState>({
    isLoading: false,
    error: null,
    progress: [],
    chatHistory: [], // Initialize chat history
    resultData: null,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    console.log("Submitting prompt via Chat hook:", prompt);
    const userMessage: ChatMessage = { role: 'user', content: prompt };
    // Add user message and reset other relevant state parts
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      progress: ["Connecting to agent..."],
      chatHistory: [...prev.chatHistory, userMessage],
      resultData: null,
    }));

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Construct the full URL including the /api prefix
    const fullApiUrl = `${apiUrl}/api/ask_team?prompt=${encodeURIComponent(prompt)}`;
    const eventSource = new EventSource(fullApiUrl);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      console.log("SSE Message (Chat hook):", event.data);
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'error') {
          console.error("Received error from backend stream (Chat hook):", data.message);
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
              // Ensure a new array reference is created by copying
              const historyCopy = [...prev.chatHistory];
              historyCopy[historyCopy.length - 1] = { ...lastMessage, content: lastMessage.content + data.message };
              updatedHistory = historyCopy;
            } else {
              // Ensure a new array reference is created
              updatedHistory = [...prev.chatHistory, { role: 'assistant', content: data.message }];
            }
            return { ...prev, chatHistory: updatedHistory };
          });
        } else if (data.type === 'status' || data.type === 'tool_start' || data.type === 'tool_end' || data.type === 'thinking' || data.type === 'tool_call' || data.type === 'reasoning') {
           const progressMessage = data.message || `Processing: ${data.type}`;
           setState(prev => ({ ...prev, progress: [...prev.progress, progressMessage] }));
        }
      } catch (e) {
        console.error("Failed to parse SSE data (Chat hook):", e);
        setState(prev => ({ ...prev, progress: [...prev.progress, event.data] }));
      }
    };

    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log("SSE Final Event (Chat hook):", event.data);
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'final_response') {
          const finalContent = data.content;
          // Calculate final history *before* calling setState
          // Use a function form of setState to get the most recent state
          setState(prev => {
              const lastMessage = prev.chatHistory[prev.chatHistory.length - 1];
              let finalHistory: ChatMessage[];
              if (lastMessage?.role === 'assistant') {
                  // Ensure a new array reference is created by copying
                  const historyCopy = [...prev.chatHistory];
                  historyCopy[historyCopy.length - 1] = { ...lastMessage, content: finalContent };
                  finalHistory = historyCopy;
              } else {
                  // Ensure a new array reference is created
                  finalHistory = [...prev.chatHistory, { role: 'assistant', content: finalContent }];
              }
              // Update state with the calculated final history
              return {
                ...prev,
                chatHistory: finalHistory,
                progress: [...prev.progress, "Final response received."],
                isLoading: false,
                // resultData: parseStructuredData(finalContent), // TODO
              };
          });
        } else {
           setState(prev => ({
             ...prev,
             error: "Received final event with unexpected structure.",
             progress: [...prev.progress, "Final event received (unexpected structure)."],
             isLoading: false,
           }));
        }
      } catch (e) {
        console.error("Failed to parse final SSE data (Chat hook):", e);
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
      console.error("EventSource failed (Chat hook):", err);
      if (eventSourceRef.current && state.isLoading && !state.error) {
         setState(prev => ({
           ...prev,
           error: "Connection to agent lost or failed.",
           progress: [...prev.progress, "Error: Connection lost."],
           isLoading: false,
         }));
         eventSourceRef.current = null;
      } else {
         console.log("EventSource closed, likely intentionally (Chat hook).");
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  // Include chatHistory in dependency array
  }, [apiUrl, state.isLoading, state.error]); // Removed state.chatHistory

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log("Manually closing SSE connection (Chat hook).");
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Return state values individually
  return {
    isLoading: state.isLoading,
    error: state.error,
    progress: state.progress,
    chatHistory: state.chatHistory,
    resultData: state.resultData,
    submitPrompt,
    closeConnection
  };
}