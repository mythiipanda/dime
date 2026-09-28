"""Suite: skill finder (adopt: fail-closed selection, no keyword routing).

Extracts `_select_skills_intent` from backend/app/graph.py with the AST
(so the eval runs the real finder, not a copy), loads the v1 skill catalog
from backend/app/skills.py, and scores every labeled case:
  every expected skill must be selected, and every selected skill must be
  in expected+alternates.

Modes:
  hermetic (default): RecordedLLM replays the recorded finder responses
    (recorded/skill_finder_responses.json); the pipeline structure —
    catalog, parsing, unknown-skill filter, fail-closed — is live.
  --live-llm: calls Gemini Flash Lite via the gemini skill CLI with the
    exact finder prompt (prompt capture + replay keeps this deterministic).
  --record: captures live prompts+responses into the recording file.

Also checks:
  - fail-closed: an LLM that errors/returns garbage -> ([], None).
  - catalog staleness: v1 markdown skills on disk vs catalog function
    output; drift fails the check (labels are keyed to the catalog).
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult, sha256_text  # noqa: E402
from trace import emit  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
REC = DATA / "recorded" / "skill_finder_responses.json"
LABELS = DATA / "skill_finder_labels.json"


class HumanMessage:
    def __init__(self, content):
        self.content = content


def _load_skills_module():
    spec = importlib.util.spec_from_file_location(
        "dime_skills", Path(__file__).resolve().parent.parent.parent
        / "app" / "skills.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_finder():
    """AST-extract `_select_skills_intent` plus the constants it uses."""
    root = Path(__file__).resolve().parent.parent.parent
    tree = ast.parse((root / "app" / "graph.py").read_text())
    mod = ast.Module(body=[], type_ignores=[])
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name == "_select_skills_intent":
            mod.body.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in (
                        "MAX_SKILLS_PER_TURN", "_VALID_ENTITY_LEVELS"):
                    mod.body.append(node)
    sk = _load_skills_module()
    ns = {"re": re, "json": json, "skills_catalog": sk.catalog,
          "HumanMessage": HumanMessage}
    exec(compile(mod, "<_select_skills_intent>", "exec"), ns)
    return ns["_select_skills_intent"], sk


class RecordedLLM:
    """Replays recorded finder responses (or records them in record mode)."""

    def __init__(self, recording, record=False):
        self.recording = recording
        self.record = record

    async def ainvoke(self, msgs):
        prompt = msgs[0].content
        h = sha256_text(prompt)
        entry = self.recording.get(h)
        if entry is not None and not self.record:
            return HumanMessage(entry["response"])
        raise RuntimeError(f"no recorded response for prompt hash {h}; "
                           "run with --record --live-llm")


class LiveLLM:
    """Gemini Flash Lite via the gemini skill CLI. Opt-in only."""

    def __init__(self, recording, record=False):
        self.recording = recording
        self.record = record
        self.cli = (Path.home() / "workspace" / "skills" / "gemini" / "bin"
                    / "gemini-chat.py")

    async def ainvoke(self, msgs):
        prompt = msgs[0].content
        h = sha256_text(prompt)
        if h in self.recording and not self.record:
            return HumanMessage(self.recording[h]["response"])
        out = subprocess.run(
            [sys.executable, str(self.cli), "gemini-3.5-flash-lite", prompt,
             "--max-tokens", "200"],
            capture_output=True, text=True, timeout=180)
        text = out.stdout.strip() or out.stderr.strip()
        self.recording[h] = {"prompt": prompt, "response": text}
        return HumanMessage(text)


def _known_skills(sk):
    return {line.split(":", 1)[0][2:] for line in
            sk.catalog().splitlines() if line.startswith("- ")}


def run(ctx):
    res = SuiteResult(name="skill_finder", mode="hermetic")
    emit("suite_started", {"suite": "skill_finder", "mode": "hermetic"})
    try:
        finder, sk = extract_finder()
    except Exception as exc:
        res.fail("extract-finder", f"could not extract finder: {exc}")
        return res
    res.ok()

    # catalog staleness: markdown files on disk vs catalog() output
    root = Path(__file__).resolve().parent.parent.parent
    disk = {p.stem for p in (root / "app" / "skills").glob("*.md")}
    known = _known_skills(sk)
    if disk != known:
        res.fail("catalog-staleness",
                 f"disk {sorted(disk)} vs catalog {sorted(known)}; "
                 "labels may be stale")
    else:
        res.ok()

    labels = json.loads(LABELS.read_text())["labels"]
    if REC.is_file():
        recording = json.loads(REC.read_text())
    else:
        recording = {}
        if not ctx.get("live_llm"):
            res.fail("no-recording",
                     f"{REC} missing and --live-llm not set; "
                     "run once with --record --live-llm")
            return res
    if ctx.get("record") and not ctx.get("live_llm"):
        res.fail("record-needs-live", "--record needs --live-llm")
        return res

    llm = (LiveLLM(recording, record=ctx.get("record"))
           if ctx.get("live_llm") else RecordedLLM(recording))
    if ctx.get("live_llm"):
        res.mode = "live-llm"

    async def _run():
        exact = 0
        misses = []
        for lab in labels:
            qid = lab["id"]
            emit("question_asked", {"suite": "skill_finder", "qid": qid,
                                   "question": lab["question"]})
            try:
                skills, level = await finder(lab["question"], llm)
            except RuntimeError as exc:
                misses.append((qid, str(exc), None, None))
                continue
            except Exception as exc:
                misses.append((qid, f"finder raised: {exc}", None, None))
                continue
            # fail-closed invariant: selected skills must be known catalog
            # entries (the finder itself enforces this on live responses)
            if not set(skills) <= known:
                misses.append((qid, f"selected unknown skills: {skills}",
                               None, skills))
                continue
            expected, alternates = lab["expected"], lab["alternates"]
            if all(e in skills for e in expected) and \
                    all(s in expected + alternates for s in skills):
                exact += 1
                res.ok()
                emit("skills_selected", {"qid": qid, "selected": skills,
                                        "entity_level": level})
            else:
                misses.append(
                    (qid, f"selected={skills} expected={expected} "
                          f"alternates={alternates}", expected, skills))
        return exact, misses

    exact, misses = asyncio.run(_run())

    # fail-closed: garbage/erroring LLM -> ([], None)
    class BrokenLLM:
        async def ainvoke(self, msgs):
            raise ConnectionError("simulated outage")

    class GarbageLLM:
        async def ainvoke(self, msgs):
            return HumanMessage("definitely not json {{{")

    async def _closed():
        try:
            r1 = await finder("Compare Luka and SGA", BrokenLLM())
            r2 = await finder("Compare Luka and SGA", GarbageLLM())
            return r1, r2
        except Exception as exc:
            return exc

    r = asyncio.run(_closed())
    if isinstance(r, Exception):
        res.fail("fail-closed", f"finder raised instead of failing closed: {r}")
    elif r == (([], None), ([], None)):
        res.ok()
    else:
        res.fail("fail-closed", f"expected ([], None) twice, got {r}")

    acc = exact / len(labels) if labels else 0
    res.notes.append(f"exact-match accuracy {exact}/{len(labels)} "
                     f"({acc:.0%}); recorded={not ctx.get('live_llm')}")
    # Regression gate, not perfection gate: label misses stay visible
    # below, but the suite fails only if accuracy drops under 80%.
    # Known strict miss (accepted baseline, do not loosen labels to
    # hide it): sf02 — finder adds a redundant shot_profile second pick.
    for qid, detail, expected, got in misses:
        if acc >= 0.8:
            res.notes.append(f"miss {qid}: {detail}")
        else:
            res.fail(qid, detail, expected=expected, got=got)
    if acc < 0.8:
        res.notes.append(f"accuracy {acc:.0%} below 80% gate")
    emit("calibration", {"suite": "skill_finder",
                         "accuracy": acc, "n": len(labels)})
    if ctx.get("record"):
        REC.parent.mkdir(parents=True, exist_ok=True)
        REC.write_text(json.dumps(recording, indent=2))
        res.notes.append(f"recording saved to {REC} ({len(recording)} entries)")
    emit("suite_finished", {"suite": "skill_finder", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
