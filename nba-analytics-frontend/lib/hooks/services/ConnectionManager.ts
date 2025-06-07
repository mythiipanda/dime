/**
 * Connection manager implementation.
 * Following Single Responsibility Principle (SRP).
 */

import { useState } from 'react';
import { IConnectionManager } from '../interfaces';

export class ConnectionManager implements IConnectionManager {
  private setIsLoadingState: React.Dispatch<React.SetStateAction<boolean>>;
  private setErrorState: React.Dispatch<React.SetStateAction<string | null>>;
  private isLoading: boolean = false;
  private error: string | null = null;

  constructor(
    setIsLoading: React.Dispatch<React.SetStateAction<boolean>>,
    setError: React.Dispatch<React.SetStateAction<string | null>>
  ) {
    this.setIsLoadingState = setIsLoading;
    this.setErrorState = setError;
  }

  setLoading(loading: boolean): void {
    this.isLoading = loading;
    this.setIsLoadingState(loading);
  }

  setError(error: string | null): void {
    this.error = error;
    this.setErrorState(error);
  }

  getLoadingState(): boolean {
    return this.isLoading;
  }

  getErrorState(): string | null {
    return this.error;
  }

  clearError(): void {
    this.setErrorState(null);
    this.error = null;
  }
}