import pytest


def _row(season, player, rank=1, rank_label="1", award="MVP"):
    return {
        "SEASON": season,
        "AWARD": award,
        "RANK": rank,
        "RANK_LABEL": rank_label,
        "PLAYER": player,
        "COACH": None,
        "TEAM": "TST",
        "AGE": 25,
        "POINTS_WON": 100,
        "POINTS_MAX": 100,
        "AWARD_SHARE": 1.0,
        "VOTES_FIRST": 10,
        "VOTES_SECOND": None,
        "VOTES_THIRD": None,
    }


@pytest.fixture
def patched_awards(monkeypatch):
    from shared.tools import award_results

    rows = [
        _row("2020-21", "Alpha", 1, "1T"),
        _row("2020-21", "Beta", 1, "1T"),
        _row("2021-22", "Gamma"),
        _row("2021-22", "Epsilon", 2, "2"),
        _row("2021-22", "Alpha", 2, "2"),
        _row("2022-23", "Delta"),
        _row("2021-22", "Alpha", 1, "1", "DPOY"),
    ]
    monkeypatch.setattr(award_results, "_table_on_hand", lambda: True)
    monkeypatch.setattr(
        award_results, "_seasons_on_hand",
        lambda: ("2020-21", "2021-22", "2022-23"))
    def read(sql, params):
        if "MAX(_fetched_at)" in sql:
            return [{"fetched_at": "2026-01-01"}]
        if "_season = ?" in sql:
            cutoff = params[0]
            matching = [row for row in rows if row["SEASON"] == cutoff]
        else:
            cutoff = params[1] if "AWARD = ?" in sql else params[0]
            matching = [row for row in rows if row["SEASON"] <= cutoff]
        if "strip_accents" in sql:
            player = params[-1]
            matching = [row for row in matching if row["PLAYER"] == player]
        if "AWARD = ?" in sql:
            award = params[0]
            matching = [row for row in matching if row["AWARD"] == award]
        return matching

    monkeypatch.setattr(award_results, "_read", read)
    return award_results


def test_winner_history_returns_leaders_with_ties_and_cutoff(patched_awards):
    result = patched_awards.get_award_results.func(
        view="winner_history", award="MVP", season="2021-22")
    assert result["ok"] is True, result
    assert [(row["season"], row["player"]) for row in result["rows"]] == [
        ("2020-21", "Alpha"), ("2020-21", "Beta"), ("2021-22", "Gamma")]
    assert all(row["tied"] for row in result["rows"][:2])
    assert result["meta"]["history_through"] == "2021-22"
    assert result["meta"]["seasons_covered"] == ["2020-21", "2021-22"]
    assert result["meta"]["coverage"].startswith(
        "Official Basketball-Reference award result for Most Valuable Player: "
        "every subject sharing the leading rank in each covered season through "
        "2021-22")

def test_single_season_views_report_single_season_rows_and_scope(
        patched_awards):
    winner = patched_awards.get_award_results.func(
        view="winner", award="MVP", season="2021-22")
    field = patched_awards.get_award_results.func(
        view="field", award="MVP", season="2021-22")
    assert [(row["season"], row["player"]) for row in winner["rows"]] == [
        ("2021-22", "Gamma")]
    assert [(row["season"], row["player"]) for row in field["rows"]] == [
        ("2021-22", "Gamma"), ("2021-22", "Epsilon"),
        ("2021-22", "Alpha")]
    assert winner["meta"]["coverage"].startswith(
        "Official Basketball-Reference award result for Most Valuable Player: "
        "every subject sharing the leading rank in 2021-22")
    assert field["meta"]["coverage"].startswith(
        "Official Basketball-Reference award result for Most Valuable Player: "
        "every published placement on the ballot in 2021-22")
    assert "through" not in winner["meta"]["coverage"]
    assert "through" not in field["meta"]["coverage"]

def test_player_awards_keeps_subject_history_contract(patched_awards):
    result = patched_awards.get_award_results.func(
        view="player_awards", player="Alpha", season="2021-22")
    assert result["ok"] is True, result
    assert [(row["season"], row["award"]) for row in result["rows"]] == [
        ("2020-21", "MVP"), ("2021-22", "MVP"), ("2021-22", "DPOY")]
    assert result["meta"]["history_through"] == "2021-22"
    assert result["meta"]["coverage"].startswith(
        "Official Basketball-Reference award result for every published award: "
        "every ballot row the subject appears on through 2021-22")
    assert "leading rank" not in result["meta"]["coverage"]


def test_winner_history_without_ranked_rows_is_not_success(patched_awards,
                                                            monkeypatch):
    monkeypatch.setattr(patched_awards, "_read", lambda sql, params: [])
    result = patched_awards.get_award_results.func(
        view="winner_history", award="MVP", season="2021-22")
    assert result["ok"] is False
    assert result["reason"] == "award_season_absent"


@pytest.mark.parametrize("view,arguments", [
    ("winner", {"award": "MVP", "season": "2021-22"}),
    ("field", {"award": "MVP", "season": "2021-22"}),
])
def test_existing_views_keep_their_contract(patched_awards, view, arguments):
    result = patched_awards.get_award_results.func(view=view, **arguments)
    assert result["ok"] is True, result
