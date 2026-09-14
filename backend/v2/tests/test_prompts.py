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
    "planner": (contracts.PlanNode,),
    "synthesizer": (contracts.DraftReport, contracts.Claim),
    "verifier": (contracts.VerificationReport, contracts.ClaimResult),
    "repair": (contracts.PlanNode,),
    "project_planner": (contracts.PlanNode,),
}

PROMPT_NAMES = tuple(OUTPUT_CONTRACTS)


def output_section(text: str) -> str:
    match = re.search(r"^## Output\n(.*?)(?=^## )", text, re.M | re.S)
    assert match, "prompt is missing an Output section"
    return match.group(1)


def test_prompt_files_match_expected_set():
    stems = {p.stem for p in PROMPTS_DIR.glob("*.md")}
    assert stems == set(PROMPT_NAMES)


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
