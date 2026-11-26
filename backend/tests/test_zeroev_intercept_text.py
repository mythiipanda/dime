from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "backend/analyst/pi-execution.ts").read_text()


def _reprompt_text() -> str:
    marker = 'session.prompt("This is a data question and no data tool has been called yet'
    at = SRC.index(marker)
    end = SRC.index('");', at)
    return SRC[at:end]


def test_intercept_names_tools_available_and_working():
    text = _reprompt_text()
    assert "submit_answer, sql_exec and verify_answer_numbers are available and working right now" in text, (
        "the intercept must explicitly name the submission and evidence tools as "
        "available so weak models stop reading it as a tool-unavailability signal"
    )


def test_intercept_blocks_tools_prefix_fiction():
    text = _reprompt_text()
    assert "there is no tools.xxx invocation form" in text, (
        "the intercept must explicitly deny the codemode tools.x fiction"
    )
    assert "direct tools you call by bare name" in text


def test_intercept_gives_concrete_count_probe_first_action():
    text = _reprompt_text()
    assert "SELECT count(*) FROM" in text, (
        "the intercept must hand the model a concrete first-action probe query shape"
    )
    assert "the silver table the ask names" in text
