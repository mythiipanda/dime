def test_strip_view_context_removes_machine_envelope():
    from shared.store.chat_runs import strip_view_context
    wire = '<dime-context kind="matchup">\n{"summary":"s","entities":{}}\n</dime-context>\n\nWho has the edge?'
    assert strip_view_context(wire) == "Who has the edge?"
    assert strip_view_context("plain question") == "plain question"
    assert strip_view_context("<dime-context broken") == "<dime-context broken"
