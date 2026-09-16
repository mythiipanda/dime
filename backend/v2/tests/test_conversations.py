from v2.conversations import ConversationStore


def test_conversation_store_scopes_history_by_owner_and_bounds_context(tmp_path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    for index in range(6):
        store.append_exchange("browser-a", "thread", f"q{index}", f"a{index}")
    assert [turn.content for turn in store.read("browser-a", "thread")] == [
        "q2", "a2", "q3", "a3", "q4", "a4", "q5", "a5"]
    assert store.read("browser-b", "thread") == []


def test_quick_answer_requires_complete_nonblank_conversation_identity():
    import pytest
    from pydantic import ValidationError
    from v2.api.routes import QuickAnswerBody

    for payload in (
        {"q": "question", "thread": "thread"},
        {"q": "question", "client": "browser"},
        {"q": "question", "thread": " ", "client": "browser"},
    ):
        with pytest.raises(ValidationError):
            QuickAnswerBody.model_validate(payload)
