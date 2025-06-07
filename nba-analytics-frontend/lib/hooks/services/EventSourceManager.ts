/**
 * EventSource manager implementation.
 * Following Single Responsibility Principle (SRP).
 */

import { IEventSourceManager } from '../interfaces';

export class EventSourceManager implements IEventSourceManager {
  private eventSource: EventSource | null = null;
  private eventHandlers: Map<string, (event: MessageEvent) => void> = new Map();

  connect(url: string): void {
    if (this.eventSource) {
      this.disconnect();
    }

    this.eventSource = new EventSource(url);
    
    this.eventSource.onopen = () => {
      console.log("SSE connection established.");
    };

    this.eventSource.onerror = (event) => {
      console.error("SSE generic connection error (.onerror):", event);
      const errorHandler = this.eventHandlers.get('connectionError');
      if (errorHandler) {
        errorHandler(event as MessageEvent);
      }
    };

    // Set up event listeners for registered handlers
    this.eventHandlers.forEach((handler, eventType) => {
      if (eventType !== 'connectionError' && this.eventSource) {
        this.eventSource.addEventListener(eventType, handler);
      }
    });
  }

  disconnect(isFinalClose: boolean = false): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      console.log("SSE connection closed by client.");
    }
  }

  addEventListener(eventType: string, handler: (event: MessageEvent) => void): void {
    this.eventHandlers.set(eventType, handler);
    
    if (this.eventSource && eventType !== 'connectionError') {
      this.eventSource.addEventListener(eventType, handler);
    }
  }

  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }
}