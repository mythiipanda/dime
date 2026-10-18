#!/usr/bin/env python3
"""Grade a final NBA analyst answer using grading_rubric.json.

Usage: python grade_answer.py <attempt_dir>
Reads <attempt_dir>/final_answer.md (or final_answer.txt) and prints a JSON report.
No evals are run; this only grades an existing artifact.
"""
import json
import os
import re
import sys
import glob

RUBRIC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grading_rubric.json")

TOKEN_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|\b\d+(?:\.\d+)?%?")


def load_rubric():
    with open(RUBRIC_PATH) as f:
        return json.load(f)

def find_answer(attempt_dir):
    for name in ("final_answer.md", "final_answer.txt", "answer.md", "answer.txt", "final.txt"):
        p = os.path.join(attempt_dir, name)
        if os.path.exists(p):
            with open(p) as f:
                return f.read(), name
    raise FileNotFoundError(f"No final answer file found in {attempt_dir}")

def collect_numbers(obj, acc):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_numbers(v, acc)

def load_evidence(attempt_dir):
    """Load evidence JSON files and return raw data + IDs."""
    ev_dir = os.path.join(attempt_dir, "evidence")
    files = sorted(glob.glob(os.path.join(ev_dir, "*.json")))
    evidence_data = []
    evidence_ids = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            evidence_data.append(data)
        except Exception:
            continue
        eid = os.path.splitext(os.path.basename(f))[0]
        evidence_ids.append(eid)
    return files, evidence_ids, evidence_data


def extract_sql_from_evidence(evidence_data):
    """Extract SQL queries from evidence JSON files."""
    queries = []
    for ev in evidence_data:
        args = ev.get("arguments", {})
        if isinstance(args, dict):
            q = args.get("sql") or args.get("query")
            if q and isinstance(q, str) and q.strip().upper().startswith(("SELECT", "WITH")):
                queries.append((ev.get("id", ""), q))
    return queries


def capability_calls(evidence_data):
    """Return (eid, capability_id, result) for every capability_execute record."""
    calls = []
    for ev in evidence_data:
        if ev.get("tool") != "capability_execute":
            continue
        args = ev.get("arguments")
        cap_id = ""
        if isinstance(args, dict):
            cap_id = args.get("capability_id") or args.get("tool") or ""
        cap_id = cap_id or ev.get("capability_id") or ""
        result = ev.get("result") if isinstance(ev.get("result"), dict) else {}
        calls.append((ev.get("id", ""), str(cap_id), result))
    return calls


def capability_result_rows(result):
    """Return the data rows a capability call produced, or None if it produced none."""
    if not isinstance(result, dict) or result.get("ok") is False:
        return None
    evidence = result.get("evidence")
    if isinstance(evidence, dict):
        rows = evidence.get("rows")
        if isinstance(rows, list):
            return rows
    rows = result.get("rows")
    if isinstance(rows, list):
        return rows
    return None


def capability_returned_data(result):
    """True when a capability call succeeded and returned at least one data row."""
    rows = capability_result_rows(result)
    if rows is not None:
        return len(rows) > 0
    # Envelopes without rows still count as data when they report success.
    return bool(isinstance(result, dict) and result.get("ok"))


def collect_capability_numbers(evidence_data):
    """Numbers read from capability_execute data rows.

    A capability result is warehouse-derived evidence (for example an official
    award ballot read verbatim from a table), so its numbers belong in the same
    pool the answer is matched against. Only data rows are collected; envelope
    scalars such as a row count or a declared maximum are skipped because they
    are not data values the answer is expected to restate."""
    nums = []
    for _eid, _cap, result in capability_calls(evidence_data):
        rows = capability_result_rows(result)
        if rows:
            collect_numbers(rows, nums)
    return nums


def usage_capability_calls(evidence_data, answer_text, answer_nums=None):
    """Capability calls the answer actually leans on, by cited id, name, or data.

    Citation is the strongest signal, but an answer often cites a follow-up
    query evidence id (say E6) while restating numbers the capability returned
    under a different id (E1). Link those calls by the numbers they produced so
    capability-grounded answers are not scored as if the capability was unused.
    """
    cap_calls = capability_calls(evidence_data)
    if not cap_calls:
        return []
    lower = answer_text.lower()
    cited_ids = set(re.findall(r"E\d+", answer_text))
    used = [(eid, cap, result) for (eid, cap, result) in cap_calls
            if eid and eid in cited_ids]
    if used:
        return used
    cap_ids = {cap for _eid, cap, _r in cap_calls if cap}
    mentioned = {cap for cap in cap_ids if cap.lower() in lower}
    used = [t for t in cap_calls if t[1] in mentioned]
    if used:
        return used
    if answer_nums:
        linked = []
        for eid, cap, result in cap_calls:
            rows = capability_result_rows(result)
            nums = []
            if rows:
                collect_numbers(rows, nums)
            if nums and any(fuzzy_match(n, an)
                            for n in nums for an in answer_nums):
                linked.append((eid, cap, result))
        if linked:
            return linked
    return []


def reexecute_queries(queries, warehouse_path):
    """Re-execute SQL queries against the warehouse and return result numbers."""
    import duckdb
    con = duckdb.connect(warehouse_path, read_only=True)
    warehouse_nums = []
    verified_queries = 0
    for eid, sql in queries:
        try:
            rows = con.execute(sql).fetchall()
            nums = []
            collect_numbers(rows, nums)
            warehouse_nums.extend(nums)
            verified_queries += 1
        except Exception:
            pass
    con.close()
    return warehouse_nums, verified_queries

def extract_answer_numbers(text):
    """Extract numeric tokens from the answer, filtering out non-factual numbers."""
    # Season spans (2023-24, 2024/25) are context labels, not claim values, so
    # drop them before tokenizing. Otherwise "2023-24" leaks a stray 24 into
    # the pool and depresses match rates.
    text = re.sub(r"\b\d{4}\s*[-/]\s*\d{2,4}\b", " ", text)
    # Evidence-id references (E6, e12) are citations, not claim numbers. Strip
    # them so the digits are not mistaken for values the answer reports.
    text = re.sub(r"\b[Ee]\d+\b", " ", text)
    # Match numbers including negative and percentage
    toks = re.findall(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\b|-?\d+(?:\.\d+)?%?\b", text)
    out = []
    for t in toks:
        is_pct = t.endswith("%")
        s = t.replace(",", "").rstrip("%")
        # Skip calendar years (1900-2100); keep 4-digit counts such as 1000.
        if re.match(r"^-?\d{4}$", s) and 1900 <= abs(int(s)) <= 2100:
            continue
        if re.match(r"^-?[eE]\d+$", s):
            continue
        try:
            val = float(s)
        except ValueError:
            continue
        if val == 0:
            continue
        out.append(val)
        # A percentage may be restated as its decimal fraction
        # (54.55% -> 0.5455). Only do this for real percentage tokens so plain
        # integers do not spawn a phantom fractional twin.
        if is_pct and 1 < val <= 100:
            out.append(val / 100.0)
    return out

def fuzzy_match(a, b, tol=0.01, rel=0.005):
    if abs(a - b) <= tol:
        return True
    if abs(b) > 1e-9 and abs(a - b) / abs(b) <= rel:
        return True
    return abs(a) < 1e-9 and abs(b) < 1e-9

def auto_score(answer_text, rubric, attempt_dir=None):
    dims = rubric["dimensions"]
    scores = {}
    lower = answer_text.lower()
    clarity = 2
    if "##" in answer_text or "#" in answer_text: clarity += 1
    if "|" in answer_text: clarity += 1
    if len(answer_text) > 200: clarity += 1
    scores["clarity"] = min(5, clarity)
    cites = len(re.findall(r"E\d+|evidence[_-]?\d+|query[_-]?\d+", answer_text))
    scores["citations"] = min(5, cites)
    edge_terms = ["uncertain", "sparse", "caveat", "note:", "limitation", "pre-2000", "small sample"]
    edge = sum(1 for t in edge_terms if t in lower)
    scores["edge_case_handling"] = min(5, edge)

    evidence_files, evidence_ids, evidence_data = [], [], []
    if attempt_dir is not None:
        evidence_files, evidence_ids, evidence_data = load_evidence(attempt_dir)

    ans_nums = extract_answer_numbers(answer_text)

    # --- Correctness: verify numbers against warehouse ---
    warehouse_nums = []
    verified_queries = 0
    warehouse_reachable = False
    warehouse_error = ""

    wh = os.environ.get(
        "DIME_WAREHOUSE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warehouse-owned.duckdb"),
    )
    try:
        queries = extract_sql_from_evidence(evidence_data)
        warehouse_nums, verified_queries = reexecute_queries(queries, wh)
        warehouse_reachable = True
    except Exception as e:
        warehouse_error = str(e)

    # Capability outputs are warehouse-derived too: a capability_execute result
    # (e.g. an official award ballot read verbatim) returns numbers a direct
    # SELECT cannot reproduce. Fold those numbers into the match pool whenever a
    # capability_execute call exists, regardless of which evidence id the answer
    # happens to cite, so a capability-grounded answer is judged against the
    # evidence it actually used.
    capability_nums = collect_capability_numbers(evidence_data)
    warehouse_nums.extend(capability_nums)

    # Which capability calls the answer rests on, and whether each succeeded
    # with data. A cited capability that errored or came back empty cannot
    # substantiate a numeric claim.
    cap_calls = capability_calls(evidence_data)
    used_cap_calls = usage_capability_calls(evidence_data, answer_text, ans_nums)
    capability_evidence_used = bool(used_cap_calls)
    capability_verified = bool(used_cap_calls) and all(
        capability_returned_data(result) for _eid, _cap, result in used_cap_calls)

    # Match answer numbers against warehouse query results
    # Use recall: for each unique warehouse number, check if a fuzzy match exists in answer
    # This avoids penalizing answers for mentioning correct numbers multiple times
    unique_wh = []
    for n in warehouse_nums:
        if not any(fuzzy_match(n, u) for u in unique_wh):
            unique_wh.append(n)

    # Check for disclosure/negative-finding language in the answer
    # When the model correctly identifies data is unavailable/not queryable,
    # the warehouse SELECT might still return rows (physical table exists
    # but is not in scope certificate). In this case, use citation coverage
    # + disclosure language as correctness proxy instead of numeric matching.
    has_disclosure = any(t in lower for t in [
        "not queryable", "not present", "not in catalog", "not in the queryable",
        "cannot compute", "cannot identify", "no data", "no mvp", "not available",
        "absent", "impossible", "not in the warehouse", "not in scope",
        "does not exist"
    ])
    has_schema_evidence = any(
        ev.get("type", "").startswith("schema") or
        (ev.get("arguments") and isinstance(ev["arguments"], dict) and
         ev["arguments"].get("table")) or
        (ev.get("action", "").startswith("schema"))
        for ev in evidence_data
    )
    # Also detect coverage evidence (which reports queryable vs non-queryable)
    has_coverage_evidence = any(
        ev.get("type", "").startswith("coverage") or
        ev.get("action", "").startswith("coverage") or
        (ev.get("result") and isinstance(ev.get("result"), dict) and
         "non_queryable_table_count" in str(ev.get("result", {})) or
         "queryable_table_count" in str(ev.get("result", {})))
        for ev in evidence_data
    )

    is_negative_finding = has_disclosure and (has_schema_evidence or has_coverage_evidence)

    if is_negative_finding:
        # For negative-finding tasks (data unavailable / not queryable),
        # use citation coverage + disclosure language as correctness proxy
        # rather than numeric matching (warehouse SELECT may return rows
        # from physical table even though table is not queryable)
        cited_ids = set(re.findall(r"E\d+", answer_text))
        if evidence_ids:
            coverage = len(cited_ids & set(evidence_ids)) / max(1, len(evidence_ids))
            has_caveat = any(t in lower for t in ["caveat", "uncertainty", "limitation"])
            if coverage >= 0.5 and (has_disclosure or has_caveat):
                match_rate = 0.8  # likely correct negative finding
            else:
                match_rate = coverage * 0.6
        else:
            match_rate = 1.0 if has_caveat else 0.5
        match_count = int(match_rate * len(ans_nums)) if ans_nums else 0
    elif unique_wh and ans_nums:
        matched_wh = 0
        for wn in unique_wh:
            if any(fuzzy_match(wn, an) for an in ans_nums):
                matched_wh += 1
        match_rate = matched_wh / len(unique_wh)
        match_count = matched_wh
    elif unique_wh and not ans_nums:
        # Warehouse has numbers but answer has none — full mismatch
        match_rate = 0.0
        match_count = 0
    elif verified_queries == 0 and not unique_wh:
        # No SQL queries to verify (e.g., schema/coverage/disclosure tasks)
        # Use citation coverage as proxy for correctness
        cited_ids = set(re.findall(r"E\d+", answer_text))
        if evidence_ids:
            coverage = len(cited_ids & set(evidence_ids)) / max(1, len(evidence_ids))
            # If answer cites most evidence and has caveat/disclosure, give benefit of doubt
            has_disclosure = any(t in lower for t in ["no", "not", "absent", "unavailable", "cannot", "impossible", "not present", "not in"])
            has_caveat = any(t in lower for t in ["caveat", "uncertainty", "limitation"])
            if coverage >= 0.5 and (has_disclosure or has_caveat):
                match_rate = 0.8  # likely correct negative finding
            else:
                match_rate = coverage * 0.6
        else:
            match_rate = 1.0 if has_caveat else 0.5
        match_count = int(match_rate * len(ans_nums)) if ans_nums else 0
    elif ans_nums:
        # Fallback: use evidence numbers directly
        evidence_nums = []
        for ev in evidence_data:
            collect_numbers(ev, evidence_nums)
        unique_ev = []
        for n in evidence_nums:
            if not any(fuzzy_match(n, u) for u in unique_ev):
                unique_ev.append(n)
        match_count = 0
        for wn in unique_ev:
            if any(fuzzy_match(wn, an) for an in ans_nums):
                match_count += 1
        match_rate = match_count / len(unique_ev) if unique_ev else 1.0
    else:
        match_rate = 1.0
        match_count = 0

    # Capability-grounded answers: score by how many of the answer's numbers the
    # capability actually returned. SQL re-execution can contribute unrelated
    # numbers (or none), and the capability envelope carries rows the answer was
    # never asked to restate, so recall against the whole pool understates
    # correctness. Precision over the answer's own numbers against the
    # capability pool is the fairer signal for these answers.
    if capability_nums and ans_nums and not is_negative_finding:
        unique_cap = []
        for n in capability_nums:
            if not any(fuzzy_match(n, u) for u in unique_cap):
                unique_cap.append(n)
        cap_matched_ans = sum(
            1 for an in ans_nums
            if any(fuzzy_match(cn, an) for cn in unique_cap))
        cap_answer_rate = cap_matched_ans / len(ans_nums)
        if cap_answer_rate > match_rate:
            match_rate = cap_answer_rate
            match_count = cap_matched_ans

    correctness = int(round(match_rate * 5))
    correctness = max(0, min(5, correctness))

    # Negative-finding proxy (schema/coverage-only evidence).
    # Queries may re-execute (schema/coverage/metadata) but yield no numeric
    # results, while the answer discloses the data is not queryable / not
    # available / not in scope / does not exist. Numeric warehouse matching
    # cannot apply here, so score the disclosure itself instead of 0:
    # warehouse_correctness = 0.8 proxy and correctness >= 4.
    disclosure_terms = ["not queryable", "not available", "not in scope",
                        "does not exist"]
    if (len(warehouse_nums) == 0
            and any(t in lower for t in disclosure_terms)):
        match_rate = 0.8
        correctness = max(correctness, 4)

    # Capability grounding check: when the answer rests on a capability_execute
    # result, that call must have succeeded and returned data. A cited
    # capability that errored or came back empty cannot substantiate a numeric
    # claim, so cap correctness rather than letting the number pool mask it.
    # A genuine absence the answer discloses is exempt (the empty result is the
    # finding, and the negative-finding proxy above already handles it).
    answer_discloses_absence = any(t in lower for t in [
        "not queryable", "not present", "not in catalog", "cannot compute",
        "no data", "not available", "absent", "does not exist", "not in scope",
    ])
    if (capability_evidence_used and not capability_verified
            and not answer_discloses_absence):
        match_rate = min(match_rate, 0.2)
        correctness = min(correctness, 1)
    scores["correctness"] = correctness

    distinct_cites = len(set(re.findall(r"E\d+", answer_text)))
    if evidence_ids:
        cited_ids = set(re.findall(r"E\d+", answer_text))
        coverage = len(cited_ids & set(evidence_ids)) / max(1, len(evidence_ids))
    else:
        coverage = 0.0
    if evidence_ids:
        completeness = int(round(coverage * 5))
    else:
        completeness = 3
    scores["completeness"] = max(0, min(5, completeness))

    scores["citations"] = min(5, max(scores["citations"], distinct_cites))
    if distinct_cites < 3 and evidence_ids:
        scores["citations"] = min(scores["citations"], 2)
    has_caveat = any(t in lower for t in ["caveat", "uncertainty", "limitation"])
    if not has_caveat:
        scores["edge_case_handling"] = min(scores["edge_case_handling"], 1)
    nums = re.findall(r"\b\d+(?:\.\d+)?%?\b", answer_text)
    report_extra = {"distinct_evidence_ids": distinct_cites, "numeric_token_count": len(nums),
                    "has_caveat_section": has_caveat,
                    "evidence_file_count": len(evidence_files),
                    "evidence_ids": evidence_ids,
                    "warehouse_number_count": len(warehouse_nums),
                    "answer_number_count": len(ans_nums),
                    "matched_number_count": match_count,
                    "match_rate": round(match_rate, 4),
                    "citation_coverage": round(coverage, 4),
                    "warehouse_correctness": round(match_rate, 4),
                    "warehouse_queries_re_executed": verified_queries,
                    "warehouse_reachable": warehouse_reachable,
                    "unique_warehouse_numbers": len(unique_wh),
                    "capability_call_count": len(cap_calls),
                    "capability_number_count": len(capability_nums),
                    "capability_evidence_used": capability_evidence_used,
                    "capability_verified": capability_verified,
    }
    wh = os.environ.get("DIME_WAREHOUSE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warehouse-owned.duckdb"))
    try:
        import duckdb
        con = duckdb.connect(wh, read_only=True)
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        con.close()
        report_extra["warehouse_reachable"] = True
        report_extra["warehouse_table_count"] = len(tables)
    except Exception as e:
        report_extra["warehouse_reachable"] = False
        report_extra["warehouse_error"] = str(e)
    total = 0.0
    for k, v in dims.items():
        total += (scores[k] / 5.0) * v["weight"]
    return scores, total, report_extra

def main():
    if len(sys.argv) < 2:
        print("Usage: python grade_answer.py <attempt_dir>")
        sys.exit(1)
    attempt_dir = sys.argv[1]
    rubric = load_rubric()
    text, name = find_answer(attempt_dir)
    scores, total, extra = auto_score(text, rubric, attempt_dir=attempt_dir)
    report = {
        "attempt_dir": attempt_dir,
        "answer_file": name,
        "scores": scores,
        "weighted_score": round(total, 4),
        "pass": total >= rubric["pass_threshold"],
        "pass_threshold": rubric["pass_threshold"],
        "checks": extra,
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
