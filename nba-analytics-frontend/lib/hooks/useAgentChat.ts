// lib/hooks/useAgentChat.ts
import { useState, useCallback } from 'react';

// Define ChatMessage interface (remains the same)
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AgentChatState {
  isLoading: boolean;
  error: string | null;
  chatHistory: ChatMessage[];
}

// Note: apiUrl prop is kept for consistency but might not be strictly needed
// if the relative path `/api/ask_team` is always used with the proxy.
interface UseAgentChatProps {
  apiUrl: string; // Base API URL (e.g., http://localhost:8000) - used by proxy
}

export function useAgentChat({ apiUrl }: UseAgentChatProps) {
  const [state, setState] = useState<AgentChatState>({
    isLoading: false,
    error: null,
    chatHistory: [],
  });

  const submitPrompt = useCallback(async (prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    console.log("Submitting prompt via Chat hook (Fetch):", prompt);
    const userMessage: ChatMessage = { role: 'user', content: prompt };

    // Reset state for new request, add user message
    setState({
      isLoading: true,
      error: null,
      chatHistory: [userMessage], // Start new history with user message
    });

    try {
      // Use relative path - Next.js rewrite handles proxying
      const fullApiUrl = `http://localhost:8000/ask_team?prompt=${encodeURIComponent(prompt)}`;
      console.log(`Fetching from: ${fullApiUrl}`);

      const response = await fetch(fullApiUrl, {
          method: 'GET', // Changed to GET as per backend update
          headers: {
              'Accept': 'application/json',
          },
          // Add a timeout (e.g., 60 seconds = 60000 ms)
          // Note: Standard fetch doesn't have a built-in timeout like this.
          // We'd need AbortController for a real timeout.
          // For now, we rely on server/browser default timeouts.
      });

      console.log(`Response status: ${response.status}`);

      if (!response.ok) {
        let errorBody = "Unknown error";
        try {
            // Try to parse error response from backend
            const errorData = await response.json();
            errorBody = errorData.detail || errorData.message || JSON.stringify(errorData);
        } catch (parseError) {
            // If parsing fails, use the status text
            errorBody = response.statusText;
        }
        throw new Error(`HTTP error ${response.status}: ${errorBody}`);
      }

      // Expecting JSON like {"role": "assistant", "content": "..."}
      const assistantMessage: ChatMessage = await response.json();

      if (assistantMessage && assistantMessage.role === 'assistant' && typeof assistantMessage.content === 'string') {
        console.log("Received assistant message:", assistantMessage.content.substring(0, 100) + "...");
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: null,
          chatHistory: [...prev.chatHistory, assistantMessage], // Add assistant message
        }));
      } else {
         console.error("Received invalid response structure:", assistantMessage);
         throw new Error("Received invalid response structure from backend.");
      }

    } catch (err) {
      console.error("Error fetching agent response:", err);
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  // Keep apiUrl dependency for consistency, though not directly used in fetch URL
  }, [apiUrl]); // Removed state dependency as functional updates are used

  // Return state values and submit function
  return {
    isLoading: state.isLoading,
    error: state.error,
    chatHistory: state.chatHistory,
    submitPrompt,
    // Removed progress and resultData as they were SSE specific
  };
}