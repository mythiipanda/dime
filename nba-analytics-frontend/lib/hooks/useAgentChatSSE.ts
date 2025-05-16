// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string;
}

// Define the ToolCallItem interface based on ChatMessage's toolCalls
interface ToolCallItem {
  tool_name: string;
  args?: any; // Arguments for the tool call
  status: 'started' | 'completed' | 'error';
  content?: string; // Summarized output or error message
  error?: string; // Specific error message if status is 'error'
  isError?: boolean; // Flag for error (computed from status or error presence)
}

// Define metadata interface for additional context
interface MessageMetadata {
  agent_id?: string;
  session_id?: string;
  run_id?: string;
  model?: string;
  timestamp?: number;
}

// Define reasoning interface for thinking process
interface ReasoningData {
  thinking?: string;
  content?: string;
  patterns?: {
    thinking?: string;
    planning?: string;
    analyzing?: string;
    [key: string]: string | undefined;
  };
}

// Define ChatMessage interface
export interface ChatMessage {
  id?: string; // Optional unique ID for each message for React keys
  role: 'user' | 'assistant';
  content: string;
  agentName?: string; // Name of the agent processing
  event?: string;
  status?: 'thinking' | 'tool_calling' | 'error' | 'complete';
  progress?: number;
  toolCalls?: ToolCallItem[];
  dataType?: 'STAT_CARD' | 'CHART_DATA' | 'TABLE_DATA' | string;
  dataPayload?: any; // Parsed JSON payload or null if buffering string
  metadata?: MessageMetadata; // Additional metadata about the message
  reasoning?: ReasoningData; // Thinking/reasoning process data
}

interface AgentChatSSEState {
  isLoading: boolean;
  error: string | null;
  chatHistory: ChatMessage[];
  // These refs will manage buffering for the *current* assistant message being streamed
  // They are not part of the setState loop directly but are used within it.
}

export function useAgentChatSSE({
  apiUrl
}: UseAgentChatSSEProps) {
  const [state, setState] = useState<AgentChatSSEState>({
    isLoading: false,
    error: null,
    chatHistory: [],
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  // Refs to manage ongoing JSON accumulation for the current assistant message
  const currentJsonBufferRef = useRef<string>("");
  const currentActiveDataTypeRef = useRef<ChatMessage['dataType'] | null>(null);


  const submitPrompt = useCallback((promptText: string) => {
    if (!promptText.trim() || state.isLoading) { // Check state.isLoading directly
        if (state.isLoading) console.warn("[SSE] Submission ignored, already loading.");
        return;
    }

    if (eventSourceRef.current) {
      console.log('[SSE] Closing existing connection before new prompt');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const newUserMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: promptText,
    };
    const initialAssistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      toolCalls: [],
      status: 'thinking',
      progress: 0,
      dataType: undefined,
      dataPayload: null
    };

    // Reset refs for the new stream session
    currentJsonBufferRef.current = "";
    currentActiveDataTypeRef.current = null;

    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      chatHistory: [...prev.chatHistory, newUserMessage, initialAssistantMessage],
    }));

    console.log(`[SSE] Connecting to ${apiUrl}...`);
    const eventSource = new EventSource(`${apiUrl}?prompt=${encodeURIComponent(promptText)}`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Partial<ChatMessage> & {
          dataType?: ChatMessage['dataType'],
          dataPayload?: string | object,
          metadata?: MessageMetadata,
          reasoning?: ReasoningData
        };

        setState(prevState => {
          const updatedHistory = [...prevState.chatHistory];
          const lastMessageIndex = updatedHistory.length - 1;

          if (lastMessageIndex < 0 || updatedHistory[lastMessageIndex].role !== 'assistant') {
            console.error("[SSE] No assistant message found to update or last message is not assistant.");
            // Create a new assistant message if needed
            if (updatedHistory.length === 0 || updatedHistory[updatedHistory.length - 1].role === 'user') {
                const newAssistantMessage: ChatMessage = {
                    id: `assistant-${Date.now()}`,
                    role: 'assistant',
                    content: '',
                    toolCalls: [],
                    status: 'thinking',
                    progress: 0,
                    event: data.event,
                    metadata: data.metadata,
                    reasoning: data.reasoning
                };
                updatedHistory.push(newAssistantMessage);
             } else {
                return prevState; // Should not happen if submitPrompt sets up correctly
             }
          }

          let targetMessage = { ...updatedHistory[lastMessageIndex] };

          // Extract agent name from metadata if available
          if (data.metadata?.agent_id) {
            // Use first part of agent_id as agent name if not already set
            if (!targetMessage.agentName) {
              const agentIdParts = data.metadata.agent_id.split('-');
              targetMessage.agentName = agentIdParts[0] || 'Assistant';
            }
          }

          // Update metadata if provided
          if (data.metadata) {
            targetMessage.metadata = {
              ...targetMessage.metadata,
              ...data.metadata
            };
          }

          // Update reasoning data if provided
          if (data.reasoning) {
            targetMessage.reasoning = {
              ...targetMessage.reasoning,
              ...data.reasoning
            };
          }

          // 1. Merge ToolCalls with enhanced error handling
          if (data.toolCalls && Array.isArray(data.toolCalls)) {
            let mergedToolCalls: ToolCallItem[] = targetMessage.toolCalls ? [...targetMessage.toolCalls] : [];

            data.toolCalls.forEach((newTc: Partial<ToolCallItem>) => {
              if (newTc && newTc.tool_name) {
                // Set isError flag based on status or error presence
                if (newTc.status === 'error' || newTc.error) {
                  newTc.isError = true;
                }

                const existingTcIndex = mergedToolCalls.findIndex(tc =>
                  tc.tool_name === newTc.tool_name &&
                  tc.status !== 'completed' &&
                  tc.status !== 'error'
                );

                if (existingTcIndex !== -1) {
                  // Update existing tool call
                  mergedToolCalls[existingTcIndex] = {
                    ...mergedToolCalls[existingTcIndex],
                    ...newTc,
                    // Preserve error information
                    error: newTc.error || mergedToolCalls[existingTcIndex].error,
                    isError: newTc.isError || mergedToolCalls[existingTcIndex].isError
                  };
                } else {
                  // Check if we have this tool call in any state
                  const anyTcIndex = mergedToolCalls.findIndex(tc => tc.tool_name === newTc.tool_name);

                  if (anyTcIndex !== -1) {
                    // Update existing tool call regardless of state
                    mergedToolCalls[anyTcIndex] = {
                      ...mergedToolCalls[anyTcIndex],
                      ...newTc
                    };
                  } else {
                    // Add new tool call
                    mergedToolCalls.push(newTc as ToolCallItem);
                  }
                }
              } else {
                console.warn("[SSE] Received tool call without a name:", newTc);
              }
            });

            targetMessage.toolCalls = mergedToolCalls;
          }

          // 2. Handle Content, DataType, and DataPayload with improved JSON handling

          // Process content based on event type
          if (data.content) {
            // Extract thinking patterns to highlight
            const extractThinkingPattern = (content: string): string | null => {
              // Look for patterns like **Thinking:** or **Planning:** or **Analyzing:**
              const thinkingMatch = content.match(/\*\*(Thinking|Planning|Analyzing):\*\*(.*?)(?=\*\*|$)/i);
              return thinkingMatch ? thinkingMatch[0] : null;
            };

            if (data.event === "RunStarted") {
              // For initial message, replace content
              targetMessage.content = data.content;
            } else if (data.event === "RunResponse") {
              // For regular responses, check if it's a thinking pattern
              const thinkingPattern = extractThinkingPattern(data.content);

              if (thinkingPattern) {
                // If it's a thinking pattern, make sure it's properly formatted
                if (!targetMessage.content?.includes(thinkingPattern)) {
                  // Add a newline before the thinking pattern if needed
                  if (targetMessage.content && !targetMessage.content.endsWith('\n\n')) {
                    targetMessage.content = targetMessage.content.trim() + '\n\n';
                  }
                  targetMessage.content = (targetMessage.content || "") + data.content;
                }
              } else {
                // For regular content, just append
                targetMessage.content = (targetMessage.content || "") + data.content;
              }
            } else if (data.event === "ToolCallStarted" || data.event === "ToolCallCompleted") {
              // For tool calls, only append if not duplicate
              if (!targetMessage.content?.includes(data.content)) {
                // Add a newline before tool call content if needed
                if (targetMessage.content && !targetMessage.content.endsWith('\n\n')) {
                  targetMessage.content = targetMessage.content.trim() + '\n\n';
                }
                targetMessage.content = (targetMessage.content || "") + data.content + "\n";
              }
            } else {
              // For other events, append content
              targetMessage.content = (targetMessage.content || "") + data.content;
            }
          }

          // Handle rich data types
          if (data.dataType) {
            currentActiveDataTypeRef.current = data.dataType;
            currentJsonBufferRef.current = "";

            // Store data type in message
            targetMessage.dataType = data.dataType;

            // Handle data payload
            if (data.dataPayload) {
              if (typeof data.dataPayload === 'string') {
                // Store string payload in buffer for accumulation
                currentJsonBufferRef.current = data.dataPayload;

                // Try to parse JSON
                try {
                  const parsedPayload = JSON.parse(data.dataPayload);
                  targetMessage.dataPayload = parsedPayload;
                } catch (e) {
                  // If parsing fails, store as string for now
                  targetMessage.dataPayload = data.dataPayload;
                }
              } else {
                // If payload is already an object, store directly
                targetMessage.dataPayload = data.dataPayload;
              }
            }
          } else if (currentActiveDataTypeRef.current && data.dataPayload) {
            // Continue accumulating JSON data
            if (typeof data.dataPayload === 'string') {
              currentJsonBufferRef.current += data.dataPayload;

              // Try to parse accumulated JSON
              try {
                const parsedPayload = JSON.parse(currentJsonBufferRef.current);
                targetMessage.dataType = currentActiveDataTypeRef.current;
                targetMessage.dataPayload = parsedPayload;
              } catch (e) {
                // If parsing fails, continue accumulating
                console.debug("[SSE] Continuing to accumulate JSON data");
              }
            }
          }

          // Update status and progress
          targetMessage.event = data.event || targetMessage.event;
          targetMessage.status = data.status || targetMessage.status;
          targetMessage.progress = data.progress !== undefined ? data.progress : targetMessage.progress;

          // Special handling for RunCompleted event
          if (data.event === "RunCompleted") {
            console.log("[SSE] Received RunCompleted event");
            // Mark the message as complete
            targetMessage.status = "complete";
            targetMessage.progress = 100;
          }

          // Update the message in history
          updatedHistory[lastMessageIndex] = targetMessage;

          // Only stop loading when we receive the final event
          // This ensures we don't stop processing prematurely
          const shouldStopLoading = data.event === 'final' ||
                                   (data.event === 'RunCompleted' && data.status === 'complete');

          return {
            ...prevState,
            chatHistory: updatedHistory,
            isLoading: !shouldStopLoading
          };
        });
      } catch (e) {
        console.error('[SSE] Failed to parse data:', e, event.data);
      }
    };

    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log('[SSE] Received final event.');
      try {
        // The 'final' event from sse.py should now contain the complete last message state
        const finalData = JSON.parse(event.data) as ChatMessage & {
          metadata?: MessageMetadata,
          reasoning?: ReasoningData
        };

        setState(prevState => {
          const finalHistory = [...prevState.chatHistory];
          const lastMessageIndex = finalHistory.length - 1;

          if (lastMessageIndex >= 0 && finalHistory[lastMessageIndex].role === 'assistant') {
            // Get the existing message to preserve any accumulated data
            const existingMessage = finalHistory[lastMessageIndex];

            // Merge the final data with the existing message
            finalHistory[lastMessageIndex] = {
              ...existingMessage, // Keep existing data
              ...finalData, // Apply fields from the final server event

              // Ensure these fields are properly set
              status: 'complete',
              progress: 100,

              // Merge metadata if both exist
              metadata: {
                ...existingMessage.metadata,
                ...finalData.metadata
              },

              // Merge reasoning if both exist
              reasoning: {
                ...existingMessage.reasoning,
                ...finalData.reasoning
              },

              // Merge tool calls if both exist
              toolCalls: finalData.toolCalls || existingMessage.toolCalls
            };

            // If we have accumulated JSON data that hasn't been parsed yet, try one more time
            if (currentJsonBufferRef.current && currentActiveDataTypeRef.current) {
              try {
                const parsedPayload = JSON.parse(currentJsonBufferRef.current);
                finalHistory[lastMessageIndex].dataType = currentActiveDataTypeRef.current;
                finalHistory[lastMessageIndex].dataPayload = parsedPayload;
              } catch (e) {
                console.warn('[SSE] Failed to parse accumulated JSON in final event:', e);
                // If parsing fails, store the raw string
                if (!finalHistory[lastMessageIndex].dataPayload) {
                  finalHistory[lastMessageIndex].dataType = currentActiveDataTypeRef.current;
                  finalHistory[lastMessageIndex].dataPayload = currentJsonBufferRef.current;
                }
              }
            }
          } else {
            // If for some reason there's no assistant message, add this one
            finalHistory.push({
                id: `assistant-${Date.now()}`,
                ...finalData,
                status: 'complete',
                progress: 100
            });
          }

          // Clear refs on final
          currentJsonBufferRef.current = "";
          currentActiveDataTypeRef.current = null;

          return {
            ...prevState,
            chatHistory: finalHistory,
            isLoading: false,
          };
        });

        // Log completion for debugging
        console.log('[SSE] Final event processed successfully');
      } catch (e) {
        console.error('[SSE] Error processing final event:', e, event.data);
        setState(prevState => ({ ...prevState, isLoading: false }));
      }

      // Close the connection
      if (eventSourceRef.current) {
          console.log('[SSE] Closing connection after final event processing.');
          eventSourceRef.current.close();
          eventSourceRef.current = null;
      }
    });

    eventSource.onerror = (error: Event) => {
      console.error('[SSE] Connection error:', error);

      // Clear refs on error
      currentJsonBufferRef.current = "";
      currentActiveDataTypeRef.current = null;

      setState(prevState => {
        const updatedHistory = [...prevState.chatHistory];
        const lastMessageIndex = updatedHistory.length - 1;

        // If there's an assistant message being streamed, mark it as error
        if (lastMessageIndex >= 0 && updatedHistory[lastMessageIndex].role === 'assistant' &&
            updatedHistory[lastMessageIndex].status !== 'complete') {
          updatedHistory[lastMessageIndex] = {
            ...updatedHistory[lastMessageIndex],
            status: 'error',
            content: updatedHistory[lastMessageIndex].content +
                     "\n\n[Connection error. The response may be incomplete.]"
          };
        }

        return {
          ...prevState,
          chatHistory: updatedHistory,
          error: "Connection error. Please try again.",
          isLoading: false,
        };
      });

      // Close the connection
      if (eventSourceRef.current) {
          console.log('[SSE] Closing connection after error');
          eventSourceRef.current.close();
          eventSourceRef.current = null;
      }
    };

  }, [apiUrl, state.isLoading]); // Added state.isLoading to prevent multiple submissions

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('[SSE] Manual connection close');

      // Close the connection
      eventSourceRef.current.close();
      eventSourceRef.current = null;

      // Get any accumulated data before clearing refs
      const accumulatedJsonData = currentJsonBufferRef.current;
      const activeDataType = currentActiveDataTypeRef.current;

      // Clear refs
      currentJsonBufferRef.current = "";
      currentActiveDataTypeRef.current = null;

      setState(prev => {
        const updatedHistory = [...prev.chatHistory];
        const lastMessageIndex = updatedHistory.length - 1;

        if (lastMessageIndex >= 0 &&
            updatedHistory[lastMessageIndex].role === 'assistant' &&
            updatedHistory[lastMessageIndex].status !== 'complete') {

          // Create updated message
          const updatedMessage: ChatMessage = {
            ...updatedHistory[lastMessageIndex],
            status: 'complete' as const,
            progress: 100
          };

          // Add note about manual stopping
          updatedMessage.content = updatedMessage.content + "\n\n[Generation stopped by user]";

          // Try to parse any accumulated JSON data
          if (accumulatedJsonData && activeDataType) {
            try {
              const parsedPayload = JSON.parse(accumulatedJsonData);
              updatedMessage.dataType = activeDataType;
              updatedMessage.dataPayload = parsedPayload;
            } catch (e) {
              console.warn('[SSE] Failed to parse accumulated JSON on manual close:', e);

              // If we have unparsed data, note it in the message
              if (accumulatedJsonData.length > 0) {
                // Only show a preview of the data to avoid cluttering the UI
                const dataPreview = accumulatedJsonData.length > 50
                  ? accumulatedJsonData.substring(0, 47) + '...'
                  : accumulatedJsonData;

                updatedMessage.content += `\n[Unparsed data available: ${dataPreview}]`;
              }
            }
          }

          // Update the message
          updatedHistory[lastMessageIndex] = updatedMessage;
        }

        return {
          ...prev,
          isLoading: false,
          chatHistory: updatedHistory
        };
      });
    }
  }, []); // Refs are stable, no need to add to deps

  useEffect(() => {
    return () => { closeConnection(); };
  }, [closeConnection]);

  return {
    isLoading: state.isLoading,
    error: state.error,
    chatHistory: state.chatHistory,
    submitPrompt,
    closeConnection
  };
}
