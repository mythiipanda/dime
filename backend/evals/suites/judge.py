"""Suite: judge with escalation (adopt: JEV cascade + criteria
decomposition + anti-hedging + calibration).

A cheap judge scores every candidate answer on five decomposed criteria
(1-10): number_match, grounding, reasoning, completeness, no_hedge.
Verdicts with confidence < 0.7 escalate to a stronger judge; the strong
verdict is final and the escalation is traced.

Candidates are fabricated from golden-question truth (correct, wrong
number, wrong season, hedged), so every verdict has a known ground truth
and the suite can check the judge discriminates.

Modes:
  hermetic (default): replays recorded verdicts
    (data/recorded/judge_verdicts.json); the cascade, criteria, and
    calibration math are live.
  --live-judge: cheap = gemini-3.5-flash-lite, strong = gemini-3.1-pro
    (override with DIME_JUDGE_STRONG).
  --record: captures prompts+verdicts into the recording.

Calibration: expressed confidence is bucketed and the per-bucket hit rate
(verdict agrees with known truth) is reported; a judge whose 0.9 bucket
hits 0.5 is miscalibrated and the report says so.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, sha256_text  # noqa: E402
from trace import emit  # noqa: E402
import scoring as _scoring  # noqa: E402  (season gate: canonical rule)

DATA = Path(__file__).resolve().parent.parent / "data"
REC = DATA / "recorded" / "judge_verdicts.json"
CHEAP_MODEL = "gemini-3.5-flash-lite"
STRONG_MODEL = os.environ.get("DIME_JUDGE_STRONG", "gemini-3.1-pro")
ESCALATE_BELOW = 0.7

CRITERIA = ["number_match", "grounding", "reasoning", "completeness",
            "no_hedge"]

JUDGE_PROMPT = """You grade a sports-analytics answer against verified warehouse facts.
Return JSON only, no prose: {{"scores": {{"number_match": 1-10, "grounding": 1-10, "reasoning": 1-10, "completeness": 1-10, "no_hedge": 1-10}}, "confidence": 0.0-1.0, "rationale": "one sentence"}}.

Criteria:
- number_match: every number in the answer matches the verified facts (wrong number = 1-3).
- grounding: every factual claim is traceable to the verified facts, nothing invented.
- reasoning: the steps from facts to conclusion are sound, no leaps.
- completeness: the full question is answered, nothing material omitted.
- no_hedge: states the answer directly; vague, evasive, or "it's hard to say" phrasing scores 1-3 even if the numbers are right.
- season errors are critical: if the answer attributes the facts to a different season than "Season in scope" (right numbers, wrong season), grounding scores 1-3 and the answer fails overall no matter how high the other scores are.

Question: {question}
Verified facts: {facts}
Season in scope: {season}
Answer to grade: {answer}
JSON:"""


def _facts_text(q, flat):
    parts = []
    for i in q["expect"].get("numbers_from", []):
        parts.append(f"value[{i}]={flat[i]}")
    for i in q["expect"].get("names_from", []):
        parts.append(f"name[{i}]={flat[i]}")
    return "; ".join(parts) or "(no numeric facts)"


def _call_model(model, prompt):
    cli = (Path.home() / "workspace" / "skills" / "gemini" / "bin"
           / "gemini-chat.py")
    last = ""
    for attempt in (1, 2):
        out = subprocess.run(
            [sys.executable, str(cli), model, prompt, "--max-tokens", "600"],
            capture_output=True, text=True, timeout=240)
        text = out.stdout.strip()
        if text and not text.startswith("Traceback"):
            return text
        last = text or out.stderr.strip()
        if attempt == 1:
            import time
            time.sleep(5)
    raise RuntimeError(f"judge model call failed twice ({model}): "
                       f"{last[:200]}")


def _parse_verdict(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON in judge output: {text[:120]}")
    v = json.loads(text[start:end + 1])
    scores = {c: max(1, min(10, int(v["scores"][c]))) for c in CRITERIA}
    return {"scores": scores,
            "confidence": max(0.0, min(1.0, float(v["confidence"]))),
            "rationale": str(v.get("rationale", ""))[:300]}


class Judge:
    def __init__(self, recording, live=False, record=False):
        self.recording = recording
        self.live = live
        self.record = record
        self.escalations = 0

    def judge(self, prompt, qid, variant):
        h = sha256_text(prompt)
        if h in self.recording and not self.record:
            v = self.recording[h]["verdict"]
        else:
            if not self.live:
                raise RuntimeError(
                    f"no recorded verdict for {qid}/{variant}; run with "
                    "--record --live-judge")
            try:
                v = _parse_verdict(_call_model(CHEAP_MODEL, prompt))
            except ValueError as exc:
                raise RuntimeError(f"cheap judge output unparseable: {exc}")
            v["judge"] = "cheap:" + CHEAP_MODEL
            self.recording[h] = {"prompt": prompt, "verdict": v}
        conf = v.get("confidence", 0)
        emit("verdict", {"qid": qid, "variant": variant,
                         "criterion": "judge-cheap",
                         "scores": v["scores"], "confidence": conf})
        if conf < ESCALATE_BELOW:
            self.escalations += 1
            eh = sha256_text("STRONG:" + prompt)
            if eh in self.recording and not self.record:
                sv = self.recording[eh]["verdict"]
            else:
                if not self.live:
                    raise RuntimeError(
                        f"no recorded strong verdict for {qid}/{variant}")
                try:
                    sv = _parse_verdict(_call_model(STRONG_MODEL, prompt))
                except ValueError as exc:
                    raise RuntimeError(
                        f"strong judge output unparseable: {exc}")
                sv["judge"] = "strong:" + STRONG_MODEL
                self.recording[eh] = {"prompt": prompt, "verdict": sv}
            emit("verdict", {"qid": qid, "variant": variant,
                             "criterion": "judge-strong-escalated",
                             "scores": sv["scores"],
                             "confidence": sv.get("confidence", 0)})
            return sv, True
        return v, False


def _verdict_pass(v, season, answer):
    """Judge's mean score, hard-gated by the deterministic season rule.

    The season gate is the canonical scorer's rule (wrong-season phrasing
    zeroes), not the judge's opinion: a wrong-season answer fails overall
    no matter how the fuzzy criteria score.
    """
    if _scoring.season_gate_tripped(season, answer):
        return False
    return sum(v["scores"].values()) / len(CRITERIA) >= 6.0


def run(ctx):
    res = SuiteResult(name="judge", mode="hermetic")
    emit("suite_started", {"suite": "judge", "mode": "hermetic"})
    live = ctx.get("live_judge")
    record = ctx.get("record")
    if record and not live:
        res.fail("record-needs-live", "--record needs --live-judge")
        return res
    recording = json.loads(REC.read_text()) if REC.is_file() else {}
    if not recording and not live:
        res.fail("no-recording", f"{REC} missing; run --record --live-judge")
        return res
    # prompt pin check (adopt: SHA-256 manifests for weekly comparability)
    MAN = DATA / "prompt_manifest.json"
    if MAN.is_file():
        man = json.loads(MAN.read_text())
        pinned = man.get("prompts", {}).get("judge_prompt")
        if pinned != sha256_text(JUDGE_PROMPT):
            res.fail("prompt-manifest",
                     "JUDGE_PROMPT drifted from the pinned manifest; "
                     "week-over-week judge numbers are not comparable. "
                     "Regenerate the manifest if the change is intended.")
            return res
        res.ok()
        res.notes.append("judge prompt matches pinned manifest")
    else:
        res.skip("prompt manifest missing; prompt drift unchecked")
    if live:
        res.mode = "live-judge"
    judge = Judge(recording, live=live, record=record)

    # escalation wiring self-test: a cheap verdict under the threshold
    # must escalate to the strong verdict (plumbing check, no network)
    try:
        probe_rec = {
            sha256_text("probe"): {
                "prompt": "probe",
                "verdict": {"scores": {c: 5 for c in CRITERIA},
                            "confidence": 0.4, "rationale": "probe",
                            "judge": "cheap:probe"}},
            sha256_text("STRONG:probe"): {
                "prompt": "probe",
                "verdict": {"scores": {c: 9 for c in CRITERIA},
                            "confidence": 0.95, "rationale": "probe",
                            "judge": "strong:probe"}},
        }
        probe_judge = Judge(probe_rec, live=False, record=False)
        sv, was_escalated = probe_judge.judge("probe", "selftest",
                                              "escalation")
        assert was_escalated and sv["judge"] == "strong:probe" \
            and probe_judge.escalations == 1, \
            "escalation wiring broken"
        res.ok()
    except AssertionError as exc:
        res.fail("escalation-wiring", str(exc))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import golden_warehouse as gw
    questions = json.loads(
        (DATA / "golden_questions.json").read_text())["questions"]


    tmp = Path(tempfile.mkdtemp(prefix="evals-judge-"))
    db = tmp / "fixture.duckdb"
    gw.build_fixture(db)
    import duckdb
    con = duckdb.connect(str(db), read_only=True)

    buckets = {}  # (lo, hi) -> [hits, n]
    variants = 0
    try:
        for q in questions:
            if q.get("status") == "stubbed" or q.get("warehouse") == "real":
                continue
            qid = q["id"]
            values = gw._verifier_values(con, q)
            if values is None:
                res.fail(qid, "oracle null; cannot build judge candidates")
                continue
            flat = gw._flatten(values, q.get("multi_row"))
            facts = _facts_text(q, flat)
            season = q["expect"].get("season")
            fab = q.get("fabricate", {})

            npos = q["expect"].get("numbers_from", [])
            pert = flat
            for p in npos:
                pert = gw._perturb_flat(pert, p)
            cands = [
                ("correct", gw._fill(fab.get("correct", ""), flat), True),
                ("wrong_number", gw._fill(fab.get("wrong_number", ""), pert),
                 False),
            ]
            if fab.get("wrong_season"):
                cands.append(
                    ("wrong_season", gw._fill(fab["wrong_season"], flat),
                     False))
            # hedged: right numbers, evasive phrasing (anti-hedging probe)
            base = gw._fill(fab.get("correct", ""), flat) or ""
            cands.append(
                ("hedged",
                 "It's hard to say precisely, but it seems like it might be "
                 f"around... {base} That's just my rough sense though.",
                 False))

            for variant, answer, truth in cands:
                if not answer:
                    continue
                variants += 1
                prompt = JUDGE_PROMPT.format(
                    question=q["question"], facts=facts,
                    season=season or "not specified", answer=answer)
                try:
                    v, escalated = judge.judge(prompt, qid, variant)
                except RuntimeError as exc:
                    res.fail(f"{qid}/{variant}", str(exc))
                    continue
                passed = _verdict_pass(v, season, answer)
                hit = (passed == truth)
                conf = v.get("confidence", 0)
                bucket = (0.5, 0.7) if conf < 0.7 else (
                    (0.7, 0.85) if conf < 0.85 else (0.85, 1.01))
                b = buckets.setdefault(bucket, [0, 0])
                b[0] += hit
                b[1] += 1
                emit("calibration", {"qid": qid, "variant": variant,
                                    "confidence": conf, "hit": hit,
                                    "escalated": escalated})

                # discrimination checks against known truth.
                # wrong_number attacks number_match; wrong_season keeps the
                # right numbers but names the wrong season, so it attacks
                # the overall verdict (season error), not number_match.
                nm = v["scores"]["number_match"]
                if variant == "correct" and not passed:
                    res.fail(f"{qid}/correct",
                             f"judge failed a correct answer: {v['scores']}")
                elif variant == "wrong_number":
                    if nm > 4:
                        res.fail(f"{qid}/{variant}",
                                 f"judge missed a wrong number "
                                 f"(number_match={nm}): {v['scores']}")
                    elif passed:
                        res.fail(f"{qid}/{variant}",
                                 "judge passed an answer with wrong numbers")
                    else:
                        res.ok()
                elif variant == "wrong_season":
                    if passed:
                        res.fail(f"{qid}/{variant}",
                                 f"judge passed a wrong-season answer: "
                                 f"{v['scores']}")
                    else:
                        res.ok()
                elif variant == "hedged":
                    if v["scores"]["no_hedge"] > 4:
                        res.fail(f"{qid}/hedged",
                                 f"anti-hedging criterion missed evasive "
                                 f"answer (no_hedge={v['scores']['no_hedge']})")
                    else:
                        res.ok()
                else:
                    res.ok()
    finally:
        con.close()

    cal_lines = []
    for (lo, hi), (hits, n) in sorted(buckets.items()):
        rate = hits / n if n else 0
        cal_lines.append(f"conf [{lo:.2f},{hi:.2f}): {hits}/{n} hit "
                         f"({rate:.0%})")
        if hi > 0.85 and n >= 3 and rate < 0.7:
            res.fail("calibration",
                     f"high-confidence bucket miscalibrated: {rate:.0%} hit")
    res.notes.append(f"judged {variants} answer variants; "
                     f"escalations={judge.escalations}")
    res.notes.extend("calibration: " + l for l in cal_lines)
    if record:
        REC.parent.mkdir(parents=True, exist_ok=True)
        REC.write_text(json.dumps(recording, indent=2))
        res.notes.append(f"recording saved ({len(recording)} entries)")
    emit("suite_finished", {"suite": "judge", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
