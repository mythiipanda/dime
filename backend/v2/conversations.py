from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from v2.contracts import ConversationTurn, EvidenceEnvelope

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


class SessionBranch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    branch_id: str = Field(max_length=64)
    owner: str = Field(max_length=80)
    thread: str = Field(max_length=80)
    parent_sequence: int = Field(ge=1)
    parent_run_id: str | None = Field(default=None, max_length=256)
    parent_turn_id: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def validate_branch(self) -> "SessionBranch":
        if not self.branch_id.strip():
            raise ValueError("branch id must be non-empty")
        if not self.owner.strip() or not self.thread.strip():
            raise ValueError("branch owner and thread must be non-empty")
        if (self.parent_run_id is None) != (self.parent_turn_id is None):
            raise ValueError("branch parent run and turn travel together")
        return self


class BranchReuse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    branch_id: str = Field(max_length=64)
    evidence_id: str = Field(max_length=256)
    parent_run_id: str | None = Field(default=None, max_length=256)
    parent_turn_id: str | None = Field(default=None, max_length=256)


class ReuseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reused: list[EvidenceEnvelope] = Field(default_factory=list)
    fresh_required: bool = False
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_decision(self) -> "ReuseDecision":
        if self.fresh_required and self.reused:
            raise ValueError("fresh execution cannot reuse evidence")
        return self


class StaleBranchEvidenceError(ValueError):
    pass


def _canonical_rows(rows: Any) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)


def _rows_hash(rows: Any) -> str:
    return hashlib.sha256(_canonical_rows(rows).encode()).hexdigest()


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
        con.execute("""CREATE TABLE IF NOT EXISTS branches (
            owner TEXT NOT NULL, thread TEXT NOT NULL, branch_id TEXT NOT NULL,
            parent_sequence INTEGER NOT NULL,
            parent_run_id TEXT, parent_turn_id TEXT,
            PRIMARY KEY(owner, thread, branch_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS branch_evidence (
            owner TEXT NOT NULL, thread TEXT NOT NULL, branch_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL, envelope TEXT NOT NULL, rows_hash TEXT NOT NULL,
            PRIMARY KEY(owner, thread, branch_id, evidence_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS branch_reuses (
            owner TEXT NOT NULL, thread TEXT NOT NULL, branch_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            parent_run_id TEXT, parent_turn_id TEXT,
            PRIMARY KEY(owner, thread, branch_id, evidence_id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS turn_evidence (
            owner TEXT NOT NULL, thread TEXT NOT NULL, sequence INTEGER NOT NULL,
            evidence_id TEXT NOT NULL, envelope TEXT NOT NULL, rows_hash TEXT NOT NULL,
            PRIMARY KEY(owner, thread, sequence, evidence_id))""")
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

    def create_branch(self, owner: str, thread: str, parent_sequence: int,
                        *, branch_id: str | None = None) -> SessionBranch:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if isinstance(parent_sequence, bool) or not isinstance(parent_sequence, int):
            raise TypeError("branch parent sequence must be an integer")
        if parent_sequence < 1:
            raise ValueError("branch parent sequence must be positive")
        if branch_id is not None:
            if not isinstance(branch_id, str) or not branch_id.strip():
                raise ValueError("branch id must be non-empty")
            branch_id = branch_id.strip()[:64]
        else:
            branch_id = f"br-{uuid.uuid4().hex[:12]}"
        with self._lock, self._connect() as con:
            parent = con.execute(
                "SELECT run_id, turn_id FROM conversations "
                "WHERE owner=? AND thread=? AND sequence=?",
                (owner, thread, parent_sequence)).fetchone()
            if parent is None:
                raise ValueError(
                    f"branch parent sequence {parent_sequence} is missing "
                    f"for thread {thread!r}")
            exists = con.execute(
                "SELECT 1 FROM branches WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id)).fetchone()
            if exists is not None:
                raise ValueError(f"duplicate branch id: {branch_id}")
            con.execute(
                "INSERT INTO branches(owner, thread, branch_id, parent_sequence, "
                "parent_run_id, parent_turn_id) VALUES(?,?,?,?,?,?)",
                (owner, thread, branch_id, parent_sequence, parent[0], parent[1]))
        return SessionBranch(branch_id=branch_id, owner=owner, thread=thread,
                             parent_sequence=parent_sequence,
                             parent_run_id=parent[0], parent_turn_id=parent[1])

    def list_branches(self, owner: str, thread: str) -> list[SessionBranch]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT branch_id, parent_sequence, parent_run_id, parent_turn_id "
                "FROM branches WHERE owner=? AND thread=? ORDER BY rowid",
                (owner, thread)).fetchall()
        return [SessionBranch(branch_id=row[0], owner=owner, thread=thread,
                              parent_sequence=row[1],
                              parent_run_id=row[2], parent_turn_id=row[3])
                for row in rows]

    def get_branch(self, owner: str, thread: str,
                   branch_id: str) -> SessionBranch | None:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if not isinstance(branch_id, str) or not branch_id.strip():
            raise ValueError("branch id must be non-empty")
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT parent_sequence, parent_run_id, parent_turn_id FROM branches "
                "WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id.strip())).fetchone()
        if row is None:
            return None
        return SessionBranch(branch_id=branch_id.strip(), owner=owner, thread=thread,
                             parent_sequence=row[0],
                             parent_run_id=row[1], parent_turn_id=row[2])

    def attach_branch_evidence(self, owner: str, thread: str, branch_id: str,
                               envelopes: Iterable[EvidenceEnvelope]) -> list[str]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if not isinstance(branch_id, str) or not branch_id.strip():
            raise ValueError("branch id must be non-empty")
        branch_id = branch_id.strip()
        items = [EvidenceEnvelope.model_validate(
            item.model_dump() if isinstance(item, EvidenceEnvelope) else item)
            for item in envelopes]
        with self._lock, self._connect() as con:
            parent = con.execute(
                "SELECT 1 FROM branches WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id)).fetchone()
            if parent is None:
                raise ValueError(f"branch {branch_id!r} is missing")
            stored = con.execute(
                "SELECT evidence_id, rows_hash FROM branch_evidence "
                "WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id)).fetchall()
            seen_ids = {row[0] for row in stored}
            seen_hashes = {row[1] for row in stored}
            batch_ids: set[str] = set()
            batch_hashes: set[str] = set()
            for item in items:
                digest = _rows_hash(item.rows)
                if (item.evidence_id in seen_ids or item.evidence_id in batch_ids):
                    raise ValueError(
                        f"duplicate branch evidence id: {item.evidence_id}")
                if digest in seen_hashes or digest in batch_hashes:
                    raise ValueError(
                        f"duplicate branch evidence rows: {item.evidence_id}")
                batch_ids.add(item.evidence_id)
                batch_hashes.add(digest)
                con.execute(
                    "INSERT INTO branch_evidence(owner, thread, branch_id, "
                    "evidence_id, envelope, rows_hash) VALUES(?,?,?,?,?,?)",
                    (owner, thread, branch_id, item.evidence_id,
                     item.model_dump_json(), digest))
        return [item.evidence_id for item in items]

    def branch_evidence(self, owner: str, thread: str,
                        branch_id: str) -> list[EvidenceEnvelope]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if not isinstance(branch_id, str) or not branch_id.strip():
            raise ValueError("branch id must be non-empty")
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT envelope FROM branch_evidence "
                "WHERE owner=? AND thread=? AND branch_id=? ORDER BY evidence_id",
                (owner, thread, branch_id.strip())).fetchall()
        return [EvidenceEnvelope.model_validate_json(row[0]) for row in rows]

    def record_branch_reuse(self, owner: str, thread: str, branch_id: str,
                            evidence_ids: Iterable[str]) -> list[BranchReuse]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if not isinstance(branch_id, str) or not branch_id.strip():
            raise ValueError("branch id must be non-empty")
        branch_id = branch_id.strip()
        ids = list(evidence_ids)
        if any(not isinstance(item, str) or not item.strip() for item in ids):
            raise ValueError("reused evidence ids must be non-empty")
        if len(ids) != len(set(ids)):
            raise ValueError("reused evidence ids must not contain duplicates")
        with self._lock, self._connect() as con:
            branch = con.execute(
                "SELECT parent_run_id, parent_turn_id FROM branches "
                "WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id)).fetchone()
            if branch is None:
                raise ValueError(f"branch {branch_id!r} is missing")
            attached = {row[0] for row in con.execute(
                "SELECT evidence_id FROM branch_evidence "
                "WHERE owner=? AND thread=? AND branch_id=?",
                (owner, thread, branch_id)).fetchall()}
            missing = sorted(set(ids) - attached)
            if missing:
                raise ValueError(f"branch holds no evidence ids: {missing}")
            for evidence_id in ids:
                con.execute(
                    "INSERT OR IGNORE INTO branch_reuses(owner, thread, branch_id, "
                    "evidence_id, parent_run_id, parent_turn_id) "
                    "VALUES(?,?,?,?,?,?)",
                    (owner, thread, branch_id, evidence_id, branch[0], branch[1]))
        return [BranchReuse(branch_id=branch_id, evidence_id=item,
                            parent_run_id=branch[0], parent_turn_id=branch[1])
                for item in ids]

    def branch_reuses(self, owner: str, thread: str,
                      branch_id: str) -> list[BranchReuse]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if not isinstance(branch_id, str) or not branch_id.strip():
            raise ValueError("branch id must be non-empty")
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT evidence_id, parent_run_id, parent_turn_id FROM branch_reuses "
                "WHERE owner=? AND thread=? AND branch_id=? ORDER BY evidence_id",
                (owner, thread, branch_id.strip())).fetchall()
        return [BranchReuse(branch_id=branch_id.strip(), evidence_id=row[0],
                            parent_run_id=row[1], parent_turn_id=row[2])
                for row in rows]

    def reuse_branch_evidence(
        self, owner: str, thread: str, branch_id: str,
        fetch_current_rows: Mapping[str, Any] | Callable[[str], Any],
    ) -> list[EvidenceEnvelope]:
        stored = self.branch_evidence(owner, thread, branch_id)
        if not stored:
            raise ValueError(f"branch {branch_id.strip()!r} holds no evidence")
        resolved: list[EvidenceEnvelope] = []
        for item in stored:
            if isinstance(fetch_current_rows, Mapping):
                if item.evidence_id not in fetch_current_rows:
                    raise ValueError(
                        f"warehouse holds no rows for reused evidence "
                        f"{item.evidence_id}")
                current = fetch_current_rows[item.evidence_id]
            else:
                current = fetch_current_rows(item.evidence_id)
            if _rows_hash(current) != _rows_hash(item.rows):
                raise StaleBranchEvidenceError(
                    f"stale reused evidence {item.evidence_id}: "
                    f"warehouse rows changed")
            resolved.append(item)
        self.record_branch_reuse(owner, thread, branch_id,
                                 [item.evidence_id for item in resolved])
        return resolved

    def decide_followup_reuse(
        self, owner: str, thread: str, branch_id: str,
        current_entities: Iterable[tuple[str, str]],
        fetch_current_rows: Mapping[str, Any] | Callable[[str], Any],
    ) -> ReuseDecision:
        from v2.contracts import canonical_entity_ref

        wanted = {(str(item[0]), str(item[1])) for item in current_entities}
        stored = self.branch_evidence(owner, thread, branch_id)
        have: set[tuple[str, str]] = set()
        for item in stored:
            for entity in item.entities:
                have.add(canonical_entity_ref(entity))
        uncovered = sorted(wanted - have)
        if uncovered:
            return ReuseDecision(reused=[], fresh_required=True,
                                 reason="followup names entities the branch holds "
                                 f"no evidence for: {uncovered}")
        reused = self.reuse_branch_evidence(owner, thread, branch_id,
                                            fetch_current_rows)
        return ReuseDecision(
            reused=reused, fresh_required=False,
            reason=f"reused {len(reused)} admitted evidence ids from the parent turn")

    def record_turn_evidence(self, owner: str, thread: str, sequence: int,
                               envelopes: Iterable[EvidenceEnvelope]) -> list[str]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise TypeError("turn sequence must be an integer")
        if sequence < 1:
            raise ValueError("turn sequence must be positive")
        items = [EvidenceEnvelope.model_validate(
            item.model_dump() if isinstance(item, EvidenceEnvelope) else item)
            for item in envelopes]
        with self._lock, self._connect() as con:
            turn = con.execute(
                "SELECT 1 FROM conversations "
                "WHERE owner=? AND thread=? AND sequence=?",
                (owner, thread, sequence)).fetchone()
            if turn is None:
                raise ValueError(
                    f"turn sequence {sequence} is missing for thread {thread!r}")
            stored = con.execute(
                "SELECT evidence_id, rows_hash FROM turn_evidence "
                "WHERE owner=? AND thread=? AND sequence=?",
                (owner, thread, sequence)).fetchall()
            seen_ids = {row[0] for row in stored}
            seen_hashes = {row[1] for row in stored}
            batch_ids: set[str] = set()
            batch_hashes: set[str] = set()
            for item in items:
                digest = _rows_hash(item.rows)
                if item.evidence_id in seen_ids or item.evidence_id in batch_ids:
                    raise ValueError(
                        f"duplicate turn evidence id: {item.evidence_id}")
                if digest in seen_hashes or digest in batch_hashes:
                    raise ValueError(
                        f"duplicate turn evidence rows: {item.evidence_id}")
                batch_ids.add(item.evidence_id)
                batch_hashes.add(digest)
                con.execute(
                    "INSERT INTO turn_evidence(owner, thread, sequence, "
                    "evidence_id, envelope, rows_hash) VALUES(?,?,?,?,?,?)",
                    (owner, thread, sequence, item.evidence_id,
                     item.model_dump_json(), digest))
        return [item.evidence_id for item in items]

    def turn_evidence(self, owner: str, thread: str,
                      sequence: int) -> list[EvidenceEnvelope]:
        owner = self._identity(owner, "conversation owner")
        thread = self._identity(thread, "conversation thread")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise TypeError("turn sequence must be an integer")
        with self._lock, self._connect() as con:
            rows = con.execute(
                "SELECT envelope FROM turn_evidence "
                "WHERE owner=? AND thread=? AND sequence=? ORDER BY evidence_id",
                (owner, thread, sequence)).fetchall()
        return [EvidenceEnvelope.model_validate_json(row[0]) for row in rows]

    def _stored_content(self, owner: str, thread: str, sequence: int) -> str:
        with self._lock, self._connect() as con:
            row = con.execute(
                "SELECT turn FROM conversations WHERE owner=? AND thread=? "
                "AND sequence=?", (owner, thread, sequence)).fetchone()
        return ConversationTurn.model_validate_json(row[0]).content


__all__ = ["BranchReuse", "ConversationReference", "ConversationStore",
           "ReuseDecision", "SessionBranch", "StaleBranchEvidenceError"]
