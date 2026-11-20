import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _flatten(node):
    if isinstance(node, dict):
        parts = []
        for key, value in node.items():
            if key in {
                "kind", "title", "subtitle", "description", "name", "label",
                "labels", "columns", "legend", "source", "units", "unit",
                "format", "encoding", "x_axis", "y_axis", "x_label", "y_label",
            }:
                continue
            parts.extend(_flatten(value))
        return parts
    if isinstance(node, (list, tuple)):
        parts = []
        for item in node:
            parts.extend(_flatten(item))
        return parts
    return [str(node)] if node is not None else []


def _numbers(text):
    return [float(m) for m in re.findall(r"-?\d+\.?\d*", text)]


HEADLINE = {"months": 7.0, "games": 82.0, "first_efg": 0.463671,
            "last_efg": 0.502232, "first_tov": 16.5, "last_tov": 13.0}


def test_chart_payload_carries_headline_numbers():
    chart = {
        "kind": "chart",
        "title": "DET 2021-22 monthly ball security",
        "unit": "rate",
        "xLabels": ["2021-10", "2021-11", "2021-12", "2022-01", "2022-02", "2022-03", "2022-04"],
        "series": [
            {"name": "eFG%", "values": [0.463671, 0.4901, 0.4852, 0.4788, 0.4910, 0.5023, 0.502232]},
            {"name": "TOV/g", "values": [16.5, 15.2, 14.8, 14.1, 13.9, 13.4, 13.0]},
        ],
        "footnote": "7 months · 82 games · eFG 0.463671 → 0.502232 · TOV/g 16.5 → 13.0",
    }
    payload_numbers = _numbers(" ".join(_flatten(chart)))
    for name, target in HEADLINE.items():
        assert any(abs(v - target) <= 0.0005 for v in payload_numbers), \
            f"{name}={target} missing inside chart payload"


def test_table_payload_carries_headline_numbers():
    table = {
        "kind": "table",
        "title": "DET 2021-22 monthly ball security",
        "columns": [
            {"key": "month", "label": "Month"},
            {"key": "games", "label": "G", "numeric": True},
            {"key": "fga", "label": "FGA", "numeric": True},
            {"key": "efg", "label": "eFG%", "numeric": True},
            {"key": "tov", "label": "TOV/g", "numeric": True},
        ],
        "rows": [
            {"month": "2021-10", "games": 6, "fga": 552, "efg": 0.463671, "tov": 16.5},
            {"month": "2022-04", "games": 9, "fga": 760, "efg": 0.502232, "tov": 13.0},
            {"month": "Season totals", "games": 82, "fga": 6720,
             "efg": 0.4880, "tov": 14.4},
            {"month": "Months covered", "games": 7, "fga": None,
             "efg": None, "tov": None},
        ],
    }
    payload_numbers = _numbers(" ".join(_flatten(table)))
    for name, target in HEADLINE.items():
        assert any(abs(v - target) <= 0.0005 for v in payload_numbers), \
            f"{name}={target} missing inside table payload"


def test_series_alone_does_not_carry_counts():
    series_only = {
        "kind": "chart",
        "title": "DET 2021-22 monthly ball security",
        "series": [
            {"name": "eFG%", "values": [0.463671, 0.4901, 0.4852, 0.4788, 0.4910, 0.5023, 0.502232]},
        ],
    }
    payload_numbers = _numbers(" ".join(_flatten(series_only)))
    assert not any(abs(v - 7.0) <= 0.0005 for v in payload_numbers)
    assert not any(abs(v - 82.0) <= 0.0005 for v in payload_numbers)


def test_flatten_matches_eval_serialization():
    artifacts = [
        {"kind": "chart", "footnote": "7 months, 82 games", "series": [{"name": "a", "values": [1.0]}]},
        {"kind": "table", "rows": [{"months": 7, "games": 82}]},
    ]
    text = json.dumps(artifacts)
    assert _numbers(text)
    assert any(abs(v - 7.0) < 1e-9 for v in _numbers(" ".join(_flatten(artifacts[0]))))
    assert any(abs(v - 82.0) < 1e-9 for v in _numbers(" ".join(_flatten(artifacts[1]))))
