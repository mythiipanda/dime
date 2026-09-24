"""Contract tests for the v2 prompt system.

Prompts are the runtime's interface to the model: each must exist, carry
the five required sections, and name the frozen contract fields its output
is parsed into. If contracts.py changes, these tests must change only
through the integration owner.
"""

import re
from pathlib import Path

import pytest

from v2 import contracts, prompts
from v2.prompts import load_prompt

PROMPTS_DIR = Path(prompts.__file__).parent

REQUIRED_SECTIONS = ("Objective", "Input", "Output", "Invariants", "Stop condition")

# prompt name -> contract models whose full field set must appear in the
# prompt's Output section
OUTPUT_CONTRACTS = {
    "intake": (contracts.TaskSpec,),
    "intake_admission": (contracts.IntakeAdmissionReview,),
    "planner": (contracts.PlanNode,),
    "requirement_review": (contracts.RequirementReview,),
    "synthesizer": (contracts.DraftReport, contracts.Claim),
    "repair_answer": (contracts.DraftReport, contracts.Claim),
    "verifier": (contracts.VerificationReport, contracts.ClaimResult),
    "repair": (contracts.PlanNode,),
    "project_planner": (contracts.PlanNode,),
}

PROMPT_NAMES = tuple(OUTPUT_CONTRACTS)


def output_section(text: str) -> str:
    match = re.search(r"^## Output\n(.*?)(?=^## )", text, re.M | re.S)
    assert match, "prompt is missing an Output section"
    return match.group(1)


def test_manifest_prompt_hashes_match_live_files():
    """The snapshot manifest pins the exact prompt bytes reviewers saw.

    If a prompt is edited, the manifest hash must be regenerated alongside,
    so the binding can never silently drift.
    """
    import hashlib, json
    manifest = json.loads(
        (PROMPTS_DIR.parent / "schema_snapshots" / "manifest.json").read_text())
    for route, filename in (("planner", "planner_v3.md"),
                            ("requirement_review", "requirement_review_v3.md")):
        live = hashlib.sha256(
            (PROMPTS_DIR / filename).read_bytes()).hexdigest()
        assert manifest[f"{route}.prompt"]["sha256"] == live, (
            f"{filename} changed without a manifest hash regeneration")


def test_ranked_metric_ids_in_prompts_match_source():
    """Ranked metric IDs listed in the prompts must equal the source keys.

    The prompts hardcode the vocabulary in a "one of ..." enum line; if
    TEAM_RATING_METRICS gains or loses a metric, the prompts must be
    updated in the same change.
    """
    from v2.adapters.models import TEAM_RATING_METRICS
    for filename in ("planner_v3.md", "requirement_review_v3.md"):
        text = (PROMPTS_DIR / filename).read_text()
        match = re.search(
            r"`requested_metric`: one of ([A-Z_, ]+)\.", text)
        assert match, f"{filename} no longer lists the ranked enum line"
        listed = [token.strip(" `") for token in match.group(1).split(",")]
        assert set(listed) == set(TEAM_RATING_METRICS), (
            f"{filename} lists {sorted(listed)}, source has "
            f"{sorted(TEAM_RATING_METRICS)}")


def test_prompt_files_match_expected_set():
    from v2.adapters.models import _PROVIDER_ROUTE_PROMPT_NAMES
    stems = {p.stem for p in PROMPTS_DIR.glob("*.md")}
    assert stems == set(PROMPT_NAMES) | set(_PROVIDER_ROUTE_PROMPT_NAMES.values())
    assert not any(PROMPTS_DIR.glob("*/*.md")), "nested prompt copies are not loaded"


@pytest.mark.parametrize("name", PROMPT_NAMES)
def test_required_sections_in_order(name):
    text = load_prompt(name)
    headings = re.findall(r"^## (.+)$", text, re.M)
    assert headings == list(REQUIRED_SECTIONS)


@pytest.mark.parametrize("name", PROMPT_NAMES)
def test_output_section_covers_contract_fields(name):
    section = output_section(load_prompt(name))
    text = load_prompt(name)
    for model in OUTPUT_CONTRACTS[name]:
        assert model.__name__ in text
        for field in model.model_fields:
            assert field in section, f"{name}.md Output omits {model.__name__}.{field}"


@pytest.mark.parametrize("name", PROMPT_NAMES)
def test_every_prompt_declares_a_stop_condition_with_content(name):
    text = load_prompt(name)
    match = re.search(r"^## Stop condition\n(.+)", text, re.M | re.S)
    assert match and match.group(1).strip()


def test_prompts_are_static_text_without_template_syntax():
    for name in PROMPT_NAMES:
        text = load_prompt(name)
        assert "{{" not in text and "{%" not in text


def test_load_prompt_returns_verbatim_file_text():
    for name in PROMPT_NAMES:
        assert load_prompt(name) == (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_load_prompt_is_cached():
    assert load_prompt("intake") is load_prompt("intake")


def test_load_prompt_missing_name_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")


def test_load_prompt_rejects_path_traversal():
    with pytest.raises(ValueError, match="prompt name"):
        load_prompt("../contracts")


def test_load_prompt_rejects_symlink(monkeypatch, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("external", encoding="utf-8")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "external.md").symlink_to(outside)
    monkeypatch.setattr(prompts, "_PROMPTS_DIR", prompts_dir)
    load_prompt.cache_clear()
    try:
        with pytest.raises(ValueError, match="cannot be a symlink"):
            load_prompt("external")
    finally:
        load_prompt.cache_clear()


def test_load_prompt_rejects_symlinked_directory(monkeypatch, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "intake.md").write_text("external", encoding="utf-8")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(prompts, "_PROMPTS_DIR", prompts_dir)
    load_prompt.cache_clear()
    try:
        with pytest.raises(ValueError, match="directory cannot be a symlink"):
            load_prompt("intake")
    finally:
        load_prompt.cache_clear()


def test_planner_and_synthesizer_require_analyst_depth_without_filler():
    planner = load_prompt("planner")
    synth = load_prompt("synthesizer")
    for phrase in (
        "Prefer depth over a minimum-viable plan",
        "modeled value, legality/contracts",
        "Do not add duplicate, filler, or unrelated nodes",
    ):
        assert phrase in planner
    for phrase in (
        "complete enough to act on",
        "counterevidence or\nuncertainty",
        "practical implication",
        "minimum-viable one-line answer",
    ):
        assert phrase in synth
    for phrase in (
        "web_search result is discovery, not substantive evidence",
        "official or primary source",
        "Keep measurement and explanation independent",
    ):
        assert phrase in planner
    for phrase in (
        "Search snippets are discovery evidence only",
        "Reconcile evidence before concluding",
        "repetition across pages is not independent evidence",
    ):
        assert phrase in synth


def test_synthesis_and_verification_require_per_fact_source_vintage() -> None:
    synth = load_prompt("synthesizer")
    verifier = load_prompt("verifier")
    for prompt in (synth, verifier):
        assert "each conflicting fact" in prompt
        assert "`vintages`, then `as_of`" in prompt
        assert "`observed_at`" in prompt



def test_verifier_prompt_aligns_supported_flag_and_reasons_contract():
    from v2.prompts import load_prompt
    prompt=load_prompt('verifier')
    assert '`supported: true` requires exactly `reasons: []`' in prompt
    assert '`supported: false` requires at least one rejection reason' in prompt
    assert 'Do not attach supportive commentary to a supported claim.' in prompt
