// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string; // Keep for potential future use, though currently overridden
}

// Define ChatMessage interface (Exported from this file now)
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  event?: string;
  status?: string;
  toolCalls?: {
    type: string;
    function: {
      name: string;
      arguments: string;
    };
  }[];
}

interface AgentChatSSEState {
  isLoading: boolean;
  error: string | null;
  progress: string[];
  chatHistory: ChatMessage[]; // Manages chat history
  resultData: null; // Removed since we're not using structured results
  // chatText is removed as progress array and chatHistory handle status/content
}

export function useAgentChatSSE({ 
  /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
  apiUrl: _apiUrl 
}: UseAgentChatSSEProps) {
  const [state, setState] = useState<AgentChatSSEState>({
    isLoading: false,
    error: null,
    progress: [],
    chatHistory: [],
    resultData: null
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    // Add user message immediately
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      chatHistory: [
        ...prev.chatHistory,
        { role: 'user', content: prompt }
      ]
    }));

    console.log('Starting new SSE connection for prompt:', prompt);

    // Close any existing connection
    if (eventSourceRef.current) {
      console.log('Closing existing SSE connection');
      eventSourceRef.current.close();
    }

    // Create new EventSource connection
    const eventSource = new EventSource(`/api/ask?prompt=${encodeURIComponent(prompt)}`);
    eventSourceRef.current = eventSource;

    // Handle incoming messages
    eventSource.onmessage = (event) => {
      console.log('Received SSE message:', event.data);
      
      try {
        const data = JSON.parse(event.data);
        console.log('Parsed SSE data:', data);

        // Handle regular message updates
        setState(prev => {
          console.log('Current state before update:', prev);
          
          let updatedProgress = [...prev.progress];
          if (data.progress) {
            updatedProgress = [...prev.progress, `Progress: ${data.progress}%`];
          }

          const updatedHistory = [...prev.chatHistory];
          // Update the last assistant message if it exists
          if (updatedHistory.length > 0) {
            const lastMessage = updatedHistory[updatedHistory.length - 1];
            if (lastMessage.role === 'assistant') {
              // For RunResponse events, append the content
              if (data.event === "RunResponse") {
                if (data.content) {
                  console.log('Updating RunResponse content:', data.content);
                  updatedHistory[updatedHistory.length - 1] = {
                    ...lastMessage,
                    content: lastMessage.content + data.content,
                    event: data.event,
                    status: data.status,
                    toolCalls: data.toolCalls
                  };
                }
              } else if (data.content) {
                // For other events, replace the content if it exists
                console.log('Updating message content:', data.content);
                updatedHistory[updatedHistory.length - 1] = {
                  ...lastMessage,
                  content: data.content,
                  event: data.event,
                  status: data.status,
                  toolCalls: data.toolCalls
                };
              }
            } else {
              // If last message was from user, add new assistant message
              console.log('Adding new assistant message');
              updatedHistory.push({
                role: 'assistant',
                content: data.content || '',
                event: data.event,
                status: data.status,
                toolCalls: data.toolCalls
              });
            }
          } else {
            // If no messages exist, add first assistant message
            console.log('Adding first assistant message');
            updatedHistory.push({
              role: 'assistant',
              content: data.content || '',
              event: data.event,
              status: data.status,
              toolCalls: data.toolCalls
            });
          }

          const newState = {
            ...prev,
            progress: updatedProgress,
            chatHistory: updatedHistory,
            isLoading: data.status !== 'complete'
          };
          
          console.log('New state after update:', newState);
          return newState;
        });

      } catch (e) {
        console.error('Failed to parse SSE data:', e);
        setState(prev => ({ 
          ...prev, 
          progress: [...prev.progress, "Received unparseable message."] 
        }));
      }
    };

    // Handle final event
    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log('Received final SSE event:', event.data);
      
      try {
        const data = JSON.parse(event.data);
        setState(prev => {
          console.log('Processing final event, current state:', prev);
          
          let finalHistory = [...prev.chatHistory];
          
          // Update or add the final assistant message
          if (finalHistory.length > 0 && finalHistory[finalHistory.length - 1].role === 'assistant') {
            finalHistory = [
              ...finalHistory.slice(0, -1),
              {
                role: 'assistant',
                content: data.content,
                status: 'complete',
                event: 'final'
              }
            ];
          } else {
            finalHistory = [
              ...finalHistory,
              {
                role: 'assistant',
                content: data.content,
                status: 'complete',
                event: 'final'
              }
            ];
          }

          const finalState = {
            ...prev,
            chatHistory: finalHistory,
            progress: [...prev.progress, "Final response received."],
            isLoading: false
          };
          
          console.log('Final state:', finalState);
          return finalState;
        });
      } catch (e) {
        console.error('Failed to parse final SSE data:', e);
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

    // Handle connection error
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      setState(prev => ({
        ...prev,
        error: "Connection error. Please try again.",
        isLoading: false
      }));
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [state.isLoading]);

  // Cleanup function
  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('Cleaning up SSE connection');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeConnection();
    };
  }, [closeConnection]);

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

// Helper function (example - implement actual parsing logic if needed)
// function parseStructuredData(content: string): StructuredResult | null {
//   try {
//     // Attempt to find JSON within the content or use specific markers
//     // This is a placeholder - real implementation needed
//     const potentialJson = content.match(/```json\n([\s\S]*?)\n```/);
//     if (potentialJson && potentialJson[1]) { // Corrected: Use &&
//       const parsed = JSON.parse(potentialJson[1]);
//       // Basic validation
//       if (parsed.type && Array.isArray(parsed.data)) { // Corrected: Use &&
//         return parsed as StructuredResult;
//       }
//     }
//   } catch (e) {
//     console.warn("Could not parse structured data from content:", e);
//   }
//   return null;
// }