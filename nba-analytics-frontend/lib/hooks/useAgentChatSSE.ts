// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string;
}

// Define the ToolCallItem interface based on ChatMessage's toolCalls
interface ToolCallItem {
  tool_name: string;
  status: 'started' | 'completed' | 'error';
  content?: string;
}

// Define ChatMessage interface
export interface ChatMessage {
  id?: string; // Optional unique ID for each message for React keys
  role: 'user' | 'assistant';
  content: string;
  event?: string;
  status?: 'thinking' | 'error' | 'complete';
  progress?: number;
  toolCalls?: ToolCallItem[];
  dataType?: 'STAT_CARD' | 'CHART_DATA' | 'TABLE_DATA' | string;
  dataPayload?: any; // Parsed JSON payload or null if buffering string
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
        const data = JSON.parse(event.data) as Partial<ChatMessage> & {dataType?: ChatMessage['dataType'], dataPayload?: string | object };
        
        setState(prevState => {
          const updatedHistory = [...prevState.chatHistory];
          const lastMessageIndex = updatedHistory.length - 1;

          if (lastMessageIndex < 0 || updatedHistory[lastMessageIndex].role !== 'assistant') {
            console.error("[SSE] No assistant message found to update or last message is not assistant.");
            // Potentially create a new assistant message if absolutely necessary, though submitPrompt should handle it.
            // For safety, let's ensure there's always an assistant message to update if we receive an event.
             if (updatedHistory.length === 0 || updatedHistory[updatedHistory.length - 1].role === 'user') {
                updatedHistory.push({
                    id: `assistant-${Date.now()}`,
                    role: 'assistant',
                    content: '',
                    toolCalls: [],
                    status: 'thinking',
                    progress: 0,
                    event: data.event,
                });
                // Re-fetch lastMessageIndex and targetMessage if a new one was pushed
                const newLastMessageIndex = updatedHistory.length - 1;
                let targetMessage = { ...updatedHistory[newLastMessageIndex] };
                // Fall through to update this newly created message
             } else {
                return prevState; // Should not happen if submitPrompt sets up correctly
             }
          }
          
          let targetMessage = { ...updatedHistory[lastMessageIndex] };


          // 1. Merge ToolCalls
          if (data.toolCalls && Array.isArray(data.toolCalls)) {
            let mergedToolCalls: ToolCallItem[] = targetMessage.toolCalls ? [...targetMessage.toolCalls] : [];
            data.toolCalls.forEach((newTc: ToolCallItem) => {
              if (newTc && newTc.tool_name) {
                const existingTcIndex = mergedToolCalls.findIndex(tc => tc.tool_name === newTc.tool_name);
                if (existingTcIndex !== -1) {
                  mergedToolCalls[existingTcIndex] = { ...mergedToolCalls[existingTcIndex], ...newTc };
                } else {
                  mergedToolCalls.push(newTc);
                }
              } else {
                console.warn("[SSE] Received tool call without a name:", newTc);
              }
            });
            targetMessage.toolCalls = mergedToolCalls;
          }

          // 2. Handle Content, DataType, and DataPayload (JSON Streaming)
          if (data.dataType) { 
            currentActiveDataTypeRef.current = data.dataType;
            currentJsonBufferRef.current = ""; 
            if (typeof data.dataPayload === 'string') { 
              currentJsonBufferRef.current += data.dataPayload;
            }
            targetMessage.dataType = currentActiveDataTypeRef.current === null ? undefined : currentActiveDataTypeRef.current;
            targetMessage.dataPayload = null; 
            // Use content from this chunk if provided (e.g., "Here's the table:")
            // If this chunk also has content, it's likely a lead-in to the JSON.
            // If not, preserve existing content or set to empty if it's a new message.
            targetMessage.content = data.content !== undefined ? data.content : (targetMessage.content || "");
          
          } else if (currentActiveDataTypeRef.current && typeof data.dataPayload === 'string') {
            currentJsonBufferRef.current += data.dataPayload;
            // If this chunk also has content AND it's different from the payload, it's likely narrative.
            if (data.content && data.content !== data.dataPayload) {
                 targetMessage.content += data.content;
             }
          } else if (data.event === "RunResponse" && data.content) {
             // Append narrative content if no active JSON streaming for this message
             if (!currentActiveDataTypeRef.current) { 
               targetMessage.content += data.content;
             }
          } else if (data.content && !currentActiveDataTypeRef.current && data.event !== "RunResponse") {
            // For other events like ToolCallStarted/Completed with their own content from sse.py
            if (!targetMessage.content) { // Only set if main content is empty
              targetMessage.content = data.content;
            }
          }
          
          // Attempt to parse JSON
          if (targetMessage.dataType === currentActiveDataTypeRef.current && 
              currentActiveDataTypeRef.current && 
              currentJsonBufferRef.current.trim().endsWith("```")) {
            let jsonToParse = currentJsonBufferRef.current.trim();
            jsonToParse = jsonToParse.slice(0, -3).trim(); 
            
            try {
              const parsedPayload = JSON.parse(jsonToParse);
              targetMessage.dataPayload = parsedPayload; 
              console.log(`[SSE] Successfully parsed ${currentActiveDataTypeRef.current}:`, parsedPayload);
              currentActiveDataTypeRef.current = null; 
              currentJsonBufferRef.current = "";    
            } catch (e) {
               console.warn(`[SSE] Failed to parse accumulated ${targetMessage.dataType} JSON:`, e, "Buffer:", jsonToParse);
               if (currentJsonBufferRef.current.length > 15000 && !jsonToParse.trim().startsWith("{") && !jsonToParse.trim().startsWith("[")) { 
                   console.error("[SSE] JSON buffer too long and doesn't look like JSON, clearing activeDataType.");
                   currentActiveDataTypeRef.current = null; currentJsonBufferRef.current = ""; 
                   targetMessage.dataType = undefined; 
               }
            }
          }

          targetMessage.event = data.event || targetMessage.event;
          targetMessage.status = data.status || targetMessage.status;
          targetMessage.progress = data.progress !== undefined ? data.progress : targetMessage.progress;
          
          updatedHistory[lastMessageIndex] = targetMessage;

          return {
            ...prevState,
            chatHistory: updatedHistory,
            isLoading: data.status !== 'complete' && data.event !== 'final',
            // These are persisted in refs for the current message, not directly in hook's main state for setState loop
          };
        });
      } catch (e) {
        console.error('[SSE] Failed to parse data:', e);
      }
    };

    eventSource.addEventListener('final', (event: MessageEvent) => {
      console.log('[SSE] Received final event.');
      try {
        setState(prevState => {
          const finalHistory = [...prevState.chatHistory];
          const lastMessageIndex = finalHistory.length - 1;

          if (lastMessageIndex >=0 && finalHistory[lastMessageIndex].role === 'assistant') {
            let targetMessage = { ...finalHistory[lastMessageIndex] };
            targetMessage.status = 'complete';
            targetMessage.progress = 100;

            // Final attempt to parse any remaining buffer content
            if (currentActiveDataTypeRef.current && currentJsonBufferRef.current.trim()) {
                let jsonToParse = currentJsonBufferRef.current.trim();
                if (jsonToParse.endsWith("```")) {
                    jsonToParse = jsonToParse.slice(0, -3).trim();
                }
                 try {
                    const parsedPayload = JSON.parse(jsonToParse);
                    targetMessage.dataPayload = parsedPayload;
                    console.log(`[SSE] Final parse attempt for ${currentActiveDataTypeRef.current}:`, parsedPayload);
                } catch (e) {
                    console.warn(`[SSE] Final parse attempt failed for ${currentActiveDataTypeRef.current}:`, e, "Buffer:", jsonToParse);
                    targetMessage.content += `\n[Unparsed data: ${currentJsonBufferRef.current}]`;
                }
            }
            finalHistory[lastMessageIndex] = targetMessage;
          }
          
          currentJsonBufferRef.current = ""; // Clear refs on final
          currentActiveDataTypeRef.current = null;

          return {
            ...prevState,
            chatHistory: finalHistory,
            isLoading: false,
          };
        });
      } catch (e) {
        console.error('[SSE] Error processing final event:', e);
        setState(prevState => ({ ...prevState, isLoading: false }));
      }
      if (eventSourceRef.current) {
          console.log('[SSE] Closing connection after final event processing.');
          eventSourceRef.current.close();
          eventSourceRef.current = null;
      }
    });

    eventSource.onerror = (error: Event) => {
      console.error('[SSE] Connection error:', error);
      currentJsonBufferRef.current = ""; // Clear refs on error
      currentActiveDataTypeRef.current = null;
      setState(prevState => ({ 
        ...prevState, 
        error: "Connection error. Please try again.", 
        isLoading: false,
      }));
      if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
      }
    };

  }, [apiUrl, state.isLoading]); // Added state.isLoading to prevent multiple submissions

  const closeConnection = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('[SSE] Manual connection close');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      
      currentJsonBufferRef.current = ""; // Clear refs
      currentActiveDataTypeRef.current = null;

      setState(prev => {
        const updatedHistory = [...prev.chatHistory];
        const lastMessageIndex = updatedHistory.length - 1;
        if (lastMessageIndex >=0 && updatedHistory[lastMessageIndex].role === 'assistant' && updatedHistory[lastMessageIndex].status !== 'complete') {
          updatedHistory[lastMessageIndex] = {
            ...updatedHistory[lastMessageIndex],
            status: 'complete',
            // Use the ref for any unparsed data when connection is closed manually
            content: currentJsonBufferRef.current ?
                     (updatedHistory[lastMessageIndex].content + `\n[Unparsed data: ${currentJsonBufferRef.current}]`) :
                     (updatedHistory[lastMessageIndex].content + "\n\n[Generation stopped by user]")
          };
        }
        return {
          ...prev,
          isLoading: false,
          chatHistory: updatedHistory,
          // jsonBuffer and activeDataType are not part of 'prev' state directly anymore
        };
      });
    }
  }, []); // currentJsonBufferRef is stable, no need to add to deps

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
