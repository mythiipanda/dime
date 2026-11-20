import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from shared.sources import bbref_awards as src


def _without_lxml(monkeypatch):
    monkeypatch.setattr(src, "etree", None)
    monkeypatch.setattr(src, "lxml_html", None)


def test_document_reports_the_missing_dependency(monkeypatch):
    _without_lxml(monkeypatch)
    with pytest.raises(src.MissingDependencyError) as excinfo:
        src._document("<table></table>", "2023-24")
    assert "lxml" in str(excinfo.value)


def test_award_tables_reports_the_missing_dependency(monkeypatch):
    _without_lxml(monkeypatch)
    with pytest.raises(src.MissingDependencyError) as excinfo:
        src._award_tables(object())
    assert "lxml" in str(excinfo.value)


def test_parse_season_page_reports_the_missing_dependency(monkeypatch):
    _without_lxml(monkeypatch)
    with pytest.raises(src.MissingDependencyError) as excinfo:
        src.parse_season_page("<table></table>", 2024)
    assert "lxml" in str(excinfo.value)


def test_require_lxml_passes_when_lxml_is_installed():
    if src.etree is None or src.lxml_html is None:
        pytest.skip("lxml is not installed in this environment")
    src.require_lxml()
