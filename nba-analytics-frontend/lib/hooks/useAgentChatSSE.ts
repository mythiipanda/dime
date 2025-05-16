// lib/hooks/useAgentChatSSE.ts
import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAgentChatSSEProps {
  apiUrl: string;
}

// Define the ToolCallItem interface based on ChatMessage's toolCalls
interface ToolCallItem {
  tool_name: string;
  args?: any; // Added: arguments for the tool call
  status: 'started' | 'completed' | 'error';
  content?: string; // Summarized output or error message
  isError?: boolean; // Added: flag for error
}

// Define ChatMessage interface
export interface ChatMessage {
  id?: string; // Optional unique ID for each message for React keys
  role: 'user' | 'assistant';
  content: string;
  agentName?: string; // Added: Name of the agent processing
  event?: string;
  status?: 'thinking' | 'tool_calling' | 'error' | 'complete'; // Added 'tool_calling'
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

          // Update agentName if provided
          if (data.agentName) {
            targetMessage.agentName = data.agentName;
          }

          // 1. Merge ToolCalls - enhanced
          if (data.toolCalls && Array.isArray(data.toolCalls)) {
            let mergedToolCalls: ToolCallItem[] = targetMessage.toolCalls ? [...targetMessage.toolCalls] : [];
            data.toolCalls.forEach((newTc: Partial<ToolCallItem>) => { // Use Partial for incoming
              if (newTc && newTc.tool_name) {
                const existingTcIndex = mergedToolCalls.findIndex(tc => tc.tool_name === newTc.tool_name && tc.status !== 'completed'); // Match only active or just started
                if (existingTcIndex !== -1) {
                  // Update existing tool call
                  mergedToolCalls[existingTcIndex] = { 
                    ...mergedToolCalls[existingTcIndex], 
                    ...newTc,
                    status: newTc.status || mergedToolCalls[existingTcIndex].status, // Ensure status is updated
                  };
                } else if (newTc.status === 'started') { // Only add new if it's a 'started' event for a new tool
                  mergedToolCalls.push(newTc as ToolCallItem); // Cast to full ToolCallItem
                } else if (newTc.status === 'completed') {
                  // If a 'completed' event comes for a tool not in 'started' state (e.g. if UI missed start)
                  // Add it directly. This is a fallback.
                  const completedTcIndex = mergedToolCalls.findIndex(tc => tc.tool_name === newTc.tool_name);
                  if (completedTcIndex !== -1) {
                     mergedToolCalls[completedTcIndex] = { ...mergedToolCalls[completedTcIndex], ...newTc as ToolCallItem };
                  } else {
                     mergedToolCalls.push(newTc as ToolCallItem);
                  }
                }
              } else {
                console.warn("[SSE] Received tool call without a name:", newTc);
              }
            });
            targetMessage.toolCalls = mergedToolCalls;
          }

          // 2. Handle Content, DataType, and DataPayload (JSON Streaming)
          // Preserve existing content logic, but ensure new event-driven content from sse.py is handled.
          
          let newContentSegment = "";
          if (data.event === "RunStarted" && data.content) {
            // For "Starting process with [AgentName]..."
            newContentSegment = data.content + "\n"; // Add newline
          } else if (data.event === "ToolCallStarted" && data.content && !data.dataType) {
            // For "[AgentName] is calling tool(s): ..."
            // This content is useful for the thinking process display.
            // Avoid directly appending to main visible content if it's just a tool call announcement,
            // unless there's no other narrative content being built.
             if (!targetMessage.content?.includes(data.content)) { // Avoid duplicates
                newContentSegment = data.content + "\n";
             }
          } else if (data.event === "ToolCallCompleted" && data.content && !data.dataType) {
            // For "Tool(s) ... completed." - also good for thinking process
            // Append if we are not yet in the final answer phase
            if (!targetMessage.content?.includes(data.content)) { // Avoid duplicates
                newContentSegment = data.content + "\n";
            }
          } else if (data.event === "RunResponse" && data.content) {
            // This is the main narrative content from the agent
            newContentSegment = data.content;
          }


          if (data.dataType) { 
            currentActiveDataTypeRef.current = data.dataType;
            currentJsonBufferRef.current = ""; 
            if (typeof data.dataPayload === 'string') { 
              currentJsonBufferRef.current += data.dataPayload;
            }
            targetMessage.dataType = currentActiveDataTypeRef.current === null ? undefined : currentActiveDataTypeRef.current;
            targetMessage.dataPayload = null; 
            // If there's also a content field in this dataType chunk, it's a lead-in.
            targetMessage.content = data.content !== undefined ? (targetMessage.content || "") + data.content : (targetMessage.content || "");
          
          } else if (currentActiveDataTypeRef.current && typeof data.dataPayload === 'string') {
            currentJsonBufferRef.current += data.dataPayload;
            // If this chunk also has content AND it's different from the payload, append it.
            if (data.content && data.content !== data.dataPayload) {
                 targetMessage.content += data.content; // Append narrative mixed with JSON stream
             }
          } else if (newContentSegment) { // General content from RunStarted, ToolCall (if no dataType), RunResponse
             // Append new segments if not actively streaming a specific data type (like JSON for a chart)
             // The ChatMessageDisplay component will handle separating reasoning from final answer using FINAL_ANSWER_MARKER
             targetMessage.content = (targetMessage.content || "") + newContentSegment;
          }
          // If content was just an announcement like "Tool X completed" and we have rich data, prioritize rich data display
          // The announcements are still good for the "thinking process" part of the UI.
          
          targetMessage.event = data.event || targetMessage.event;
          targetMessage.status = data.status || targetMessage.status; // status like 'tool_calling'
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
        // The 'final' event from sse.py should now contain the complete last message state
        const finalData = JSON.parse(event.data) as ChatMessage;

        setState(prevState => {
          const finalHistory = [...prevState.chatHistory];
          const lastMessageIndex = finalHistory.length - 1;

          if (lastMessageIndex >=0 && finalHistory[lastMessageIndex].role === 'assistant') {
            // Overwrite the last assistant message with the complete data from 'final' event
            finalHistory[lastMessageIndex] = {
              ...finalHistory[lastMessageIndex], // Keep ID
              ...finalData, // Apply all fields from the final server event
              status: 'complete',
              progress: 100,
            };
          } else {
            // If for some reason there's no assistant message, add this one.
            finalHistory.push({
                id: `assistant-${Date.now()}`, 
                ...finalData, 
                status: 'complete', 
                progress: 100
            });
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
