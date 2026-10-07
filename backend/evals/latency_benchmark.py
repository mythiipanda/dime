import argparse
import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

DEFAULT_CHAT_URL = "https://dime-backend.jollybeach-4dab2707.eastus.azurecontainerapps.io/api/v2/chat/stream"
DEFAULT_TIMEOUT = 60.0
CLIENT_HEADER_VALUE = "latency-benchmark"
REL_TOL = 1e-4
ABS_TOL = 1e-9
REQUEST_PAUSE_S = 1.0
CONSECUTIVE_ERROR_LIMIT = 5
REGRESSION_EXIT = 1
INFRA_EXIT = 2

NUMBER_RE = re.compile(r"(?<!\w)[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:%)?(?!\w)")
SEASON_RE = re.compile(r"\b\d{4}\s*[-/\u2013\u2014]\s*\d{2,4}\b")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
WHITESPACE_RE = re.compile(r"\s+")
TRAILING_PUNCT_RE = re.compile(r"[.!?\u201d\u2019]+$")

TOOL_RESULT = "tool_result"
TOOL_CALL = "tool_call"
FINAL_ANSWER = "final_answer"
ERROR_EVENT = "error"


def percentile(values, pct):
    items = sorted(values)
    if not items:
        return None
    if len(items) == 1:
        return round(float(items[0]), 9)
    rank = (pct / 100.0) * (len(items) - 1)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return round(float(items[low]), 9)
    frac = rank - low
    return round(float(items[low] + frac * (items[high] - items[low])), 9)


def extract_numbers(text):
    cleaned = SEASON_RE.sub(" ", text if isinstance(text, str) else "")
    cleaned = YEAR_RE.sub(" ", cleaned)
    out = []
    for match in NUMBER_RE.finditer(cleaned):
        raw = match.group(0)
        core = raw[:-1] if raw.endswith("%") else raw
        core = core.replace(",", "")
        if core in ("", "+", "-", ".", "+.", "-."):
            continue
        try:
            out.append(float(core))
        except ValueError:
            continue
    return out


def _normalize_text(value):
    collapsed = WHITESPACE_RE.sub(" ", value.strip()).casefold()
    return TRAILING_PUNCT_RE.sub("", collapsed)


def _looks_numeric(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return bool(extract_numbers(value))
    return False


def score_golden(expected, answer_text):
    if _looks_numeric(expected):
        truth = extract_numbers(str(expected))
        if not truth:
            return False
        claimed = extract_numbers(answer_text)
        return any(
            math.isclose(number, truth[0], rel_tol=REL_TOL, abs_tol=ABS_TOL)
            for number in claimed
        )
    return _normalize_text(str(expected)) == _normalize_text(answer_text if isinstance(answer_text, str) else "")


def _parse_block(event_type, data_lines):
    out = []
    for data in data_lines:
        if data == "[DONE]":
            continue
        try:
            item = json.loads(data)
        except ValueError:
            continue
        if isinstance(item, dict):
            out.append((event_type, item))
    return out


def parse_sse_events(text):
    events = []
    event_type = None
    data_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            events.extend(_parse_block(event_type, data_lines))
            event_type = None
            data_lines = []
        elif stripped.startswith("event:"):
            event_type = stripped[len("event:"):].strip() or None
        elif stripped.startswith("data:"):
            data_lines.append(stripped[len("data:"):].strip())
    events.extend(_parse_block(event_type, data_lines))
    return events


def _frame_text(data):
    text = data.get("text")
    return text if isinstance(text, str) and text else None


def _run_id_of(data):
    run_id = data.get("run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    carry = data.get("carry")
    if isinstance(carry, dict):
        inner = carry.get("run_id")
        if isinstance(inner, str) and inner:
            return inner
    return None


def summarize_frames(frames):
    ttft = None
    answer = None
    error = None
    durations = {}
    saw_tool = False
    saw_timing = False
    fallback_parts = []
    legacy_parts = []
    for elapsed, event_type, data in frames:
        if not isinstance(data, dict):
            continue
        text = _frame_text(data)
        if text is not None and ttft is None:
            ttft = elapsed
        if event_type == ERROR_EVENT:
            message = data.get("message")
            if error is None:
                error = message if isinstance(message, str) and message else "sse error"
            continue
        if event_type in (TOOL_CALL, TOOL_RESULT):
            saw_tool = True
        if event_type == TOOL_RESULT:
            ms = data.get("ms")
            if isinstance(ms, (int, float)) and not isinstance(ms, bool):
                name = data.get("name")
                key = name if isinstance(name, str) and name else "unknown"
                durations[key] = round(durations.get(key, 0.0) + ms / 1000.0, 6)
                saw_timing = True
        if event_type == FINAL_ANSWER and text is not None:
            answer = text
        elif text is not None and _run_id_of(data) is not None and "node" not in data:
            legacy_parts.append(text)
        elif event_type is None and text is not None and "node" not in data:
            fallback_parts.append(text)
    if answer is None:
        answer = "".join(legacy_parts) if legacy_parts else "".join(fallback_parts)
    if not frames:
        error = "empty stream"
    tool_status = "measured" if (saw_tool or saw_timing) else "unavailable"
    return {
        "answer_text": answer if answer is not None else "",
        "ttft_s": ttft,
        "tool_durations": durations,
        "tool_status": tool_status,
        "error": error,
    }


def build_scoreboard(records):
    ok = [r for r in records if r.get("error") is None]
    totals = [r["total_s"] for r in ok if r.get("total_s") is not None]
    ttfts = [r["ttft_s"] for r in ok if r.get("ttft_s") is not None]
    per_tool = {}
    for record in ok:
        for name, seconds in (record.get("tool_durations") or {}).items():
            per_tool.setdefault(name, []).append(seconds)
    tool_p95 = {name: percentile(values, 95) for name, values in per_tool.items()}
    tool_p95 = {name: value for name, value in tool_p95.items() if value is not None}
    top_tool = None
    top_tool_p95 = None
    if tool_p95:
        top_tool = max(tool_p95, key=lambda name: tool_p95[name])
        top_tool_p95 = tool_p95[top_tool]
    measured = [r["cost_usd"] for r in ok if r.get("cost_status") == "measured" and r.get("cost_usd") is not None]
    estimated = [r["cost_usd"] for r in ok if r.get("cost_status") == "estimated" and r.get("cost_usd") is not None]
    if measured:
        cost_per_query = sum(measured) / len(measured)
        cost_status = "measured"
    elif estimated:
        cost_per_query = sum(estimated) / len(estimated)
        cost_status = "estimated"
    else:
        cost_per_query = None
        cost_status = "unavailable"
    grades = [r["golden_correct"] for r in ok if r.get("golden_correct") is not None]
    return {
        "n": len(records),
        "p50_total_s": percentile(totals, 50),
        "p95_total_s": percentile(totals, 95),
        "p95_ttft_s": percentile(ttfts, 95),
        "top_tool": top_tool,
        "top_tool_p95_s": top_tool_p95,
        "cost_usd_per_query": cost_per_query,
        "cost_status": cost_status,
        "golden_acc": (sum(1 for g in grades if g) / len(grades)) if grades else None,
        "errors": len(records) - len(ok),
    }


def baseline_medians(runs):
    medians = {}
    for key in ("p50_total_s", "p95_total_s", "p95_ttft_s", "golden_acc"):
        values = [r["scoreboard"][key] for r in runs if r["scoreboard"].get(key) is not None]
        medians[key] = percentile(values, 50)
    return medians


def check_regression(baseline, candidate, threshold_pct):
    medians = baseline["medians"]
    reasons = []
    for key in ("p50_total_s", "p95_total_s", "p95_ttft_s"):
        base = medians.get(key)
        value = candidate.get(key)
        if base is None or value is None or base <= 0:
            continue
        if value > base * (1.0 + threshold_pct / 100.0):
            reasons.append(key + " regressed: " + _fmt(value) + " vs baseline " + _fmt(base))
    base_acc = medians.get("golden_acc")
    cand_acc = candidate.get("golden_acc")
    if base_acc is not None and cand_acc is not None:
        if cand_acc < base_acc - threshold_pct / 100.0:
            reasons.append("golden_acc regressed: " + _fmt(cand_acc) + " vs baseline " + _fmt(base_acc))
    return ("REGRESSION", reasons) if reasons else ("PASS", [])


def _fmt(value):
    return repr(round(value, 4))


def clean_proxy_env(env):
    out = {}
    for key, value in env.items():
        if key in ("NO_PROXY", "no_proxy") and isinstance(value, str):
            out[key] = ",".join(
                part for part in value.split(",") if not part.strip().startswith("[")
            )
        else:
            out[key] = value
    return out


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _default_questions_path():
    return str(Path(__file__).with_name("latency_golden.jsonl"))


def _default_out_dir():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return str(Path(__file__).with_name("runs") / stamp)


def _default_baseline_path():
    return str(Path(__file__).with_name("latency-baseline.json"))


def load_questions(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError("line " + str(lineno) + ": invalid JSON") from exc
            for key in ("task_id", "question"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError("line " + str(lineno) + ": " + key + " must be a non-empty string")
            answer = row.get("answer")
            if isinstance(answer, bool) or not isinstance(answer, (int, float, str)):
                raise ValueError("line " + str(lineno) + ": answer must be a number or string")
            if isinstance(answer, str) and not answer.strip():
                raise ValueError("line " + str(lineno) + ": answer must be a non-empty string")
            rows.append(row)
    return rows


def _headers(api_key):
    headers = {"x-dime-client": CLIENT_HEADER_VALUE}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    return headers


def stream_frames(client, url, headers, timeout, question):
    frames = []
    start = time.monotonic()
    event_type = None
    data_lines = []
    with client.stream("GET", url, params={"q": question}, headers=headers, timeout=timeout) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            stripped = line.strip()
            if not stripped:
                for parsed in _parse_block(event_type, data_lines):
                    frames.append((time.monotonic() - start, parsed[0], parsed[1]))
                event_type = None
                data_lines = []
            elif stripped.startswith("event:"):
                event_type = stripped[len("event:"):].strip() or None
            elif stripped.startswith("data:"):
                data_lines.append(stripped[len("data:"):].strip())
    for parsed in _parse_block(event_type, data_lines):
        frames.append((time.monotonic() - start, parsed[0], parsed[1]))
    return frames


def run_question(client, url, headers, timeout, row):
    record = {
        "task_id": row["task_id"],
        "question": row["question"],
        "expected": row["answer"],
        "answer_text": "",
        "total_s": None,
        "ttft_s": None,
        "tool_durations": {},
        "tool_status": "unavailable",
        "golden_correct": None,
        "error": None,
        "cost_usd": None,
        "cost_status": "unavailable",
    }
    start = time.monotonic()
    try:
        frames = stream_frames(client, url, headers, timeout, row["question"])
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)[:200]
        record["_error_kind"] = "transport"
        return record
    summary = summarize_frames(frames)
    record["answer_text"] = summary["answer_text"]
    record["total_s"] = time.monotonic() - start
    record["ttft_s"] = summary["ttft_s"]
    record["tool_durations"] = summary["tool_durations"]
    record["tool_status"] = summary["tool_status"]
    record["error"] = summary["error"]
    if summary["error"] is None:
        record["golden_correct"] = score_golden(row["answer"], summary["answer_text"])
        record["_error_kind"] = None
    else:
        record["total_s"] = None
        record["ttft_s"] = None
        record["_error_kind"] = "sse"
    return record


def _proxy_kwargs():
    env = clean_proxy_env(dict(os.environ))
    proxy = None
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        value = env.get(key, "")
        if isinstance(value, str) and value.strip():
            proxy = value.strip()
            break
    if proxy is not None:
        return {"proxy": proxy, "trust_env": False}
    return {"trust_env": False}


def fetch_prod_revision(chat_url, timeout):
    try:
        parts = urlparse(chat_url)
        base = parts.scheme + "://" + parts.netloc
        response = httpx.get(base + "/api/revision", timeout=timeout, **_proxy_kwargs())
        if response.status_code != 200:
            return None
        try:
            data = response.json()
        except ValueError:
            return response.text[:200] or None
        if isinstance(data, dict):
            for key in ("revision", "git_revision", "git_sha", "version"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    return value[:200]
            return json.dumps(data)[:200]
        return str(data)[:200]
    except Exception:
        return None


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_once(client, url, headers, timeout, questions, run_id, prod_revision):
    records = []
    started_at = _utc_now()
    wall_start = time.monotonic()
    consecutive_transport_errors = 0
    for index, row in enumerate(questions):
        if index:
            time.sleep(REQUEST_PAUSE_S)
        record = run_question(client, url, headers, timeout, row)
        records.append(record)
        if record.get("_error_kind") == "transport":
            consecutive_transport_errors += 1
            if consecutive_transport_errors >= CONSECUTIVE_ERROR_LIMIT:
                raise RuntimeError(
                    "stopping after " + str(consecutive_transport_errors) + " consecutive transport errors; last: " + str(record["error"]))
        else:
            consecutive_transport_errors = 0
    for record in records:
        record.pop("_error_kind", None)
    return {
        "run_id": run_id,
        "started_at": started_at,
        "wall_s": time.monotonic() - wall_start,
        "prod_revision": prod_revision,
        "verdict": None,
        "scoreboard": build_scoreboard(records),
        "questions": records,
    }


def _write_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default=_default_questions_path())
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default=None)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--baseline", default=_default_baseline_path())
    args = parser.parse_args(argv)
    if args.runs < 1:
        print("runs must be >= 1")
        return INFRA_EXIT
    if args.freeze and args.runs != 3:
        print("freeze requires --runs 3")
        return INFRA_EXIT
    try:
        questions = load_questions(args.questions)
    except (OSError, ValueError) as exc:
        print("cannot load questions: " + str(exc))
        return INFRA_EXIT
    if not questions:
        print("no questions loaded")
        return INFRA_EXIT
    url = os.environ.get("DIME_CHAT_URL", DEFAULT_CHAT_URL)
    api_key = os.environ.get("DIME_CHAT_API_KEY", "")
    try:
        timeout = float(os.environ.get("DIME_CHAT_TIMEOUT", "") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    if not math.isfinite(timeout) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT
    headers = _headers(api_key)
    out_dir = args.out or _default_out_dir()
    prod_revision = fetch_prod_revision(url, timeout)
    runs = []
    with httpx.Client(**_proxy_kwargs()) as client:
        for number in range(1, args.runs + 1):
            try:
                runs.append(_run_once(
                    client, url, headers, timeout, questions,
                    "run-" + str(number).zfill(2), prod_revision))
            except RuntimeError as exc:
                print(str(exc))
                return INFRA_EXIT
    if args.freeze:
        for run in runs:
            run["verdict"] = "FROZEN"
        baseline = {
            "frozen_at": _utc_now(),
            "questions_file": Path(args.questions).name,
            "questions_sha256": _sha256_file(args.questions),
            "n_questions": len(questions),
            "n_runs": len(runs),
            "regression_threshold_pct": 10.0,
            "golden_tolerance": {"rel_tol": REL_TOL, "abs_tol": ABS_TOL},
            "runs": runs,
        }
        _write_json(args.baseline, baseline)
        run_doc = {
            "questions_file": Path(args.questions).name,
            "questions_sha256": baseline["questions_sha256"],
            "n_runs": len(runs),
            "runs": runs,
        }
        _write_json(str(Path(out_dir) / "run.json"), run_doc)
        for run in runs:
            print(run["run_id"] + " FROZEN " + json.dumps(run["scoreboard"]))
        return 0
    verdicts = []
    if os.path.exists(args.baseline):
        with open(args.baseline, encoding="utf-8") as handle:
            baseline_doc = json.load(handle)
        reference = {"medians": baseline_medians(baseline_doc["runs"])}
        for run in runs:
            verdict, reasons = check_regression(reference, run["scoreboard"], baseline_doc.get("regression_threshold_pct", 10.0))
            run["verdict"] = verdict
            verdicts.append(verdict)
            print(run["run_id"] + " " + verdict + (" " + "; ".join(reasons) if reasons else ""))
    else:
        for run in runs:
            run["verdict"] = "PASS"
            verdicts.append("PASS")
            print(run["run_id"] + " PASS (no baseline)")
    run_doc = {
        "questions_file": Path(args.questions).name,
        "questions_sha256": _sha256_file(args.questions),
        "n_runs": len(runs),
        "runs": runs,
    }
    _write_json(str(Path(out_dir) / "run.json"), run_doc)
    return REGRESSION_EXIT if "REGRESSION" in verdicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
