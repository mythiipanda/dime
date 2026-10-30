from __future__ import annotations
from v2.runtime import presentation

import json

def _parse_status_texts(text: str) -> list[str]:
    out: list[str] = []
    for chunk in text.split("\n\n"):
        if not chunk.startswith("event: status\n"):
            continue
        payload = chunk.split("data: ", 1)[1]
        out.append(json.loads(payload)["text"])
    return out


def test_status_lines_for_phrase_keeps_base_without_doubling() -> None:
    from v2 import contracts
    from v2.api import routes

    task = contracts.TaskSpec(
        goal="Q6 check",
        mode="quick",
        deliverable="answer",
        season=contracts.SeasonRef(value="2024-25", source="user", confidence=1.0),
        requirements=[
            contracts.EvidenceRequirement(
                id="r1",
                description="Points for the starters last season",
                capability_options=["qualified_leaders"],
                capability_arguments={},
            )
        ],
    )
    lines = presentation._status_lines(task)
    assert lines == [
        "Checking Points for the starters last for 2024-25…",
        "Comparing Points for the starters last across 2024-25…",
        "Verifying every number…",
    ]
    assert "for for" not in " ".join(lines).lower()
