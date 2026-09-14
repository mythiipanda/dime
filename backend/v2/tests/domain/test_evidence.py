from datetime import datetime

import pytest

from v2.contracts import EvidenceEnvelope
from v2.domain.evidence import EvidenceIndex


def envelope(evidence_id: str, *, lineage=(), rows=None):
    return EvidenceEnvelope(evidence_id=evidence_id, capability="test", source="fixture",
        observed_at=datetime(2026, 9, 14), rows=rows or [{"PTS": 10}], lineage=list(lineage))


def test_index_resolves_nested_values_and_ancestors():
    index = EvidenceIndex([envelope("raw", rows={"teams": [{"PTS": 10}]}),
                           envelope("derived", lineage=["raw"])])
    assert index.ancestors("derived") == {"raw"}
    assert [(v.path, v.value) for v in index.values(["raw"])] == [("rows.teams[0].PTS", 10)]


@pytest.mark.parametrize("items, message", [
    ([envelope("same"), envelope("same")], "unique"),
    ([envelope("child", lineage=["missing"])], "unknown evidence lineage"),
    ([envelope("a", lineage=["b"]), envelope("b", lineage=["a"])], "acyclic"),
])
def test_index_rejects_invalid_lineage(items, message):
    with pytest.raises(ValueError, match=message):
        EvidenceIndex(items)
