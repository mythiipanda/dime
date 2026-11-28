import { BACKEND } from "./chat";
import { getClientId } from "./api";

export interface MintedObject {
  object_id: string;
  read_token: string;
  owner_token: string;
}

export function ownerTokenFor(objectId: string): string | null {
  try {
    return window.localStorage.getItem(`dime_object_token:${objectId}`);
  } catch {
    return null;
  }
}

export function readTokenFor(objectId: string): string | null {
  try {
    return window.localStorage.getItem(`dime_object_rtoken:${objectId}`);
  } catch {
    return null;
  }
}

function retainReadToken(objectId: string, readToken: string) {
  try {
    window.localStorage.setItem(`dime_object_rtoken:${objectId}`, readToken);
  } catch {}
}

export async function fetchOwnedObject(objectId: string): Promise<{ read_token?: string } | null> {
  const token = ownerTokenFor(objectId);
  if (!token) return null;
  try {
    const response = await fetch(`${BACKEND}/api/objects/${encodeURIComponent(objectId)}`, {
      headers: { "x-dime-owner": getClientId(), "x-owner-token": token },
    });
    if (!response.ok) return null;
    return await response.json().catch(() => null);
  } catch {
    return null;
  }
}

function retainOwnerToken(objectId: string, ownerToken: string) {
  try {
    window.localStorage.setItem(`dime_object_token:${objectId}`, ownerToken);
  } catch {}
}

export async function mintObject(kind: string, title: string, payload: unknown): Promise<MintedObject> {
  const response = await fetch(`${BACKEND}/api/objects`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-dime-owner": getClientId() },
    body: JSON.stringify({ kind, title, payload }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body?.object_id || !body?.read_token || !body?.owner_token) throw new Error("mint failed");
  retainOwnerToken(body.object_id, body.owner_token);
  retainReadToken(body.object_id, body.read_token);
  return body as MintedObject;
}

export async function updateObject(objectId: string, patch: { title?: string; payload?: unknown; archived?: boolean }): Promise<boolean> {
  const token = ownerTokenFor(objectId);
  if (!token) return false;
  try {
    const response = await fetch(`${BACKEND}/api/objects/${encodeURIComponent(objectId)}`, {
      method: "PATCH",
      headers: { "content-type": "application/json", "x-dime-owner": getClientId(), "x-owner-token": token },
      body: JSON.stringify(patch),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export function shareLink(readToken: string): string {
  return `${window.location.origin}/s/${readToken}`;
}
