import re
from datetime import UTC, datetime

import pytest

from v2.contracts import (Claim, ClaimKind, DraftReport, EntityRef,
                          EvidenceEnvelope, RunMode, SeasonRef, TaskSpec,
                          VerificationStatus)
from v2.runtime.verifier import verify_mechanical

_NUM = re.compile(
    r"(?<![A-Za-z])(?:20\d{2}-\d{2}|[-+]?\$?\d[\d,]*(?:\.\d+)?%?)")


def _walk(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    elif value is not None:
        yield value


def _canon(raw):
    text = str(raw).strip().replace(",", "").replace("$", "")
    out = {text.lower()}
    try:
        f = float(text.rstrip("%"))
    except ValueError:
        return out
    out |= {f"{f:g}", f"{f:.1f}", f"{f:.2f}"}
    if abs(f) <= 1:
        out |= {f"{f * 100:g}", f"{f * 100:.1f}", f"{f * 100:.2f}"}
    return {x.rstrip("0").rstrip(".") if "." in x else x for x in out}


def evidence_values(tables):
    values = set()
    for table in tables:
        for value in _walk(table):
            values |= _canon(value)
            if isinstance(value, str):
                for raw in _NUM.findall(value):
                    values |= _canon(raw)
    return values


def factual_numerals(text):
    vals = []
    for match in _NUM.finditer(text or ""):
        raw = match.group(0)
        if raw.isdigit() and match.end() < len(text) and text[match.end()] == ".":
            if match.start() == 0 or text[match.start() - 1] == "\n":
                continue
        vals.append(raw)
    return vals


def check_claim_grounding(text, tables, allow=None):
    supported = evidence_values(tables)
    allowed = {x for a in (allow or []) for x in _canon(a)}
    claims = factual_numerals(text)
    unsupported = []
    for claim in claims:
        forms = _canon(claim)
        if not (forms & supported or forms & allowed):
            unsupported.append(claim)
    return {
        "claims": len(claims),
        "supported": len(claims) - len(unsupported),
        "unsupported": unsupported,
        "coverage": (round((len(claims) - len(unsupported)) / len(claims), 3)
                     if claims else 1.0),
    }


def evidence_envelope(scenario_id, turns):
    return {
        "version": 1,
        "scenario_id": scenario_id,
        "turns": [{"tables": t.get("evidence_tables", []),
                   "tool_trace": t.get("tool_trace", [])} for t in turns],
    }


NUMERAL_TABLES = [{"rows": [{"PTS": 44}]}]
NUMERAL_ALLOW = ["2"]
NUMERAL_TEXT_45 = "He scored 45 in 2 games."
NUMERAL_TEXT_44 = "He scored 44 in 2 games."
PERCENT_TABLES = [{"rows": [{"PLAYER": "Luke Kennard", "FG3_PCT": 0.478,
                             "FG3M": 117, "FG3A": 245}],
                   "meta": {"season": "2025-26", "qualification": "82+ makes"}}]
PERCENT_TEXT = "In 2025-26 Kennard shot 47.8% (117 on 245); 82 makes required."


def _numeral_case(text, source):
    claim = Claim(text=text, kind=ClaimKind.OBSERVED, evidence_ids=["e"])
    return {
        "source": source,
        "text": text,
        "tables": NUMERAL_TABLES,
        "allow": NUMERAL_ALLOW,
        "task": TaskSpec(goal="State the scoring total.", mode=RunMode.QUICK,
                         deliverable="answer"),
        "draft": DraftReport(sections=[text], claims=[claim]),
        "evidence": [EvidenceEnvelope(
            evidence_id="e", capability="boxscore", source="fixture",
            observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
            rows=[{"PTS": 44}])],
    }


def _percent_case(source):
    claim = Claim(text=PERCENT_TEXT, kind=ClaimKind.OBSERVED, evidence_ids=["e"])
    return {
        "source": source,
        "text": PERCENT_TEXT,
        "tables": PERCENT_TABLES,
        "allow": None,
        "task": TaskSpec(
            goal="State the shooting line.", mode=RunMode.QUICK,
            deliverable="answer",
            entities=[EntityRef(id="LUK", type="player",
                                display_name="Luke Kennard")],
            season=SeasonRef(value="2025-26", source="user", confidence=1)),
        "draft": DraftReport(sections=[PERCENT_TEXT], claims=[claim]),
        "evidence": [EvidenceEnvelope(
            evidence_id="e", capability="boxscore", source="fixture",
            observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
            season="2025-26",
            entities=[EntityRef(id="LUK", type="player",
                                display_name="Luke Kennard")],
            rows=PERCENT_TABLES[0]["rows"],
            units={"FG3_PCT": "percent"},
            qualification=PERCENT_TABLES[0]["meta"]["qualification"])],
    }


def _equivalence(case):
    grounding = check_claim_grounding(case["text"], case["tables"], case["allow"])
    report = verify_mechanical(case["task"], case["draft"], case["evidence"],
                               (), allowed_constants=case["allow"] or ())
    product_repair = report.status == VerificationStatus.REPAIR
    grounding_unsupported = bool(grounding["unsupported"])
    return {
        "source": case["source"],
        "text": case["text"],
        "product_status": report.status.value,
        "product_repair": product_repair,
        "product_reasons": [r for cr in report.claim_results for r in cr.reasons],
        "grounding_coverage": grounding["coverage"],
        "grounding_unsupported": grounding["unsupported"],
        "grounding_unsupported_flag": grounding_unsupported,
        "divergence": product_repair != grounding_unsupported,
    }


def _fixture_cases():
    return [
        _numeral_case(NUMERAL_TEXT_45,
                      "test_benchmark_pack.py:119 flags invented number"),
        _numeral_case(NUMERAL_TEXT_44,
                      "test_benchmark_pack.py:119 substitute 44 for 45"),
        _percent_case("test_benchmark_pack.py:107 percent scaling"),
    ]


def test_benchmark_pack_line119_flags_uncited_45_product_repair_and_grounding_unsupported_agree():
    result = _equivalence(_numeral_case(
        NUMERAL_TEXT_45, "test_benchmark_pack.py:119 flags invented number"))
    assert check_claim_grounding(
        NUMERAL_TEXT_45, NUMERAL_TABLES, NUMERAL_ALLOW)["unsupported"] == ["45"]
    assert result["product_status"] == VerificationStatus.REPAIR.value
    assert any("uncited numeral 45" in reason
               for reason in result["product_reasons"])
    assert result["grounding_unsupported"] == ["45"]
    assert result["divergence"] is False


def test_benchmark_pack_line119_substitute_44_product_pass_and_grounding_coverage_1_agree():
    result = _equivalence(_numeral_case(
        NUMERAL_TEXT_44, "test_benchmark_pack.py:119 substitute 44 for 45"))
    assert check_claim_grounding(
        NUMERAL_TEXT_44, NUMERAL_TABLES, NUMERAL_ALLOW)["coverage"] == 1.0
    assert result["product_status"] == VerificationStatus.PASS.value
    assert result["grounding_unsupported"] == []
    assert result["divergence"] is False


def test_benchmark_pack_line107_percent_scaling_case_agrees_across_harnesses():
    result = _equivalence(_percent_case("test_benchmark_pack.py:107 percent scaling"))
    assert result["grounding_unsupported"] == []
    assert result["grounding_coverage"] == 1.0
    assert result["product_status"] == VerificationStatus.PASS.value
    assert result["divergence"] is False


def test_benchmark_pack_line126_evidence_envelope_excludes_answer_and_question_text():
    env = evidence_envelope("case", [{"text": "secret", "evidence_tables":
                                      [{"rows": [{"PTS": 33}]}],
                                      "tool_trace": [{"name": "get_x"}]}])
    raw = __import__("json").dumps(env)
    assert "secret" not in raw and "33" in raw and "get_x" in raw


def test_cross_harness_grounding_equivalence_ledger_over_all_fixture_rows():
    results = [_equivalence(case) for case in _fixture_cases()]
    lines = []
    for result in results:
        lines.append(
            f"{result['source']} | product={result['product_status']} | "
            f"repair={result['product_repair']} | "
            f"unsupported={result['grounding_unsupported']} | "
            f"coverage={result['grounding_coverage']} | "
            f"divergence={result['divergence']} | "
            f"reasons={result['product_reasons']}")
    ledger = "\n".join(lines)
    divergent = [r for r in results if r["divergence"]]
    assert not divergent, f"REPAIR !<=> unsupported != []:\n{ledger}"
    assert len(results) == 3
