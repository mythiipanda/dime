from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_skill_teaches_sql_backed_deltas():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "inside `sql_exec` itself" in src
    assert "never by mental arithmetic" in src
    assert "does not appear verbatim in a tool result" in src


def test_skill_presubmission_covers_derived_figures():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Every derived figure" in src
    assert "recompute it inside sql_exec before submitting" in src



def test_skill_teaches_artifact_prose_parity():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Every figure stated in the prose blocks also lives in an artifact row" in src
    assert "missing_in_artifacts" in src



def test_skill_teaches_verbatim_no_rounding():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Never compress or round a figure in prose" in src
    assert "$4.447M" in src


def test_skill_teaches_batch_recheck_before_resubmission():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "re-check ALL prose figures" in src
    assert "not only the figure the last rejection flagged" in src



def test_skill_teaches_derived_into_artifact_rows():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "computed INTO the artifact rows themselves" in src
    assert "self-backing" in src
    assert "unsupported_claims" in src



def test_skill_bans_prose_side_arithmetic():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Never compute any arithmetic in prose" in src
    assert "prose-typed arithmetic is invisible to the audit" in src



def test_skill_teaches_deadline_awareness():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "stop verifying and fixing" in src
    assert "partial deliverable inside budget" in src



def test_skill_teaches_summary_stat_home_and_no_prose_markdown():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "labeled summary row" in src
    assert "Never present data as a prose markdown table" in src



def test_skill_teaches_stipulation_echo():
    src = (ROOT / "backend/analyst/skills/factual-accuracy-and-exactness/SKILL.md").read_text()
    assert "Echo every methodological stipulation" in src
    assert "uncovered ask" in src
