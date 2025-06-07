/**
 * Message manager implementation.
 * Following Single Responsibility Principle (SRP).
 */

import { useState } from 'react';
import { IMessageManager, FrontendChatMessage, IntermediateStep } from '../interfaces';

export class MessageManager implements IMessageManager {
  private setChatHistory: React.Dispatch<React.SetStateAction<FrontendChatMessage[]>>;
  private currentAIMessageId: string | null = null;
  private currentThoughtChunkId: string | null = null;

  constructor(setChatHistory: React.Dispatch<React.SetStateAction<FrontendChatMessage[]>>) {
    this.setChatHistory = setChatHistory;
  }

  addUserMessage(content: string): void {
    const userMsgId = this.generateId('user');
    const userMessage: FrontendChatMessage = {
      id: userMsgId,
      type: 'human',
      content,
    };

    this.setChatHistory(prev => [...prev, userMessage]);
  }

  initializeAIMessage(): string {
    const aiMsgId = this.generateId('ai');
    const initialAIMessage: FrontendChatMessage = {
      id: aiMsgId,
      type: 'ai',
      content: '',
      intermediateSteps: [],
      isStreaming: true,
    };

    this.currentAIMessageId = aiMsgId;
    this.currentThoughtChunkId = null;
    this.setChatHistory(prev => [...prev, initialAIMessage]);
    
    return aiMsgId;
  }

  updateAIMessage(messageId: string, updater: (prev: FrontendChatMessage) => FrontendChatMessage): void {
    this.setChatHistory(prev => 
      prev.map(msg => msg.id === messageId ? updater(msg) : msg)
    );
  }

  addIntermediateStep(messageId: string, step: Omit<IntermediateStep, 'id' | 'timestamp'>): void {
    const newStep: IntermediateStep = {
      ...step,
      id: this.generateId('step'),
      timestamp: Date.now(),
    };

    this.updateAIMessage(messageId, prevMessage => ({
      ...prevMessage,
      intermediateSteps: [...(prevMessage.intermediateSteps || []), newStep],
    }));

    // Track current thought chunk for accumulation
    if (newStep.type === 'thought_chunk') {
      this.currentThoughtChunkId = newStep.id;
    } else {
      this.currentThoughtChunkId = null;
    }
  }

  updateThoughtChunk(messageId: string, chunk: string): void {
    if (!this.currentThoughtChunkId) {
      this.addIntermediateStep(messageId, {
        type: 'thought_chunk',
        thoughtChunkContent: chunk
      });
      return;
    }

    this.updateAIMessage(messageId, prevMsg => ({
      ...prevMsg,
      intermediateSteps: (prevMsg.intermediateSteps || []).map(step =>
        step.id === this.currentThoughtChunkId
          ? { ...step, thoughtChunkContent: (step.thoughtChunkContent || '') + chunk }
          : step
      ),
      isStreaming: true,
    }));
  }

  getChatHistory(): FrontendChatMessage[] {
    // Note: In the actual hook, this will be handled by React state
    // This is a placeholder for interface compliance
    return [];
  }

  clearHistory(): void {
    this.setChatHistory([]);
    this.currentAIMessageId = null;
    this.currentThoughtChunkId = null;
  }

  getCurrentAIMessageId(): string | null {
    return this.currentAIMessageId;
  }

  private generateId(prefix: string): string {
    return `${Date.now()}-${prefix}-${Math.random().toString(36).substring(7)}`;
  }
}