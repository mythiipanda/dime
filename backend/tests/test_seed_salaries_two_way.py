import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import polars as pl

from seed_salaries import annotate_row_kinds


class FakeCon:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql):
        class Result:
            def __init__(self, rows):
                self.rows = rows

            def fetchall(self):
                return self.rows

        return Result(self.rows)


def kinds(frame_rows, txn_rows):
    frame = pl.DataFrame(frame_rows)
    out = annotate_row_kinds(frame, FakeCon(txn_rows))
    return {f"{r['PLAYER_NAME']}|{r['TEAM']}": r["ROW_KIND"] for r in out.to_dicts()}


CLAYTON_TXNS = [
    ("walter-clayton-jr", "Signing", "jazz", "2025-07-02", "Utah Jazz re-signed guard Walter Clayton Jr. to a Rookie Scale Contract."),
    ("walter-clayton-jr", "Waive", "grizzlies", "2026-10-19", "Memphis Grizzlies waived guard Walter Clayton Jr.."),
    ("walter-clayton-jr", "Signing", "mavericks", "2026-10-21", "Dallas Mavericks signed guard Walter Clayton Jr. to a Two-Way Contract."),
]


def test_clayton_memphis_row_is_dead_money_not_roster():
    rows = kinds([{"PLAYER_NAME": "Walter Clayton", "TEAM": "MEM"}], CLAYTON_TXNS)
    assert rows["Walter Clayton|MEM"] == "dead_money"


def test_clayton_dallas_row_if_present_would_be_two_way():
    rows = kinds(
        [{"PLAYER_NAME": "Walter Clayton", "TEAM": "MEM"},
         {"PLAYER_NAME": "Walter Clayton", "TEAM": "DAL"}],
        CLAYTON_TXNS)
    assert rows["Walter Clayton|DAL"] == "two_way"
    assert rows["Walter Clayton|MEM"] == "dead_money"


def test_active_two_way_signing_annotated():
    txns = [("test-player", "Signing", "lakers", "2026-08-01",
             "Los Angeles Lakers signed guard Test Player to a Two-Way Contract.")]
    rows = kinds([{"PLAYER_NAME": "Test Player", "TEAM": "LAL"}], txns)
    assert rows["Test Player|LAL"] == "two_way"


def test_conversion_to_nba_contract_restores_roster():
    txns = [
        ("conv-player", "Signing", "suns", "2026-07-01",
         "Phoenix Suns signed forward Conv Player to a Two-Way Contract."),
        ("conv-player", "ContractConverted", "suns", "2026-11-01",
         "Phoenix Suns converted the contract of forward Conv Player to an NBA Contract."),
    ]
    rows = kinds([{"PLAYER_NAME": "Conv Player", "TEAM": "PHX"}], txns)
    assert rows["Conv Player|PHX"] == "roster"


def test_waived_standard_plus_two_way_elsewhere():
    txns = [
        ("mixed-player", "Signing", "celtics", "2025-07-01", "Boston Celtics signed Mixed Player."),
        ("mixed-player", "Waive", "celtics", "2026-09-01", "Boston Celtics waived Mixed Player."),
        ("mixed-player", "Signing", "heat", "2026-09-15", "Miami Heat signed Mixed Player to a Two-Way Contract."),
    ]
    rows = kinds(
        [{"PLAYER_NAME": "Mixed Player", "TEAM": "BOS"},
         {"PLAYER_NAME": "Mixed Player", "TEAM": "MIA"}],
        txns)
    assert rows["Mixed Player|BOS"] == "dead_money"
    assert rows["Mixed Player|MIA"] == "two_way"


def test_same_team_standard_resigning_resurrects():
    txns = [
        ("resign-player", "Waive", "bulls", "2026-01-01", "Chicago Bulls waived Resign Player."),
        ("resign-player", "Signing", "bulls", "2026-02-01", "Chicago Bulls signed Resign Player."),
    ]
    rows = kinds([{"PLAYER_NAME": "Resign Player", "TEAM": "CHI"}], txns)
    assert rows["Resign Player|CHI"] == "roster"


def test_continuing_two_way_carries_forward_without_same_season_rows():
    txns = [("carry-player", "Signing", "jazz", "2025-07-01",
             "Utah Jazz signed Carry Player to a Two-Way Contract.")]
    rows = kinds([{"PLAYER_NAME": "Carry Player", "TEAM": "UTA"}], txns)
    assert rows["Carry Player|UTA"] == "two_way"


def test_waive_of_two_way_team_ends_two_way_state():
    txns = [
        ("end-player", "Signing", "kings", "2026-07-01",
         "Sacramento Kings signed End Player to a Two-Way Contract."),
        ("end-player", "Waive", "kings", "2026-10-01", "Sacramento Kings waived End Player."),
    ]
    rows = kinds([{"PLAYER_NAME": "End Player", "TEAM": "SAC"}], txns)
    assert rows["End Player|SAC"] == "unknown"


def test_standard_waive_dead_money_survives_later_two_way_waive():
    txns = [
        ("precedence-player", "Signing", "bucks", "2026-07-01",
         "Milwaukee Bucks signed Precedence Player."),
        ("precedence-player", "Waive", "bucks", "2026-10-01",
         "Milwaukee Bucks waived Precedence Player."),
        ("precedence-player", "Signing", "bucks", "2026-10-03",
         "Milwaukee Bucks signed Precedence Player to a Two-Way Contract."),
        ("precedence-player", "Waive", "bucks", "2026-12-01",
         "Milwaukee Bucks waived Precedence Player."),
    ]
    rows = kinds([{"PLAYER_NAME": "Precedence Player", "TEAM": "MIL"}], txns)
    assert rows["Precedence Player|MIL"] == "dead_money"


def test_two_way_waive_then_standard_resign_restores_roster():
    txns = [
        ("return-player", "Signing", "kings", "2026-07-01",
         "Sacramento Kings signed Return Player to a Two-Way Contract."),
        ("return-player", "Waive", "kings", "2026-10-01", "Sacramento Kings waived Return Player."),
        ("return-player", "Signing", "kings", "2026-11-01",
         "Sacramento Kings signed Return Player."),
    ]
    rows = kinds([{"PLAYER_NAME": "Return Player", "TEAM": "SAC"}], txns)
    assert rows["Return Player|SAC"] == "roster"


def test_suffix_matching_handles_jr_discrepancy():
    rows = kinds([{"PLAYER_NAME": "Walter Clayton Jr.", "TEAM": "MEM"}], CLAYTON_TXNS)
    assert rows["Walter Clayton Jr.|MEM"] == "dead_money"


def test_same_day_events_order_by_group_sort_trailing_integer():
    txns = [
        ("order-player", "Signing", "kings", "2026-10-01",
         "Sacramento Kings signed Order Player to a Two-Way Contract.", "TrxSign3", 0.0),
        ("order-player", "Waive", "kings", "2026-10-01",
         "Sacramento Kings waived Order Player.", "TrxWaive1", 0.0),
    ]
    rows = kinds([{"PLAYER_NAME": "Order Player", "TEAM": "SAC"}], txns)
    assert rows["Order Player|SAC"] == "dead_money"


def test_same_team_resurrection_flags_resurrected_companion():
    txns = [
        ("flag-player", "Signing", "kings", "2026-07-01",
         "Sacramento Kings signed Flag Player."),
        ("flag-player", "Waive", "kings", "2026-10-01", "Sacramento Kings waived Flag Player."),
        ("flag-player", "Signing", "kings", "2026-11-01",
         "Sacramento Kings signed Flag Player."),
    ]
    frame = pl.DataFrame([{"PLAYER_NAME": "Flag Player", "TEAM": "SAC"}])
    out = annotate_row_kinds(frame, FakeCon(txns))
    row = out.to_dicts()[0]
    assert row["ROW_KIND"] == "roster"
    assert row["RESURRECTED"] is True


def test_rows_without_resurrection_history_flag_false():
    rows_frame = pl.DataFrame([{"PLAYER_NAME": "Walter Clayton", "TEAM": "MEM"}])
    out = annotate_row_kinds(rows_frame, FakeCon(CLAYTON_TXNS))
    row = out.to_dicts()[0]
    assert row["ROW_KIND"] == "dead_money"
    assert row["RESURRECTED"] is False
