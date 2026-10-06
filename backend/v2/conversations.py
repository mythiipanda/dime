from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v2.contracts import ConversationTurn

_LOCKS_GUARD = Lock()
_LOCKS: dict[Path, Lock] = {}


def _path_lock(path: Path) -> Lock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(resolved, Lock())


class ConversationReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: str = Field(max_length=80)
    thread: str = Field(max_length=80)
    sequence: int = Field(ge=1)
    role: str = Field(max_length=16)
    run_id: str | None = Field(default=None, max_length=256)
    turn_id: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_reference(self) -> "ConversationReference":
        for name in ("owner", "thread", "role"):
            if not getattr(self, name).strip():
                raise ValueError(f"conversation reference {name} must be non-empty")
        if self.role not in ("user", "assistant"):
            raise ValueError("conversation reference role must be user or assistant")
        if (self.run_id is None) != (self.turn_id is None):
            raise ValueError("conversation reference run and turn travel together")
        if self.run_id is not None and not self.run_id.strip():
            raise ValueError("conversation reference run id must be non-empty")
        if self.turn_id is not None and not self.turn_id.strip():
            raise ValueError("conversation reference turn id must be non-empty")
        return self


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
            turn TEXT NOT NULL, run_id TEXT, turn_id TEXT,
            PRIMARY KEY(owner, thread, sequence))""")
        columns = {row[1] for row in con.execute("PRAGMA table_info(conversations)")}
        for column in ("run_id", "turn_id"):
            if column not in columns:
                con.execute(f"ALTER TABLE conversations ADD COLUMN {column} TEXT")
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

    def append_exchange(self, owner: str, thread: str, user: str, assistant: str,
                        *, run_id: str | None = None,
                        turn_id: str | None = None) -> None:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if (run_id is None) != (turn_id is None):
            raise ValueError("conversation run and turn travel together")
        if run_id is not None and not run_id.strip():
            raise ValueError("conversation run id must be non-empty")
        if turn_id is not None and not turn_id.strip():
            raise ValueError("conversation turn id must be non-empty")
        turns = (ConversationTurn(role="user", content=user),
                 ConversationTurn(role="assistant", content=assistant))
        with self._lock, self._connect() as con:
            start = con.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM conversations "
                "WHERE owner=? AND thread=?", (owner, thread)).fetchone()[0]
            con.executemany(
                "INSERT INTO conversations(owner,thread,sequence,turn,run_id,turn_id)"
                " VALUES(?,?,?,?,?,?)",
                [(owner, thread, start + index, turn.model_dump_json(),
                  run_id, turn_id)
                 for index, turn in enumerate(turns, 1)],
            )

    def references(self, owner: str, thread: str) -> list[ConversationReference]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT sequence, turn, run_id, turn_id FROM conversations "
                "WHERE owner=? AND thread=? ORDER BY sequence",
                (owner, thread)).fetchall()
        refs = []
        for sequence, raw, run_id, ledger_turn in rows:
            turn = ConversationTurn.model_validate_json(raw)
            refs.append(ConversationReference(
                owner=owner, thread=thread, sequence=sequence,
                role=turn.role, run_id=run_id, turn_id=ledger_turn))
        return refs

    def resolve_user_turns(self, owner: str, thread: str,
                           entries: Iterable[Any]) -> list[str]:
        from v2.runtime.ledger import LedgerKind

        records = list(entries)
        requests: dict[str, str] = {}
        for entry in records:
            if entry.kind == LedgerKind.TURN_START:
                if entry.turn_id in requests:
                    raise ValueError(
                        f"ledger repeats turn {entry.turn_id!r}")
                requests[entry.turn_id] = entry.data.get("request")
        resolved = []
        for ref in self.references(owner, thread):
            if ref.role != "user" or ref.turn_id is None:
                continue
            request = requests.get(ref.turn_id)
            if not isinstance(request, str) or not request:
                raise ValueError(
                    f"ledger holds no request for turn {ref.turn_id!r}")
            stored = self._stored_content(owner, thread, ref.sequence)
            if stored != request:
                raise ValueError(
                    f"conversation index disagrees with the log for turn "
                    f"{ref.turn_id!r}")
            resolved.append(request)
        return resolved

    def _stored_content(self, owner: str, thread: str, sequence: int) -> str:
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT turn FROM conversations WHERE owner=? AND thread=? "
                "AND sequence=?", (owner, thread, sequence)).fetchone()
        return ConversationTurn.model_validate_json(row[0]).content


__all__ = ["ConversationReference", "ConversationStore"]
