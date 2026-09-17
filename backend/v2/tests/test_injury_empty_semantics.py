import pytest


def test_team_injury_impact_source_encodes_empty_report_as_unknown():
    from pathlib import Path
    source = Path("backend/app/tools/team.py").read_text()
    assert 'availability_known = bool(out or questionable)' in source
    assert '"low" if availability_known else "unknown"' in source
    assert "empty injury rows do not establish" in source


def test_injury_adapter_preserves_empty_team_report_limitation():
    from v2.adapters import call_capability
    from v2.adapters.tests.test_adapters import FakeTool

    payload = {"tool": "get_injuries", "ok": True, "rows": [],
               "meta": {"source": "fixture", "season": "2025-26",
                        "warning": "empty team or league injury report does not establish universal availability"}}
    envelope = call_capability(
        "injuries", {"team": "CLE", "season": "2025-26"},
        tools={"get_injuries": FakeTool(payload)},
    )
    assert any("empty team or league injury report" in warning
               for warning in envelope.warnings)
    assert "empty result set" in envelope.warnings
