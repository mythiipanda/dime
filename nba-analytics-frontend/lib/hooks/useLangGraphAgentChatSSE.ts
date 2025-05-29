import { useState, useEffect, useCallback, useRef } from 'react';

// Define the structure for an intermediate step in the AI's process
export interface IntermediateStep {
  id: string; // Unique ID for the step
  type: 'tool_call' | 'tool_result' | 'system_event' | 'thought_chunk' | 'error_event';
  timestamp: number; // To help with ordering if needed
  // Specific data for each type
  toolCalls?: Array<{ name: string; args: Record<string, any>; id: string }>; // For tool_call
  toolName?: string;       // For tool_result
  toolCallId?: string;     // For tool_result
  toolResultContent?: string; // For tool_result (can be stringified JSON)
  systemEventContent?: string; // For system_event
  nodeName?: string;       // For system_event
  thoughtChunkContent?: string; // For thought_chunk
  errorEventContent?: string; // For error_event
  isError?: boolean; // For tool_result or error_event
}

// Define the structure of a chat message for the frontend
export interface FrontendChatMessage {
  id: string; // Unique ID for the message
  type: 'human' | 'ai'; // Simplified to human or AI. AI messages will contain intermediate steps.
  content?: string; // Text content (for human messages, or final AI answer)
  
  // AI-specific fields
  isStreaming?: boolean; // True if AI message is still streaming its final answer or thoughts
  intermediateSteps?: IntermediateStep[]; // Array to hold tool calls, results, thoughts, system events
  llmOutput?: string | object; // To store raw LLM output if needed for display
}

interface AgentSSEHookOptions {
  apiUrl: string;
}

export function useLangGraphAgentChatSSE({
  apiUrl,
}: AgentSSEHookOptions) {
  const [chatHistory, setChatHistory] = useState<FrontendChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentAIMessageRef = useRef<FrontendChatMessage | null>(null); // This will hold the AI's entire turn
  const currentThoughtChunkRef = useRef<IntermediateStep | null>(null); // To accumulate thought stream

  const connectionClosedIntentionallyRef = useRef(false);
  const graphEndReceivedRef = useRef(false);

  const updateCurrentAIMessage = useCallback((updater: (prevMessage: FrontendChatMessage) => FrontendChatMessage) => {
    if (currentAIMessageRef.current) {
      const updatedMessage = updater(currentAIMessageRef.current);
      currentAIMessageRef.current = updatedMessage;
      setChatHistory(prev => 
        prev.map(msg => msg.id === updatedMessage.id ? updatedMessage : msg)
      );
    }
  }, []);

  const addIntermediateStep = useCallback((step: Omit<IntermediateStep, 'id' | 'timestamp'>) => {
    if (currentAIMessageRef.current) {
      const newStep: IntermediateStep = {
        ...step,
        id: Date.now().toString() + '-step-' + Math.random().toString(36).substring(7),
        timestamp: Date.now(),
      };
      updateCurrentAIMessage(prevMessage => ({
        ...prevMessage,
        intermediateSteps: [...(prevMessage.intermediateSteps || []), newStep],
      }));
      // If this new step is a thought chunk, set it as current
      if (newStep.type === 'thought_chunk') {
        currentThoughtChunkRef.current = newStep;
      } else {
        currentThoughtChunkRef.current = null; // Reset if it's not a continuous thought stream
      }
    }
  }, [updateCurrentAIMessage]);


  const closeConnection = useCallback((isFinalClose: boolean = false) => {
    if (eventSourceRef.current) {
      if (isFinalClose || !graphEndReceivedRef.current) { 
        connectionClosedIntentionallyRef.current = true;
      }
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsLoading(false);
      if (currentAIMessageRef.current) {
        updateCurrentAIMessage(prev => ({...prev, isStreaming: false}));
      }
      // currentAIMessageRef.current = null; // Don't nullify here, final answer might still be processed
      currentThoughtChunkRef.current = null;
      console.log("SSE connection closed by client.");
    }
  }, [updateCurrentAIMessage]);

  const submitPrompt = useCallback(async (prompt: string) => {
    if (eventSourceRef.current) {
      console.log("Closing existing SSE connection before starting new one.");
      closeConnection();
    }
    graphEndReceivedRef.current = false;
    connectionClosedIntentionallyRef.current = false;
    
    // Initialize the new AI message for this turn
    const newAIMsgId = Date.now().toString() + '-ai-' + Math.random().toString(36).substring(7);
    const initialAIMessage: FrontendChatMessage = {
      id: newAIMsgId,
      type: 'ai',
      content: '', // Initially no content, will be filled by final_answer or thoughts
      intermediateSteps: [],
      isStreaming: true, // Starts in streaming state
    };
    currentAIMessageRef.current = initialAIMessage;
    currentThoughtChunkRef.current = null; // Reset any ongoing thought
    setChatHistory(prev => [...prev, initialAIMessage]);

    setIsLoading(true);
    setError(null);

    const url = `${apiUrl}?query=${encodeURIComponent(prompt)}`;
    eventSourceRef.current = new EventSource(url);
    console.log(`SSE connection opened to: ${url}`);

    eventSourceRef.current.onopen = () => {
      console.log("SSE connection established.");
      connectionClosedIntentionallyRef.current = false;
    };

    eventSourceRef.current.onerror = (event) => {
      if (graphEndReceivedRef.current || connectionClosedIntentionallyRef.current) {
        setIsLoading(false);
        return;
      }
      console.error("SSE generic connection error (.onerror):", event);
      const errorContent = "Connection error with the AI agent. Please check your network or try again.";
      setError(errorContent);
      addIntermediateStep({ type: 'error_event', errorEventContent: errorContent });
      if (currentAIMessageRef.current) {
        updateCurrentAIMessage(prev => ({...prev, isStreaming: false, content: prev.content || "Failed to get a response."}));
      }
      setIsLoading(false);
      closeConnection();
    };

    eventSourceRef.current.addEventListener('node_update', (event: Event) => {
      const eventWithMessage = event as MessageEvent;
      const data = JSON.parse(eventWithMessage.data);
      console.log("SSE Event (node_update):", data);
      addIntermediateStep({ 
        type: 'system_event', 
        systemEventContent: `Processing step: ${data.node_name || 'Unknown step'}`,
        nodeName: data.node_name 
      });
    });

    eventSourceRef.current.addEventListener('message', (event: Event) => {
      const eventWithMessage = event as MessageEvent;
      const data = JSON.parse(eventWithMessage.data);
      console.log("SSE Event (message - likely tool related):", data);
      
      if (data.type === 'tool_call') {
        addIntermediateStep({ type: 'tool_call', toolCalls: data.tool_calls });
      } else if (data.type === 'tool_result') {
        addIntermediateStep({ 
          type: 'tool_result', 
          toolName: data.name, 
          toolCallId: data.tool_call_id,
          toolResultContent: typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2),
          isError: data.is_error === true || (typeof data.content === 'string' && data.content.toLowerCase().includes('error')) // Check for explicit error flag or content
        });
      } else if (data.type === 'ai') { // This might be an older way of sending final answer, or intermediate LLM output
          updateCurrentAIMessage(prev => ({
            ...prev,
            llmOutput: data.content, // Store as llmOutput, actual final answer comes from 'final_answer' or accumulated thoughts
            // Potentially update main content if this is meant to be the only AI response and no 'final_answer' event comes
            // content: prev.content || data.content, 
            isStreaming: false // Assuming this variant of 'ai' message is not streaming further by itself
          }));
      } else if (data.type === 'human'){
        console.warn("Received human message from SSE, typically not expected here.");
      }
    });

    eventSourceRef.current.addEventListener('thought_stream', (event: Event) => {
      const eventWithMessage = event as MessageEvent;
      const data = JSON.parse(eventWithMessage.data);
      console.log("SSE Event (thought_stream):", data.chunk);
      
      if (currentAIMessageRef.current) {
        // If there's an active thought_chunk, append to it
        if (currentThoughtChunkRef.current && currentThoughtChunkRef.current.type === 'thought_chunk') {
          const updatedThoughtChunkContent = (currentThoughtChunkRef.current.thoughtChunkContent || '') + data.chunk;
          const thoughtChunkId = currentThoughtChunkRef.current.id;
          
          // Update the specific thought chunk step
          currentThoughtChunkRef.current.thoughtChunkContent = updatedThoughtChunkContent;
          updateCurrentAIMessage(prevMsg => ({
            ...prevMsg,
            intermediateSteps: (prevMsg.intermediateSteps || []).map(step => 
              step.id === thoughtChunkId ? { ...step, thoughtChunkContent: updatedThoughtChunkContent } : step
            ),
            isStreaming: true, // Overall AI message is still streaming thoughts
          }));
        } else {
          // Otherwise, create a new thought_chunk step
          addIntermediateStep({ type: 'thought_chunk', thoughtChunkContent: data.chunk });
        }
      }
    });

    eventSourceRef.current.addEventListener('final_answer', (event: Event) => {
      const eventWithMessage = event as MessageEvent;
      const data = JSON.parse(eventWithMessage.data);
      console.log("SSE Event (final_answer):", data.answer);
      currentThoughtChunkRef.current = null; // Final answer received, stop accumulating thoughts
      if (currentAIMessageRef.current) {
        updateCurrentAIMessage(prev => ({
          ...prev,
          content: data.answer, 
          isStreaming: false, // Final answer means streaming is complete for content
        }));
      }
      // setIsLoading(false); // Moved to graph_end or error
    });

    eventSourceRef.current.addEventListener('graph_end', (event: Event) => {
      console.log("SSE Event (graph_end) RECEIVED. Finalizing.");
      graphEndReceivedRef.current = true;
      setIsLoading(false);
      if (currentAIMessageRef.current) {
         updateCurrentAIMessage(prev => ({...prev, isStreaming: false}));
      }
      closeConnection(true); // Close connection as graph has ended
    });

    eventSourceRef.current.addEventListener('error', (event: Event) => { 
      const eventWithMessage = event as MessageEvent; 
      if (eventWithMessage.data) { 
        try {
          const data = JSON.parse(eventWithMessage.data);
          console.error("SSE Event (backend error):", data);
          const errorMsgContent = data.message || "An error occurred with the AI agent.";
          setError(errorMsgContent);
          addIntermediateStep({ type: 'error_event', errorEventContent: errorMsgContent, isError: true });
          if (currentAIMessageRef.current) {
            updateCurrentAIMessage(prev => ({...prev, isStreaming: false, content: prev.content || "Error processing request."}))     
          }
        } catch (e) {
          console.error("Failed to parse backend error event data:", eventWithMessage.data, e);
          const genericError = "Received an unparsable error from the agent.";
          setError(genericError);
          addIntermediateStep({ type: 'error_event', errorEventContent: genericError, isError: true });
           if (currentAIMessageRef.current) {
            updateCurrentAIMessage(prev => ({...prev, isStreaming: false, content: prev.content || "Error processing request."}))     
          }
        }
      }
      setIsLoading(false);
      closeConnection(); // Close on backend error
    });

  }, [apiUrl, closeConnection, addIntermediateStep, updateCurrentAIMessage]);

  useEffect(() => {
    return () => {
      closeConnection(true); // Ensure connection is closed on unmount
    };
  }, [closeConnection]);

  return {
    chatHistory,
    isLoading,
    error,
    submitPrompt,
    closeConnection,
    setChatHistory
  };
} 