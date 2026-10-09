from datetime import UTC, date, datetime

from v2.contracts import Claim, ClaimKind, DraftReport, EntityRef, SeasonRef, TaskSpec, VerificationStatus, EvidenceEnvelope
from v2.runtime.verifier import verify_mechanical


def task(season="2025-26"):
    from v2.contracts import RunMode
    return TaskSpec(goal="Rank the league scorer and report the team record",
        mode=RunMode.QUICK, deliverable="answer",
        entities=[EntityRef(id="LAL", type="team", display_name="Los Angeles Lakers")],
        season=SeasonRef(value=season, source="user", confidence=1), as_of=date(2026, 4, 15))


def evidence():
    return EvidenceEnvelope(
        evidence_id="leaders", capability="qualified_leaders",
        source="warehouse:silver_leaders_pts",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
        season="2025-26", as_of=date(2026, 4, 15),
        entities=[EntityRef(id="LAL", type="team", display_name="Los Angeles Lakers")],
        rows=[
            {"PLAYER": "Luka Doncic", "PTS": 2143, "TEAM": "Los Angeles Lakers"},
            {"PLAYER": "Shai Gilgeous-Alexander", "PTS": 1998, "TEAM": "Oklahoma City Thunder"},
        ],
        units={"PTS": "count"},
        metric_definitions={"PTS": "total regular-season points"},
        qualification="qualified players", coverage="all qualified players")


def result_for(text):
    claim = Claim(text=text, kind=ClaimKind.OBSERVED, evidence_ids=["leaders"])
    report = DraftReport(sections=[text], claims=[claim])
    return verify_mechanical(task(), report, [evidence()])


def supported_for(text):
    return result_for(text).claim_results[0].supported


def test_ascii_season_claim_is_supported():
    assert supported_for("Luka Doncic led the NBA with 2143 points in 2025-26.")


def test_nonbreaking_hyphen_season_is_treated_as_a_season():
    text = "Luka Doncic led the NBA with 2143 points in 2025\u201126."
    assert supported_for(text), result_for(text).claim_results[0].reasons


def test_dash_variants_are_treated_as_a_season():
    for separator in ("\u2013", "\u2014", "\u2212"):
        text = f"Luka Doncic led the NBA with 2143 points in 2025{separator}26."
        assert supported_for(text), (separator, result_for(text).claim_results[0].reasons)


def test_unicode_season_still_rejects_an_unsupported_season():
    result = result_for("Luka Doncic led the NBA with 2143 points in 2024\u201125.")
    assert not result.claim_results[0].supported
    assert "uncited season 2024\u201125" in result.claim_results[0].reasons


def test_nonbreaking_space_does_not_split_a_season_span():
    text = "Luka Doncic led the NBA with 2143 points in\u00a02025-26."
    assert supported_for(text), result_for(text).claim_results[0].reasons


def test_uncited_numerals_still_fail_with_unicode_separator():
    text = "Luka Doncic led the NBA with 2143 points in 2025\u201126 and 9999 rebounds."
    result = result_for(text)
    assert not result.claim_results[0].supported
    assert any(reason.startswith("uncited numeral 9999") for reason in result.claim_results[0].reasons)


def test_season_span_is_consumed_as_one_token():
    text = "Luka Doncic led the NBA with 2143 points in 2025\u201126 and 9999 rebounds."
    reasons = result_for(text).claim_results[0].reasons
    assert not any(reason.startswith("uncited numeral 2025") for reason in reasons)
    assert not any(reason.startswith("uncited numeral 26") for reason in reasons)
    assert not any(
        reason == "claim numerals do not match the named entity rows: 2025, 26"
        for reason in reasons
    )


def test_unicode_separated_date_is_rejected_as_uncited():
    result = result_for("Luka Doncic led the NBA with 2143 points on 2026\u201104\u201115.")
    reasons = result.claim_results[0].reasons
    assert not result.claim_results[0].supported
    assert not any(reason.startswith("uncited numeral 2026") for reason in reasons)
    assert not any(reason.startswith("uncited numeral 04") for reason in reasons)
