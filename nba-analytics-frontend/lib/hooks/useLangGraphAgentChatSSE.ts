/**
 * Refactored LangGraph Agent Chat SSE Hook
 * Following SOLID principles with service-based architecture.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  AgentSSEHookOptions, 
  IChatHookReturn, 
  FrontendChatMessage,
  IntermediateStep 
} from './interfaces';
import { 
  EventSourceManager, 
  MessageManager, 
  ConnectionManager, 
  ThreadManager 
} from './services';

export function useLangGraphAgentChatSSE({
  apiUrl,
  threadId: initialThreadId,
  userId,
}: AgentSSEHookOptions): IChatHookReturn {
  // State management
  const [chatHistory, setChatHistory] = useState<FrontendChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(initialThreadId || null);
  
  // Refs for immediate access
  const threadIdRef = useRef<string | null>(initialThreadId || null);
  const graphEndReceivedRef = useRef(false);
  const connectionClosedIntentionallyRef = useRef(false);
  
  // Service instances
  const eventSourceManagerRef = useRef(new EventSourceManager());
  const messageManagerRef = useRef(new MessageManager(setChatHistory));
  const connectionManagerRef = useRef(new ConnectionManager(setIsLoading, setError));
  const threadManagerRef = useRef(new ThreadManager(setCurrentThreadId, threadIdRef));

  const eventSourceManager = eventSourceManagerRef.current;
  const messageManager = messageManagerRef.current;
  const connectionManager = connectionManagerRef.current;
  const threadManager = threadManagerRef.current;

  // Move closeConnection above all event handler helpers to avoid ReferenceError
  const closeConnection = useCallback((isFinalClose: boolean = false) => {
    if (eventSourceManager.isConnected()) {
      if (isFinalClose || !graphEndReceivedRef.current) { 
        connectionClosedIntentionallyRef.current = true;
      }
      eventSourceManager.disconnect(isFinalClose);
      connectionManager.setLoading(false);
      console.log("SSE connection closed by client.");
    }
  }, [eventSourceManager, connectionManager]);

  // Helper functions for event listeners
  const handleNodeUpdate = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse node_update event data:", event.data, err);
      return;
    }
    console.log("SSE Event (node_update):", data);
    if (data.thread_id && !threadManager.getCurrentThreadId()) {
      console.log(`Setting thread_id: ${data.thread_id}`);
      threadManager.setThreadId(data.thread_id);
    }
    messageManager.addIntermediateStep(aiMessageId, {
      type: 'system_event',
      systemEventContent: `Processing step: ${data.node_name || 'Unknown step'}`,
      nodeName: data.node_name
    });
  }, [threadManager, messageManager]);

  const handleMessage = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse message event data:", event.data, err);
      return;
    }
    console.log("SSE Event (message):", data);
    if (data.type === 'tool_call') {
      messageManager.addIntermediateStep(aiMessageId, { type: 'tool_call', toolCalls: data.tool_calls });
    } else if (data.type === 'tool_result') {
      messageManager.addIntermediateStep(aiMessageId, { 
        type: 'tool_result', 
        toolName: data.name, 
        toolCallId: data.tool_call_id,
        toolResultContent: typeof data.content === 'string' ? data.content : JSON.stringify(data.content, null, 2),
        isError: data.is_error === true || (typeof data.content === 'string' && data.content.toLowerCase().includes('error'))
      });
    } else if (data.type === 'ai') {
      messageManager.updateAIMessage(aiMessageId, prev => ({
        ...prev,
        llmOutput: data.content,
        isStreaming: false
      }));
    }
  }, [messageManager]);

  const handleThoughtStream = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse thought_stream event data:", event.data, err);
      return;
    }
    console.log("SSE Event (thought_stream):", data.chunk);
    messageManager.updateThoughtChunk(aiMessageId, data.chunk);
  }, [messageManager]);

  const handleFinalAnswer = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse final_answer event data:", event.data, err);
      return;
    }
    console.log("SSE Event (final_answer):", data.answer);
    messageManager.updateAIMessage(aiMessageId, prev => ({
      ...prev,
      content: data.answer,
      isStreaming: false,
    }));
  }, [messageManager]);

  const handleGraphEnd = useCallback((aiMessageId: string, event: MessageEvent) => {
    console.log("SSE Event (graph_end) RECEIVED. Finalizing.");
    graphEndReceivedRef.current = true;
    connectionManager.setLoading(false);
    messageManager.updateAIMessage(aiMessageId, prev => ({...prev, isStreaming: false}));
    closeConnection(true);
  }, [graphEndReceivedRef, connectionManager, messageManager, closeConnection]);

  const handleError = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse error event data:", event.data, err);
      data = { message: "An error occurred with the AI agent (malformed error event)." };
    }
    console.error("SSE Event (backend error):", data);
    const errorMsgContent = data.message || "An error occurred with the AI agent.";
    connectionManager.setError(errorMsgContent);
    messageManager.addIntermediateStep(aiMessageId, { 
      type: 'error_event', 
      errorEventContent: errorMsgContent, 
      isError: true 
    });
    messageManager.updateAIMessage(aiMessageId, prev => ({
      ...prev, 
      isStreaming: false, 
      content: prev.content || "Error processing request."
    }));
    connectionManager.setLoading(false);
    closeConnection();
  }, [connectionManager, messageManager, closeConnection]);

  const handleCustomData = useCallback((aiMessageId: string, event: MessageEvent) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      console.error("Failed to parse custom_data event data:", event.data, err);
      return;
    }
    console.log("SSE Event (custom_data):", data);
    if (data.status && data.step && data.message) {
      messageManager.addIntermediateStep(aiMessageId, {
        type: 'system_event',
        systemEventContent: `[${data.step.toUpperCase()}] ${data.message}`,
        nodeName: data.step
      });
    } else {
      messageManager.addIntermediateStep(aiMessageId, {
        type: 'system_event',
        systemEventContent: `Custom: ${JSON.stringify(data)}`
      });
    }
  }, [messageManager]);

  const handleConnectionError = useCallback((aiMessageId: string, event: MessageEvent) => {
    if (graphEndReceivedRef.current || connectionClosedIntentionallyRef.current) {
      connectionManager.setLoading(false);
      return;
    }
    console.error("SSE connection error:", event);
    const errorContent = "Connection error with the AI agent. Please check your network or try again.";
    connectionManager.setError(errorContent);
    messageManager.addIntermediateStep(aiMessageId, { 
      type: 'error_event', 
      errorEventContent: errorContent 
    });
    messageManager.updateAIMessage(aiMessageId, prev => ({
      ...prev, 
      isStreaming: false, 
      content: prev.content || "Failed to get a response."
    }));
    connectionManager.setLoading(false);
    closeConnection();
  }, [graphEndReceivedRef, connectionClosedIntentionallyRef, connectionManager, messageManager, closeConnection]);

  // Refactored setupEventHandlers
  const setupEventHandlers = useCallback((aiMessageId: string) => {
    eventSourceManager.addEventListener('node_update', (event) => handleNodeUpdate(aiMessageId, event));
    eventSourceManager.addEventListener('message', (event) => handleMessage(aiMessageId, event));
    eventSourceManager.addEventListener('thought_stream', (event) => handleThoughtStream(aiMessageId, event));
    eventSourceManager.addEventListener('final_answer', (event) => handleFinalAnswer(aiMessageId, event));
    eventSourceManager.addEventListener('graph_end', (event) => handleGraphEnd(aiMessageId, event));
    eventSourceManager.addEventListener('error', (event) => handleError(aiMessageId, event));
    eventSourceManager.addEventListener('custom_data', (event) => handleCustomData(aiMessageId, event));
    eventSourceManager.addEventListener('connectionError', (event) => handleConnectionError(aiMessageId, event));
  }, [
    eventSourceManager,
    handleNodeUpdate,
    handleMessage,
    handleThoughtStream,
    handleFinalAnswer,
    handleGraphEnd,
    handleError,
    handleCustomData,
    handleConnectionError
  ]);

  const submitPrompt = useCallback(async (prompt: string, isNewConversation: boolean = false) => {
    if (eventSourceManager.isConnected()) {
      console.log("Closing existing SSE connection before starting new one.");
      closeConnection();
    }
    
    graphEndReceivedRef.current = false;
    connectionClosedIntentionallyRef.current = false;
    
    // Add user message and initialize AI message
    if (isNewConversation) {
      threadManager.generateNewThread();
      setChatHistory([]);
    }
    
    messageManager.addUserMessage(prompt);
    const aiMessageId = messageManager.initializeAIMessage();
    
    connectionManager.setLoading(true);
    connectionManager.setError(null);

    // Build URL with parameters
    const urlParams = new URLSearchParams({ query: prompt });
    
    const currentThreadId = threadManager.getCurrentThreadId();
    if (currentThreadId && !isNewConversation) {
      console.log(`Including thread_id in request: ${currentThreadId}`);
      urlParams.append('thread_id', currentThreadId);
    }
    
    if (userId) {
      urlParams.append('user_id', userId);
    }

    const url = `${apiUrl}?${urlParams.toString()}`;
    
    // Setup event handlers before connecting
    setupEventHandlers(aiMessageId);
    
    // Connect to SSE
    eventSourceManager.connect(url);
    console.log(`SSE connection opened to: ${url}`);
  }, [
    apiUrl, 
    userId, 
    eventSourceManager, 
    messageManager, 
    connectionManager, 
    threadManager, 
    closeConnection, 
    setupEventHandlers
  ]);

  useEffect(() => {
    return () => {
      closeConnection(true);
    };
  }, [closeConnection]);

  const startNewConversation = useCallback(() => {
    threadManager.generateNewThread();
    setChatHistory([]);
    connectionManager.setError(null);
    if (eventSourceManager.isConnected()) {
      closeConnection(true);
    }
  }, [threadManager, connectionManager, eventSourceManager, closeConnection]);

  return {
    chatHistory,
    isLoading,
    error,
    currentThreadId,
    submitPrompt,
    closeConnection,
    setChatHistory,
    startNewConversation,
    submitNewConversation: (prompt: string) => submitPrompt(prompt, true),
  };
}