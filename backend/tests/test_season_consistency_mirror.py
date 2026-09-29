
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "season_consistency_mirror.json"


def _load():
    data = json.loads(FIXTURE.read_text())
    assert "header" in data and "cases" in data
    return data


def test_fixture_has_source_attribution():
    data = _load()
    header = data["header"]
    assert "dime-internal" in header["canonical_source"]
    assert header["canonical_sha"]
    assert header["generated"]
    assert any("2024-25" in r for r in header["rules"])


def test_cases_well_formed():
    data = _load()
    ids = [c["id"] for c in data["cases"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 10
    for c in data["cases"]:
        assert c["metric"] in ("season_consistency", "numeric_acc")
        assert isinstance(c["facts"], dict)
        assert isinstance(c["answer"], str) and c["answer"]
        assert isinstance(c["expected"], (int, float))


def test_wrong_season_verdicts_are_zero():
    data = _load()
    by_id = {c["id"]: c for c in data["cases"]}
    assert by_id["numeric_wrong_season_number"]["expected"] == 0.0
    assert by_id["numeric_right_number_wrong_season_phrasing"]["expected"] == 0.0
    assert by_id["consistency_wrong_season"]["expected"] == 0.0


def test_no_penalty_without_season_claim():
    data = _load()
    by_id = {c["id"]: c for c in data["cases"]}
    assert by_id["consistency_no_mention"]["expected"] == 1.0
    assert by_id["numeric_no_season_mention"]["expected"] == 1.0
    assert by_id["consistency_no_season_label"]["expected"] == 1.0


def _local_scorer_source():
    for cand in (
        os.environ.get("DIME_INTERNAL", ""),
        str(Path.home() / "workspace" / "dime-internal"),
    ):
        if not cand:
            continue
        p = Path(cand) / "evals" / "dimebench" / "scoring.py"
        if p.is_file():
            return p.read_text()
    return None


def _fetch_pinned_scorer(sha):
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import (  # noqa: E402
            add_surrogate_to_request, read_json_response)
    except ImportError:
        return None
    url = ("https://api.github.com/repos/mythiipanda/dime-internal"
           f"/git/blobs/{sha}")
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/vnd.github+json")
        add_surrogate_to_request(req, "custom.github",
                                 allowed_hosts=("api.github.com",))
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = read_json_response(resp)
    except Exception:
        return None
    if data.get("sha") != sha:
        return None
    return base64.b64decode(data["content"]).decode("utf-8")


def _hermetic_fallback_scorer():
    _SEASON_RE = re.compile(r"(20\d\d)\s*[-–—]\s*(\d{2,4})")

    def _canon(raw: str) -> str:
        raw = raw.replace("–", "-").replace("—", "-")
        m = re.match(r"(20\d\d)\s*-\s*(\d{2,4})", raw)
        return f"{m.group(1)}-{m.group(2)[-2:]}"

    def _named(answer: str) -> set:
        return {_canon(f"{a}-{b}") for a, b in _SEASON_RE.findall(answer)}

    def _gate(facts: dict, answer: str, numeric_only: bool) -> bool:
        season = facts.get("season")
        if not season:
            return False
        nums = [v for k, v in facts.items()
                if k != "season" and isinstance(v, (int, float))]
        if numeric_only and not nums:
            return False
        named = _named(answer)
        return bool(named) and _canon(season) not in named

    def season_consistency(facts: dict, answer: str) -> float:
        return 0.0 if _gate(facts, answer, numeric_only=False) else 1.0

    def numeric_acc(facts: dict, answer: str) -> float:
        nums = [v for k, v in facts.items()
                if k != "season" and isinstance(v, (int, float))]
        if not nums:
            return 1.0
        if _gate(facts, answer, numeric_only=True):
            return 0.0
        for v in nums:
            if not re.search(r"(?<!\d)" + re.escape(str(v)) + r"(?!\d)",
                             answer):
                return 0.0
        return 1.0

    return {"season_consistency": season_consistency,
            "numeric_acc": numeric_acc,
            "__source__": "hermetic-fallback"}


def _canonical_scorer(header):
    src = _local_scorer_source() or _fetch_pinned_scorer(
        header["canonical_sha"])
    if src is not None:
        ns: dict = {}
        exec(compile(src, "dimebench/scoring.py", "exec"), ns)
        return ns, ("local-dime-internal" if _local_scorer_source()
                    else "pinned-blob")
    return _hermetic_fallback_scorer(), "hermetic-fallback"


def test_expected_outputs_match_canonical_scorer():
    data = _load()
    scorer, source = _canonical_scorer(data["header"])
    canonical = source != "hermetic-fallback"
    print(f"\n[season_consistency_mirror] scorer source: {source} "
          f"({'CANONICAL' if canonical else 'FALLBACK-ONLY'})")
    for c in data["cases"]:
        fn = scorer.get(c["metric"])
        assert callable(fn), f"canonical scorer has no {c['metric']}"
        got = fn(c["facts"], c["answer"])
        assert got == c["expected"], (
            f"{c['id']}: {source} {c['metric']} returned {got}, "
            f"fixture expects {c['expected']}")
    if not canonical:
        pytest.skip(
            "fallback-only: canonical scorer unreachable "
            "(no dime-internal checkout, pinned blob fetch failed); "
            "verdicts match the hermetic port of the documented rules "
            "but this does NOT verify against the canonical scorer and "
            "cannot detect canonical drift")
