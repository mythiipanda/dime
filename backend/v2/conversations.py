from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from v2.contracts import ConversationTurn

_LOCKS_GUARD = Lock()
_LOCKS: dict[Path, Lock] = {}


def _path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(resolved, Lock())


class ConversationStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = _path_lock(self._path)
        self._reject_symlinks()

    def _reject_symlinks(self) -> None:
        if self._path.is_symlink():
            raise ValueError("conversation store cannot be a symlink")
        if any(part.is_symlink() for part in (self._path.parent, *self._path.parent.parents)):
            raise ValueError("conversation store parent cannot be a symlink")
        for suffix in ("-journal", "-wal", "-shm"):
            if Path(f"{self._path}{suffix}").is_symlink():
                raise ValueError("conversation store auxiliary file cannot be a symlink")

    def _connect(self) -> sqlite3.Connection:
        self._reject_symlinks()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._path, timeout=10)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""CREATE TABLE IF NOT EXISTS conversations (
            owner TEXT NOT NULL, thread TEXT NOT NULL, sequence INTEGER NOT NULL,
            turn TEXT NOT NULL, PRIMARY KEY(owner, thread, sequence))""")
        return con

    @staticmethod
    def _identity(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be non-empty")
        return value[:80]

    def read(self, owner: str, thread: str, limit: int = 8) -> list[ConversationTurn]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        limit = min(8, max(1, int(limit)))
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT turn FROM conversations WHERE owner=? AND thread=? "
                "ORDER BY sequence DESC LIMIT ?", (owner, thread, limit)).fetchall()
        return [ConversationTurn.model_validate_json(row[0]) for row in reversed(rows)]

    def append_exchange(self, owner: str, thread: str, user: str, assistant: str) -> None:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        turns = (ConversationTurn(role="user", content=user),
                 ConversationTurn(role="assistant", content=assistant))
        with self._lock, self._connect() as con:
            start = con.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM conversations "
                "WHERE owner=? AND thread=?", (owner, thread)).fetchone()[0]
            con.executemany(
                "INSERT INTO conversations(owner,thread,sequence,turn) VALUES(?,?,?,?)",
                [(owner, thread, start + index, turn.model_dump_json())
                 for index, turn in enumerate(turns, 1)],
            )


__all__ = ["ConversationStore"]
