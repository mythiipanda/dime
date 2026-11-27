import os
import random
from itertools import product

from shared.tools.cap_rules import CAP, allowed_incoming, hard_cap_consequences
from shared.tools.league.cba_cap import _outgoing_needed
from shared.tools.league.trade_legality import (
    _evaluate_team,
    _expanded_matching_use,
    _placement_fits,
)

SEED = 20261127
CASES = int(os.environ.get("VERIFY_CBA_CASES", "600"))
MATCHING_CUSHION = 250_000
EXPANDED_MATCHING_CUSHION = 9_096_000
EXPANDED_LOW_MAX = 8_846_000
EXPANDED_MID_MAX = 35_384_000


def _assignment_oracle(salaries, capacities, required_bins, matching_limit=None):
    positive = [int(salary or 0) for salary in salaries]
    positive = [salary for salary in positive if salary > 0]
    bins = [int(capacity or 0) for capacity in capacities]
    for assignment in product(range(len(bins)), repeat=len(positive)):
        loads = [0] * len(bins)
        used = 0
        for salary, position in zip(positive, assignment):
            loads[position] += salary
            used |= 1 << position
        if any(loads[position] > bins[position] for position in range(len(bins))):
            continue
        if matching_limit is not None and loads and loads[0] > matching_limit:
            continue
        if (used & required_bins) == required_bins:
            return True
    return False


def _assert_placement(salaries, capacities, required_bins, matching_limit=None):
    expected = _assignment_oracle(
        salaries, capacities, required_bins, matching_limit)
    actual = _placement_fits(
        salaries, capacities, required_bins, matching_limit)
    assert actual == expected, (
        "placement mismatch: "
        f"salaries={salaries!r} capacities={capacities!r} "
        f"required_bins={required_bins!r} matching_limit={matching_limit!r} "
        f"actual={actual!r} expected={expected!r}")


def test_placement_fits_small_input_space_exhaustively():
    count = 0
    for salary_count in range(4):
        for bin_count in range(1, 4):
            for salaries in product(range(3), repeat=salary_count):
                for capacities in product(range(4), repeat=bin_count):
                    for required_bins in range(1 << bin_count):
                        _assert_placement(
                            list(salaries), list(capacities), required_bins)
                        count += 1
    assert count == 23_360


def test_placement_fits_generated_inputs_match_assignment_oracle():
    rng = random.Random(SEED)
    for _ in range(CASES):
        bin_count = rng.randint(1, 4)
        salary_count = rng.randint(0, 5)
        capacities = [rng.randint(0, 12) for _ in range(bin_count)]
        salaries = []
        for _ in range(salary_count):
            if rng.random() < 0.6:
                capacity = rng.choice(capacities)
                salary = max(0, capacity + rng.choice((-1, 0, 1)))
            else:
                salary = rng.randint(0, 14)
            salaries.append(salary)
        required_bins = rng.randrange(1 << bin_count)
        matching_limit = rng.choice((None, rng.randint(0, 18)))
        _assert_placement(salaries, capacities, required_bins, matching_limit)


def _expected_allowed_incoming(outgoing, over_apron1, cap_room):
    if over_apron1:
        return outgoing
    if outgoing <= EXPANDED_LOW_MAX:
        matched = outgoing * 2 + MATCHING_CUSHION
    elif outgoing <= EXPANDED_MID_MAX:
        matched = outgoing + EXPANDED_MATCHING_CUSHION
    else:
        matched = outgoing * 5 // 4 + MATCHING_CUSHION
    room_allowance = outgoing + cap_room + MATCHING_CUSHION
    if cap_room > 0 and room_allowance > matched:
        return room_allowance
    return matched


def _money_edges():
    low = EXPANDED_LOW_MAX
    mid = EXPANDED_MID_MAX
    values = {0, 1, 249_999, 250_000, low - 1, low, low + 1,
              mid - 1, mid, mid + 1, 60_000_000}
    return sorted(values)


def test_generated_matching_inverse_and_monotonicity():
    rng = random.Random(SEED + 1)
    outgoing_values = _money_edges() + [
        rng.randint(0, 80_000_000) for _ in range(CASES)]
    for outgoing in outgoing_values:
        for over_apron1 in (False, True):
            rooms = (0, 1, rng.randint(2, 30_000_000))
            for room in rooms:
                allow, rule = allowed_incoming(outgoing, over_apron1, room)
                expected_allow = _expected_allowed_incoming(
                    outgoing, over_apron1, room)
                assert allow == expected_allow, (
                    "matching allowance differs from the 2026-27 band: "
                    f"outgoing={outgoing!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} allow={allow!r} "
                    f"expected={expected_allow!r} rule={rule!r}")
                assert allow >= outgoing, (
                    "matching allowance below outgoing: "
                    f"outgoing={outgoing!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} allow={allow!r} rule={rule!r}")
                ahead, _ = allowed_incoming(outgoing + 1, over_apron1, room)
                assert ahead >= allow, (
                    "matching allowance is not monotone in outgoing: "
                    f"outgoing={outgoing!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} allow={allow!r} ahead={ahead!r}")
                more_room, _ = allowed_incoming(
                    outgoing, over_apron1, room + 1)
                assert more_room >= allow, (
                    "matching allowance is not monotone in cap room: "
                    f"outgoing={outgoing!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} allow={allow!r} "
                    f"more_room={more_room!r}")


def test_generated_outgoing_needed_is_exact_matching_inverse():
    rng = random.Random(SEED + 2)
    incoming_values = _money_edges() + [
        rng.randint(1, 90_000_000) for _ in range(CASES)]
    for incoming in incoming_values:
        for over_apron1 in (False, True):
            for room in (0, 1, rng.randint(2, 30_000_000)):
                needed = _outgoing_needed(incoming, over_apron1, room)
                allow, rule = allowed_incoming(needed, over_apron1, room)
                assert allow >= incoming, (
                    "outgoing_needed does not reach incoming: "
                    f"incoming={incoming!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} needed={needed!r} allow={allow!r} "
                    f"rule={rule!r}")
                if needed:
                    lower, lower_rule = allowed_incoming(
                        needed - 1, over_apron1, room)
                    assert lower < incoming, (
                        "outgoing_needed is not minimal: "
                        f"incoming={incoming!r} over_apron1={over_apron1!r} "
                        f"cap_room={room!r} needed={needed!r} "
                        f"lower_outgoing={needed - 1!r} lower_allow={lower!r} "
                        f"rule={lower_rule!r}")


def test_hard_cap_trigger_truth_table_at_apron_boundaries():
    payrolls = (CAP["apron1"] - 1, CAP["apron1"], CAP["apron1"] + 1,
                CAP["apron2"] - 1, CAP["apron2"], CAP["apron2"] + 1)
    for bits in range(64):
        flags = {
            "aggregates": bool(bits & 1),
            "cash_out": 1_000_000 if bits & 2 else 0,
            "prior_tpe": bool(bits & 4),
            "snt_tpe": bool(bits & 8),
            "is_snt_receiver": bool(bits & 16),
            "expanded_matching": bool(bits & 32),
        }
        expected_aprons = set()
        if flags["aggregates"] or flags["cash_out"] or flags["snt_tpe"]:
            expected_aprons.add("second apron")
        if (flags["prior_tpe"] or flags["is_snt_receiver"]
                or flags["expanded_matching"]):
            expected_aprons.add("first apron")
        for payroll in payrolls:
            result = hard_cap_consequences("BOS", payroll, **flags)
            expected_violations = {
                apron for apron in expected_aprons
                if payroll > CAP["apron1" if apron == "first apron" else "apron2"]}
            joined_issues = "\n".join(result["issues"])
            case = (f"payroll={payroll!r} flags={flags!r} "
                    f"result={result!r}")
            assert len(result["aprons"]) == len(set(result["aprons"])), case
            assert set(result["aprons"]) == expected_aprons, case
            assert result["hard_cap"] == "+".join(result["aprons"]), case
            assert set(result["violations"]) == expected_violations, case
            assert len(result["issues"]) == len(expected_violations), case
            assert (("hard-capped at the first apron" in joined_issues)
                    == ("first apron" in expected_violations)), case
            assert (("hard-capped at the second apron" in joined_issues)
                    == ("second apron" in expected_violations)), case


def _generated_tpe(rng, index):
    status = rng.choice(("current_year", "prior_year"))
    origin_year = 2026 if status == "current_year" else 2025
    kind = "sign_and_trade" if rng.random() < 0.2 else "ordinary"
    return {"team": "BOS", "amount": rng.randint(2_000_000, 14_000_000),
            "kind": kind, "origin_year": origin_year,
            "origin_season": f"{origin_year}-{(origin_year + 1) % 100:02d}",
            "status": status, "legacy_defaults": False}


def _integration_input(rng):
    outgoing_count = rng.choice((1, 1, 2, 3))
    outgoing = rng.randint(5_000_000, 60_000_000)
    incoming_count = rng.randint(0, 4)
    incoming_salaries = [rng.randint(1_000_000, 38_000_000)
                         for _ in range(incoming_count)]
    in_rows = [{"player": f"Incoming {index}", "salary": salary}
               for index, salary in enumerate(incoming_salaries, 1)]
    side = {"out_names": [f"Outgoing {index}"
                          for index in range(outgoing_count, 0, -1)],
            "out_total": outgoing,
            "in_names": [row["player"] for row in in_rows],
            "in_rows": in_rows,
            "in_total": sum(incoming_salaries),
            "pay_before": rng.randint(125_000_000, 228_000_000)}
    team_tpes = [_generated_tpe(rng, index)
                 for index in range(rng.randint(0, 3))]
    cash_out = rng.choice((0, 0, 1_000_000, 5_000_000))
    cash_moves = ([{"from": "BOS", "to": "MIA", "amount": cash_out}]
                  if cash_out else [])
    return side, incoming_salaries, team_tpes, cash_moves, cash_out


def _expected_expanded_matching(salaries, in_total, outgoing, room_before,
                                capacities, required_bins):
    if outgoing <= 0 or in_total <= outgoing:
        return False
    if room_before > 0 and in_total <= outgoing + room_before + MATCHING_CUSHION:
        return False
    if not capacities:
        return True
    strict_limit = outgoing
    if room_before > 0:
        strict_limit += room_before + MATCHING_CUSHION
    return not _assignment_oracle(
        salaries, [strict_limit] + capacities, required_bins, strict_limit)


def test_expanded_matching_generated_inputs_match_strict_assignment_oracle():
    rng = random.Random(SEED + 4)
    for _ in range(CASES):
        salary_count = rng.randint(0, 4)
        salaries = [rng.randint(0, 14) for _ in range(salary_count)]
        tpe_count = rng.randint(0, 3)
        capacities = [rng.randint(0, 14) for _ in range(tpe_count)]
        required_bins = sum(1 << (index + 1) for index in range(tpe_count))
        outgoing = rng.randint(0, 24)
        room_before = rng.choice((0, rng.randint(0, 12)))
        in_total = sum(salaries)
        expected = _expected_expanded_matching(
            salaries, in_total, outgoing, room_before, capacities,
            required_bins)
        actual = _expanded_matching_use(
            salaries, in_total, outgoing, room_before, capacities,
            required_bins)
        assert actual == expected, (
            "expanded matching mismatch: "
            f"salaries={salaries!r} in_total={in_total!r} "
            f"outgoing={outgoing!r} room_before={room_before!r} "
            f"capacities={capacities!r} required_bins={required_bins!r} "
            f"actual={actual!r} expected={expected!r}")


def test_evaluate_team_generated_inputs_keep_matching_and_hard_caps_in_sync():
    rng = random.Random(SEED + 3)
    for _ in range(CASES):
        side, salaries, team_tpes, cash_moves, cash_out = _integration_input(rng)
        row, issues = _evaluate_team(
            "BOS", side, [], cash_moves, team_tpes, None, None, 0, 2026)
        expected_pay_after = (side["pay_before"] - side["out_total"]
                              + side["in_total"])
        expected_over_apron1 = expected_pay_after > CAP["apron1"]
        expected_over_apron2 = expected_pay_after > CAP["apron2"]
        expected_capacities = [
            item["amount"] + (0 if expected_over_apron1 else MATCHING_CUSHION)
            for item in team_tpes]
        capacities = [detail["capacity"] for detail in row["tpe_details"]]
        required_bins = sum(
            1 << (index + 1) for index in range(len(expected_capacities)))
        room_before = max(0, CAP["cap"] - side["pay_before"])
        expected_allow = _expected_allowed_incoming(
            side["out_total"], expected_over_apron1, room_before)
        expected_fit = _assignment_oracle(
            salaries, [expected_allow] + expected_capacities, required_bins)
        expected_expanded = _expected_expanded_matching(
            salaries, side["in_total"], side["out_total"], room_before,
            expected_capacities, required_bins)
        expected_aprons = set()
        if len(side["out_names"]) > 1 or cash_out or any(
                item["kind"] == "sign_and_trade" for item in team_tpes):
            expected_aprons.add("second apron")
        if expected_expanded or any(
                item["status"] == "prior_year" for item in team_tpes):
            expected_aprons.add("first apron")
        actual_aprons = set(filter(None, row["hard_cap"].split("+")))
        joined_issues = "\n".join(issues)
        first_violation = ("first apron" in expected_aprons
                           and expected_pay_after > CAP["apron1"])
        second_violation = ("second apron" in expected_aprons
                            and expected_pay_after > CAP["apron2"])
        case = (f"side={side!r} team_tpes={team_tpes!r} "
                f"cash_moves={cash_moves!r} row={row!r} issues={issues!r} "
                f"expected_fit={expected_fit!r} "
                f"expected_aprons={sorted(expected_aprons)!r}")
        assert row["payroll_after"] == expected_pay_after, case
        assert row["over_apron1"] == expected_over_apron1, case
        assert row["over_apron2"] == expected_over_apron2, case
        assert len(capacities) == len(team_tpes), case
        assert capacities == expected_capacities, case
        assert row["allowed_incoming"] == expected_allow, case
        assert row["matching_ok"] == expected_fit, case
        assert actual_aprons == expected_aprons, case
        assert (("hard-capped at the first apron" in joined_issues)
                == first_violation), case
        assert (("hard-capped at the second apron" in joined_issues)
                == second_violation), case
