from v2.conversations import ConversationStore

def test_conversation_store_scopes_history_by_owner_and_bounds_context(tmp_path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    for index in range(6):
        store.append_exchange("browser-a", "thread", f"q{index}", f"a{index}")
    assert [turn.content for turn in store.read("browser-a", "thread")] == [
        "q2", "a2", "q3", "a3", "q4", "a4", "q5", "a5"]
    assert store.read("browser-b", "thread") == []
