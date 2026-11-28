from analyst.tools.common import call_sync, disclose_scoped_season


class FakeTool:
    def __init__(self, result):
        self.result = result
        self.seen = None

    def invoke(self, args):
        self.seen = args
        return self.result


def test_args_single_season_injected_into_meta():
    tool = FakeTool({"tool": "x", "ok": True, "rows": [], "meta": {"source": "warehouse"}})
    out = call_sync(tool, "x", {"season": "1996-97"})
    assert out["meta"]["season"] == "1996-97"
    assert out["meta"]["source"] == "warehouse"


def test_meta_created_when_absent():
    tool = FakeTool({"tool": "x", "ok": True, "rows": []})
    out = call_sync(tool, "x", {"season": "1996-97"})
    assert out["meta"]["season"] == "1996-97"


def test_existing_declaration_wins():
    tool = FakeTool({"tool": "x", "ok": True, "rows": [], "meta": {"season": "1996-97"}})
    out = call_sync(tool, "x", {"season": "2024-25"})
    assert out["meta"]["season"] == "1996-97"


def test_distinct_range_endpoints_not_injected():
    tool = FakeTool({"tool": "x", "ok": True, "rows": []})
    out = call_sync(tool, "x", {"start_season": "1996-97", "end_season": "1997-98"})
    assert "season" not in out.get("meta", {})


def test_collapsing_range_endpoints_injected():
    tool = FakeTool({"tool": "x", "ok": True, "rows": []})
    out = call_sync(tool, "x", {"start_season": "1996-97", "end_season": "1996-97"})
    assert out["meta"]["season"] == "1996-97"


def test_failed_results_untouched():
    tool = FakeTool({"tool": "x", "ok": False, "error": "boom"})
    out = call_sync(tool, "x", {"season": "1996-97"})
    assert "season" not in out.get("meta", {})


def test_no_season_args_no_injection():
    tool = FakeTool({"tool": "x", "ok": True, "rows": []})
    out = call_sync(tool, "x", {"player": "Michael Jordan"})
    assert "season" not in out.get("meta", {})


def test_noncanonical_forms_canonicalized():
    out = disclose_scoped_season({"ok": True, "rows": []}, {"season": "1996-1997"})
    assert out["meta"]["season"] == "1996-97"
