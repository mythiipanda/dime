import { useSyncExternalStore } from "react";

let draft = "";
const listeners = new Set<() => void>();

function emit() {
  for (const listen of listeners) listen();
}

export function getComposerDraft(): string {
  return draft;
}

export function setComposerDraft(value: string): void {
  if (value === draft) return;
  draft = value;
  emit();
}

export function clearComposerDraft(): void {
  setComposerDraft("");
}

export function subscribeComposerDraft(listen: () => void): () => void {
  listeners.add(listen);
  return () => {
    listeners.delete(listen);
  };
}

export function useComposerDraft(): string {
  return useSyncExternalStore(subscribeComposerDraft, getComposerDraft, getComposerDraft);
}
