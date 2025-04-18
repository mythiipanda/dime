// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string; // Use this prop
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
  chatHistory: ChatMessage[]; // Manages chat history
  resultData: null; // Removed since we're not using structured results
  // chatText is removed as progress array and chatHistory handle status/content
}

export function useAgentChatSSE({ 
  apiUrl // Use the passed apiUrl
}: UseAgentChatSSEProps) {
  const [state, setState] = useState<AgentChatSSEState>({
    isLoading: false,
    error: null,
    chatHistory: [],
    resultData: null
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const submitPrompt = useCallback((prompt: string) => {
    if (!prompt.trim() || state.isLoading) return;

    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      chatHistory: [
        ...prev.chatHistory,
        { role: 'user', content: prompt }
      ]
    }));

    console.log(`[SSE] Connecting to ${apiUrl}...`);

    if (eventSourceRef.current) {
      console.log('[SSE] Closing existing connection');
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`${apiUrl}?prompt=${encodeURIComponent(prompt)}`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      // console.debug('[SSE] Received message:', event.data); // Optional: Keep for debugging
      try {
        const data = JSON.parse(event.data);
        // console.debug('[SSE] Parsed data:', data); // Optional: Keep for debugging
        setState(prev => {
          const updatedHistory = [...prev.chatHistory];
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
              } else if (data.content) {
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
            ...prev,
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
        const data = JSON.parse(event.data);
        setState(prev => {
          let finalHistory = [...prev.chatHistory];
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
            isLoading: false
          };
          return finalState;
        });
      } catch (e) {
        console.error('[SSE] Failed to parse final data:', e);
        setState(prev => ({ ...prev, error: "Failed to parse final event.", isLoading: false }));
      }
      eventSource.close();
      eventSourceRef.current = null;
    });

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      setState(prev => ({ ...prev, error: "Connection error. Please try again.", isLoading: false }));
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [state.isLoading, apiUrl]);

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('[SSE] Manual connection close');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setState(prev => {
        const updatedHistory = [...prev.chatHistory];
        if (updatedHistory.length > 0 && updatedHistory[updatedHistory.length - 1].role === 'assistant') {
          updatedHistory[updatedHistory.length - 1] = {
            ...updatedHistory[updatedHistory.length - 1],
            status: 'complete',
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
    resultData: state.resultData,
    submitPrompt,
    closeConnection
  };
}

// Removed commented-out parseStructuredData helper