
class _FakeCore:
    @staticmethod
    def rows():
        return [{
            "display_name": "Boston Celtics",
            "injuries": "[{'status': 'Day-To-Day', 'date': '2026-07-27T16:11Z', "
                        "'athlete': {'displayName': 'Jayson Tatum'}}]",
        }]

def test_named_player_filter_reads_nested_warehouse_injuries(monkeypatch):
    from shared.tools import league

    monkeypatch.setattr(
        league, "_warehouse_or_live",
        lambda *args, **kwargs: (_FakeCore.rows(), {"source": "warehouse"}),
    )
    monkeypatch.setattr("shared.tools._core.coerce_player_id", lambda value: 1628369)
    monkeypatch.setattr("shared.tools.gamelog.playoff_inactive_note",
                        lambda *args: None)
    monkeypatch.setattr("shared.tools.splits._resolve_name", lambda *args: "Jayson Tatum")

    result = league.get_injuries.invoke({
        "player": "Jayson Tatum", "season": "2025-26",
    })

    assert len(result["rows"]) == 1
    nested = result["rows"][0]["injuries"][0]
    assert nested["athlete"]["displayName"] == "Jayson Tatum"
    assert nested["date"] == "2026-07-27T16:11Z"
    assert "player_note" not in result

def test_nested_json_injuries_are_exported_as_structured_values(monkeypatch):
    from shared.tools import league

    monkeypatch.setattr(
        league, "_warehouse_or_live",
        lambda *args, **kwargs: ([{
            "display_name": "New York Knicks",
            "injuries": '[{"status":"Out","athlete":{"displayName":"Player X"}}]',
        }], {"source": "warehouse"}),
    )
    result = league.get_injuries.invoke({"team": "NYK", "season": "2025-26"})
    assert result["rows"][0]["injuries"] == [
        {"status": "Out", "athlete": {"displayName": "Player X"}},
    ]
