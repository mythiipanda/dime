/**
 * Thread manager implementation.
 * Following Single Responsibility Principle (SRP).
 */

import { useRef } from 'react';
import { IThreadManager } from '../interfaces';

export class ThreadManager implements IThreadManager {
  private setCurrentThreadId: React.Dispatch<React.SetStateAction<string | null>>;
  private threadIdRef: React.MutableRefObject<string | null>;

  constructor(
    setCurrentThreadId: React.Dispatch<React.SetStateAction<string | null>>,
    threadIdRef: React.MutableRefObject<string | null>
  ) {
    this.setCurrentThreadId = setCurrentThreadId;
    this.threadIdRef = threadIdRef;
  }

  getCurrentThreadId(): string | null {
    return this.threadIdRef.current;
  }

  setThreadId(threadId: string | null): void {
    this.threadIdRef.current = threadId;
    this.setCurrentThreadId(threadId);
  }

  generateNewThread(): void {
    this.setThreadId(null);
  }
}