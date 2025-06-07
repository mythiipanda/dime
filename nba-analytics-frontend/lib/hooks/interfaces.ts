/**
 * Interfaces for the chat hook components.
 * Following Interface Segregation Principle (ISP).
 */

import React from 'react';

export interface IntermediateStep {
  id: string;
  type: 'tool_call' | 'tool_result' | 'system_event' | 'thought_chunk' | 'error_event';
  timestamp: number;
  toolCalls?: Array<{ name: string; args: Record<string, any>; id: string }>;
  toolName?: string;
  toolCallId?: string;
  toolResultContent?: string;
  systemEventContent?: string;
  nodeName?: string;
  thoughtChunkContent?: string;
  errorEventContent?: string;
  isError?: boolean;
}

export interface FrontendChatMessage {
  id: string;
  type: 'human' | 'ai';
  content?: string;
  isStreaming?: boolean;
  intermediateSteps?: IntermediateStep[];
  llmOutput?: string | object;
}

export interface AgentSSEHookOptions {
  apiUrl: string;
  threadId?: string;
  userId?: string;
}

export interface IEventSourceManager {
  connect(url: string): void;
  disconnect(isFinalClose?: boolean): void;
  addEventListener(eventType: string, handler: (event: MessageEvent) => void): void;
  isConnected(): boolean;
}

export interface IMessageManager {
  addUserMessage(content: string): void;
  initializeAIMessage(): string;
  updateAIMessage(messageId: string, updater: (prev: FrontendChatMessage) => FrontendChatMessage): void;
  addIntermediateStep(messageId: string, step: Omit<IntermediateStep, 'id' | 'timestamp'>): void;
  getChatHistory(): FrontendChatMessage[];
  clearHistory(): void;
}

export interface IConnectionManager {
  setLoading(loading: boolean): void;
  setError(error: string | null): void;
  getLoadingState(): boolean;
  getErrorState(): string | null;
}

export interface IThreadManager {
  getCurrentThreadId(): string | null;
  setThreadId(threadId: string | null): void;
  generateNewThread(): void;
}

export interface IChatHookReturn {
  chatHistory: FrontendChatMessage[];
  isLoading: boolean;
  error: string | null;
  currentThreadId: string | null;
  submitPrompt: (prompt: string, isNewConversation?: boolean) => Promise<void>;
  closeConnection: (isFinalClose?: boolean) => void;
  setChatHistory: React.Dispatch<React.SetStateAction<FrontendChatMessage[]>>;
  startNewConversation: () => void;
  submitNewConversation: (prompt: string) => Promise<void>;
}