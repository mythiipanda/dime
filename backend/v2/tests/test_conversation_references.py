from __future__ import annotations

import pytest

from v2.conversations import ConversationStore


def test_append_exchange_stores_a_ledger_reference(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one", run_id="run", turn_id="t1")
    refs = store.references("o", "t")
    assert [(ref.role, ref.run_id, ref.turn_id) for ref in refs] == [
        ("user", "run", "t1"),
        ("assistant", "run", "t1"),
    ]


def test_legacy_rows_without_references_still_read(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.append_exchange("o", "t", "ask-one", "a-one")
    assert [turn.content for turn in store.read("o", "t")] == ["ask-one", "a-one"]
    assert store.references("o", "t")[0].run_id is None
