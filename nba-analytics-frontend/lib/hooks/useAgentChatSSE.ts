// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string;
}

// Define ChatMessage interface
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  event?: string;
  status?: 'thinking' | 'error' | 'complete';
  progress?: number;
  toolCalls?: {
    tool_name: string;
    status: 'started' | 'completed' | 'error';
    content?: string;
  }[];
}

interface AgentChatSSEState {
  isLoading: boolean;
  error: string | null;
  chatHistory: ChatMessage[];
  // resultData was here, removed as it's not actively used per previous comments.
}

export function useAgentChatSSE({ 
  apiUrl
}: UseAgentChatSSEProps) {
  const [state, setState] = useState<AgentChatSSEState>({
    isLoading: false,
    error: null,
    chatHistory: [],
    // resultData: null // Removed from initial state
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    setState(prev => {
      if (!prompt.trim() || prev.isLoading) return prev;

      // Close existing connection if any
      if (eventSourceRef.current) {
        console.log('[SSE] Closing existing connection before new prompt');
        eventSourceRef.current.close();
        eventSourceRef.current = null; // Clear the ref immediately
      }
      
      console.log(`[SSE] Connecting to ${apiUrl}...`);
      const eventSource = new EventSource(`${apiUrl}?prompt=${encodeURIComponent(prompt)}`);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        // console.debug('[SSE] Received message:', event.data);
        try {
          const data = JSON.parse(event.data);
          // console.debug('[SSE] Parsed data:', data);
          setState(innerPrev => { // Use innerPrev to avoid conflict with outer prev
            const updatedHistory = [...innerPrev.chatHistory];
            if (updatedHistory.length > 0) {
              const lastMessage = updatedHistory[updatedHistory.length - 1];
              if (lastMessage.role === 'assistant') {
                if (data.event === "RunResponse") {
                  if (data.content) {
                    updatedHistory[updatedHistory.length - 1] = {
                      ...lastMessage,
                      content: lastMessage.content + data.content,
                      event: data.event,
                      status: data.status,
                      toolCalls: data.toolCalls
                    };
                  }
                } else if (data.content) { // Handle other events that might replace content
                  updatedHistory[updatedHistory.length - 1] = {
                    ...lastMessage,
                    content: data.content,
                    event: data.event,
                    status: data.status,
                    toolCalls: data.toolCalls
                  };
                }
              } else {
                updatedHistory.push({
                  role: 'assistant',
                  content: data.content || '',
                  event: data.event,
                  status: data.status,
                  toolCalls: data.toolCalls
                });
              }
            } else {
              updatedHistory.push({
                role: 'assistant',
                content: data.content || '',
                event: data.event,
                status: data.status,
                toolCalls: data.toolCalls
              });
            }

            const newState = {
              ...innerPrev,
              chatHistory: updatedHistory,
              isLoading: data.status !== 'complete' && data.event !== 'final'
            };
            return newState;
          });
        } catch (e) {
          console.error('[SSE] Failed to parse data:', e);
        }
      };

      eventSource.addEventListener('final', (event: MessageEvent) => {
        console.log('[SSE] Received final event.');
        try {
          // We might still parse data if the final event contains useful metadata, but we won't use it for message content.
          // const data = JSON.parse(event.data);
          // console.log('[SSE] Final event data:', data); 

          setState(innerPrev => {
            let finalHistory = [...innerPrev.chatHistory];
            
            // Ensure the *last* message is marked complete, if it's an assistant message
            if (finalHistory.length > 0) {
              const lastMessageIndex = finalHistory.length - 1;
              const lastMessage = finalHistory[lastMessageIndex];
              if (lastMessage.role === 'assistant' && lastMessage.status !== 'complete') {
                finalHistory[lastMessageIndex] = {
                  ...lastMessage,
                  status: 'complete' 
                };
              }
            }
            
            // Do NOT add a new message from the final event data
            const finalState = {
              ...innerPrev,
              chatHistory: finalHistory, // Use the potentially updated history (last message status)
              isLoading: false
            };
            return finalState;
          });
        } catch (e) {
          console.error('[SSE] Error processing final event (state update only):', e);
          // Still ensure loading is set to false on error
          setState(innerPrev => ({ ...innerPrev, isLoading: false }));
        }
        // Close connection AFTER state update attempt
        if (eventSourceRef.current) {
            console.log('[SSE] Closing connection after final event processing.');
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
      });

      eventSource.onerror = (error) => {
        console.error('[SSE] Connection error:', error);
        setState(innerPrev => ({ ...innerPrev, error: "Connection error. Please try again.", isLoading: false }));
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
      };

      // Return new state for the initial prompt submission
      return {
        ...prev,
        isLoading: true,
        error: null,
        chatHistory: [
          ...prev.chatHistory,
          { role: 'user', content: prompt }
        ]
      };
    });
  }, [apiUrl]); // Only apiUrl is a true dependency now

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('[SSE] Manual connection close');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setState(prev => {
        const updatedHistory = [...prev.chatHistory];
        if (updatedHistory.length > 0 && updatedHistory[updatedHistory.length - 1].role === 'assistant' && updatedHistory[updatedHistory.length - 1].status !== 'complete') {
          updatedHistory[updatedHistory.length - 1] = {
            ...updatedHistory[updatedHistory.length - 1],
            status: 'complete', // Mark as complete
            content: updatedHistory[updatedHistory.length - 1].content + "\n\n[Generation stopped by user]"
          };
        }
        return { ...prev, isLoading: false, chatHistory: updatedHistory };
      });
    }
  }, []);

  useEffect(() => {
    return () => { closeConnection(); };
  }, [closeConnection]);

  return {
    isLoading: state.isLoading,
    error: state.error,
    chatHistory: state.chatHistory,
    // resultData: state.resultData, // Removed from returned object
    submitPrompt,
    closeConnection
  };
}

// Removed commented-out parseStructuredData helper