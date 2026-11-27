import { listBoards, type Board } from "./boards";
import { fetchOwnedObject, mintObject, readTokenFor, updateObject } from "./objects-client";

const mappingKey = (localId: string) => `dime_board_object:${localId}`;

export function boardObjectMapping(localId: string): string | null {
  try {
    return window.localStorage.getItem(mappingKey(localId));
  } catch {
    return null;
  }
}

function retainMapping(localId: string, objectId: string) {
  try {
    window.localStorage.setItem(mappingKey(localId), objectId);
  } catch {}
}

export function clearMapping(localId: string) {
  try {
    window.localStorage.removeItem(mappingKey(localId));
  } catch {}
}

export function boardIntent(board: Board) {
  return {
    season: board.season,
    rows: board.rows.map((row) => ({ player_id: row.player_id })),
    columns: board.columns.map((column) => ({ metric_id: column.metric_id })),
    ...(board.template_id ? { template_id: board.template_id } : {}),
  };
}

function persistable(board: Board): boolean {
  return board.rows.length > 0 && board.columns.length > 0;
}

export async function syncBoardObject(board: Board): Promise<{ objectId: string; readToken: string } | null> {
  if (!persistable(board)) return null;
  const existing = boardObjectMapping(board.id);
  if (existing) {
    const updated = await updateObject(existing, { title: board.title, payload: boardIntent(board) });
    if (updated) {
      return { objectId: existing, readToken: "" };
    }
    clearMapping(board.id);
  }
  try {
    const minted = await mintObject("board", board.title, boardIntent(board));
    retainMapping(board.id, minted.object_id);
    return { objectId: minted.object_id, readToken: minted.read_token };
  } catch {
    return null;
  }
}

export async function archiveBoardObject(localId: string): Promise<void> {
  const objectId = boardObjectMapping(localId);
  if (!objectId) return;
  await updateObject(objectId, { archived: true });
  clearMapping(localId);
}

export async function boardShareToken(board: Board): Promise<{ objectId: string; readToken: string } | null> {
  const synced = await syncBoardObject(board);
  if (!synced) return null;
  if (synced.readToken) return synced;
  const cached = readTokenFor(synced.objectId);
  if (cached) return { objectId: synced.objectId, readToken: cached };
  const owned = await fetchOwnedObject(synced.objectId);
  return owned?.read_token ? { objectId: synced.objectId, readToken: owned.read_token } : null;
}

let started = false;
export function startBoardSync() {
  if (started || typeof window === "undefined") return;
  started = true;
  const reconcile = () => {
    const boards = listBoards();
    const localIds = new Set(boards.map((board) => board.id));
    for (const board of boards) {
      void syncBoardObject(board);
    }
    try {
      for (let index = 0; index < window.localStorage.length; index += 1) {
        const key = window.localStorage.key(index);
        if (!key?.startsWith("dime_board_object:")) continue;
        const localId = key.slice("dime_board_object:".length);
        if (!localIds.has(localId)) void archiveBoardObject(localId);
      }
    } catch {}
  };
  window.addEventListener("dime:boards", reconcile);
  reconcile();
}
