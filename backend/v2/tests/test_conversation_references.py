from __future__ import annotations

import pytest

from v2.conversations import ConversationStore
from v2.runtime.ledger import LedgerKind, RunLedger


def _ledger_with_turns() -> RunLedger:
    ledger = RunLedger("run")
    for turn_id, request in (("t1", "ask-one"), ("t2", "ask-two")):
        ledger.append(
            LedgerKind.TURN_START, turn_id=turn_id, data={"request": request},
        )
        ledger.append(
            LedgerKind.TURN_END, turn_id=turn_id, data={"reason": "complete"},
        )
    return ledger


def test_append_exchange_stores_a_ledger_reference(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one", run_id="run", turn_id="t1")
    refs = store.references("o", "t")
    assert [(ref.role, ref.run_id, ref.turn_id) for ref in refs] == [
        ("user", "run", "t1"),
        ("assistant", "run", "t1"),
    ]


def test_conversation_resolves_user_content_from_the_ledger_alone(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one", run_id="run", turn_id="t1")
    store.append_exchange("o", "t", "ask-two", "a-two", run_id="run", turn_id="t2")
    ledger = _ledger_with_turns()
    resolved = store.resolve_user_turns("o", "t", ledger.entries)
    assert resolved == ["ask-one", "ask-two"]


def test_conversation_reference_mismatch_fails_loudly_naming_the_turn(
    tmp_path,
) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one", run_id="run", turn_id="t1")
    ledger = RunLedger("run")
    ledger.append(LedgerKind.TURN_START, turn_id="t1", data={"request": "other"})
    ledger.append(LedgerKind.TURN_END, turn_id="t1", data={"reason": "complete"})
    with pytest.raises(ValueError, match="t1"):
        store.resolve_user_turns("o", "t", ledger.entries)


def test_legacy_rows_without_references_still_read(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one")
    assert [turn.content for turn in store.read("o", "t")] == ["ask-one", "a-one"]
    assert store.references("o", "t")[0].run_id is None
