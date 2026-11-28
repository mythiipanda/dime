import os
import random
from itertools import combinations
from collections import Counter
from itertools import product

from shared.tools.cap_rules import (
    CAP,
    allowed_incoming,
    hard_cap_consequences,
    matching_election,
)
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
STANDARD_MATCH_RULE = ("standard TPE matching: 100% of outgoing salary plus "
                       "applicable cushion")
AGGREGATED_STANDARD_MATCH_RULE = (
    "aggregated standard TPE matching: 100% of aggregated outgoing salary "
    "plus applicable cushion")
CAP_ROOM_MATCH_RULE = "cap room plus outgoing salary plus $250k (under the cap)"
DECLARED_TPE_MATCH_RULE = (
    "declared TPE capacity: separate non-combined exception bin")
NO_SALARY_MATCH_RULE = "no salary matching required (no incoming player salary)"
NO_AVAILABLE_MATCH_RULE = ("no available salary-matching structure "
                           "(no outgoing player salary)")


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
    if outgoing <= 0 and cap_room <= 0:
        return 0, NO_AVAILABLE_MATCH_RULE
    if over_apron1:
        return outgoing, "100% (above the first apron)"
    if outgoing <= EXPANDED_LOW_MAX:
        matched = outgoing * 2 + MATCHING_CUSHION
        rule = "200% plus $250k (below the first apron)"
    elif outgoing <= EXPANDED_MID_MAX:
        matched = outgoing + EXPANDED_MATCHING_CUSHION
        rule = "outgoing salary plus $9.096M (below the first apron)"
    else:
        matched = outgoing * 5 // 4 + MATCHING_CUSHION
        rule = "125% plus $250k (below the first apron)"
    room_allowance = outgoing + cap_room + MATCHING_CUSHION
    if cap_room > 0 and room_allowance > matched:
        return room_allowance, CAP_ROOM_MATCH_RULE
    return matched, rule


def _money_edges():
    low = EXPANDED_LOW_MAX
    mid = EXPANDED_MID_MAX
    values = {0, 1, 249_999, 250_000, low - 1, low, low + 1,
              mid - 1, mid, mid + 1, 60_000_000}
    return sorted(values)


def test_allowed_incoming_rule_identity_at_scaled_band_boundaries():
    cases = (
        (EXPANDED_LOW_MAX, EXPANDED_LOW_MAX * 2 + MATCHING_CUSHION,
         "200% plus $250k (below the first apron)"),
        (EXPANDED_LOW_MAX + 1,
         EXPANDED_LOW_MAX + 1 + EXPANDED_MATCHING_CUSHION,
         "outgoing salary plus $9.096M (below the first apron)"),
        (EXPANDED_MID_MAX, EXPANDED_MID_MAX + EXPANDED_MATCHING_CUSHION,
         "outgoing salary plus $9.096M (below the first apron)"),
        (EXPANDED_MID_MAX + 1,
         (EXPANDED_MID_MAX + 1) * 5 // 4 + MATCHING_CUSHION,
         "125% plus $250k (below the first apron)"),
    )
    for outgoing, expected_allow, expected_rule in cases:
        assert allowed_incoming(outgoing, False) == (
            expected_allow, expected_rule), (
            f"boundary rule identity changed: outgoing={outgoing!r}")


def _expected_matching_election(incoming, outgoing, cap_room=0,
                                cushion=MATCHING_CUSHION, outgoing_count=1,
                                expanded_matching=False,
                                uses_declared_tpe=False):
    simultaneous = ("aggregated_standard" if outgoing_count > 1
                    else "standard_simultaneous")
    if incoming <= 0:
        base = "no_salary_matching"
    elif expanded_matching:
        base = "expanded"
    elif cap_room > 0 and incoming <= outgoing + cap_room + cushion:
        base = "cap_room"
    elif outgoing > 0 and incoming <= outgoing + cushion:
        base = simultaneous
    elif uses_declared_tpe and outgoing > 0:
        base = simultaneous
    elif uses_declared_tpe:
        base = "declared_tpe"
    elif outgoing > 0 and incoming > outgoing + cushion:
        base = "expanded"
    else:
        base = "no_available_structure"
    mechanisms = [base]
    if uses_declared_tpe and base != "declared_tpe":
        mechanisms.append("declared_tpe")
    return {"matching_structure": "+".join(mechanisms),
            "matching_mechanisms": mechanisms,
            "expanded_required": bool(expanded_matching)}


def test_matching_election_oracle_matches_production_vector_matrix():
    vectors = (
        ({"incoming": 0, "outgoing": 20_000_000}, "no_salary_matching"),
        ({"incoming": 20_100_000, "outgoing": 20_000_000},
         "standard_simultaneous"),
        ({"incoming": 20_250_000, "outgoing": 20_000_000},
         "standard_simultaneous"),
        ({"incoming": 20_100_000, "outgoing": 20_000_000,
          "cap_room": 14_961_000}, "cap_room"),
        ({"incoming": 30_000_000, "outgoing": 20_000_000,
          "cap_room": 14_961_000}, "cap_room"),
        ({"incoming": 30_100_000, "outgoing": 30_000_000,
          "outgoing_count": 2}, "aggregated_standard"),
        ({"incoming": 20_250_001, "outgoing": 20_000_000,
          "expanded_matching": True}, "expanded"),
        ({"incoming": 20_000_001, "outgoing": 20_000_000, "cushion": 0,
          "expanded_matching": True}, "expanded"),
        ({"incoming": 22_000_000, "outgoing": 20_000_000,
          "uses_declared_tpe": True}, "standard_simultaneous"),
        ({"incoming": 8_000_000, "outgoing": 0,
          "uses_declared_tpe": True}, "declared_tpe"),
        ({"incoming": 8_000_000, "outgoing": 0},
         "no_available_structure"),
    )
    for vector, structure in vectors:
        expected = _expected_matching_election(**vector)
        actual = matching_election(**vector)
        case = f"vector={vector!r} actual={actual!r} expected={expected!r}"
        assert expected["matching_mechanisms"][0] == structure, case
        assert actual["matching_structure"] == expected["matching_structure"], case
        assert actual["matching_mechanisms"] == expected["matching_mechanisms"], case
        assert actual["expanded_required"] == expected["expanded_required"], case


def _expected_operative_match_rule(expanded_rule, election):
    selected = election["matching_mechanisms"][0]
    if selected == "standard_simultaneous":
        return STANDARD_MATCH_RULE
    if selected == "aggregated_standard":
        return AGGREGATED_STANDARD_MATCH_RULE
    if selected == "cap_room":
        return CAP_ROOM_MATCH_RULE
    if selected == "declared_tpe":
        return DECLARED_TPE_MATCH_RULE
    if selected == "no_salary_matching":
        return NO_SALARY_MATCH_RULE
    if selected == "no_available_structure":
        return NO_AVAILABLE_MATCH_RULE
    return expanded_rule


def test_generated_matching_inverse_and_monotonicity():
    rng = random.Random(SEED + 1)
    outgoing_values = _money_edges() + [
        rng.randint(0, 80_000_000) for _ in range(CASES)]
    for outgoing in outgoing_values:
        for over_apron1 in (False, True):
            rooms = (0, 1, rng.randint(2, 30_000_000))
            for room in rooms:
                allow, rule = allowed_incoming(outgoing, over_apron1, room)
                expected_allow, expected_rule = _expected_allowed_incoming(
                    outgoing, over_apron1, room)
                assert (allow, rule) == (expected_allow, expected_rule), (
                    "matching allowance or rule differs from the 2026-27 band: "
                    f"outgoing={outgoing!r} over_apron1={over_apron1!r} "
                    f"cap_room={room!r} allow={allow!r} rule={rule!r} "
                    f"expected_allow={expected_allow!r} "
                    f"expected_rule={expected_rule!r}")
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
            result = hard_cap_consequences("BOS", payroll, lines=dict(CAP), **flags)
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
            assert (("would exceed the first apron" in joined_issues
                     and "transaction is prohibited" in joined_issues)
                    == ("first apron" in expected_violations)), case
            assert (("would exceed the second apron" in joined_issues
                     and "transaction is prohibited" in joined_issues)
                    == ("second apron" in expected_violations)), case


def _generated_tpe(rng, index):
    status = rng.choice(("current_year", "prior_year"))
    origin_year = 2026 if status == "current_year" else 2025
    kind = "sign_and_trade" if rng.random() < 0.2 else "ordinary"
    return {"team": "BOS", "amount": rng.randint(2_000_000, 14_000_000),
            "kind": kind, "origin_year": origin_year,
            "origin_season": f"{origin_year}-{(origin_year + 1) % 100:02d}",
            "status": status, "legacy_defaults": False,
            "timing_basis": "season_approximate", "as_of_date": None,
            "origin_date": None, "expiry_date": None,
            "effective_expiry_date": None, "expiry_date_derived": False}


def _incoming_salary(rng):
    boundary_roll = rng.random()
    if boundary_roll < 0.15:
        return rng.choice((1, 249_999, 250_000, 250_001, 500_000, 999_999))
    if boundary_roll < 0.35:
        return rng.randint(1, 999_999)
    return rng.randint(1_000_000, 38_000_000)


def _integration_input(rng):
    outgoing_count = rng.choice((0, 1, 1, 2, 3))
    outgoing = (rng.randint(5_000_000, 60_000_000)
                if outgoing_count else 0)
    incoming_count = rng.randint(0, 4)
    incoming_salaries = [_incoming_salary(rng) for _ in range(incoming_count)]
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


def _oracle_first_capacity(outgoing, allow, room_before):
    if outgoing <= 0 and room_before <= 0:
        return 0
    return allow


def _expected_expanded_matching(salaries, in_total, outgoing, room_before,
                                capacities, required_bins,
                                cushion=MATCHING_CUSHION):
    if outgoing <= 0 or in_total <= outgoing:
        return False
    if in_total <= outgoing + cushion:
        return False
    if room_before > 0 and in_total <= outgoing + room_before + cushion:
        return False
    if not capacities:
        return True
    strict_limit = outgoing + cushion
    if room_before > 0:
        strict_limit += room_before
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
        cushion = rng.randint(0, 3)
        in_total = sum(salaries)
        expected = _expected_expanded_matching(
            salaries, in_total, outgoing, room_before, capacities,
            required_bins, cushion)
        actual = _expanded_matching_use(
            salaries, in_total, outgoing, room_before, capacities,
            required_bins, cushion)
        assert actual == expected, (
            "expanded matching mismatch: "
            f"salaries={salaries!r} in_total={in_total!r} "
            f"outgoing={outgoing!r} room_before={room_before!r} "
            f"cushion={cushion!r} capacities={capacities!r} "
            f"required_bins={required_bins!r} "
            f"actual={actual!r} expected={expected!r}")


def test_expanded_matching_standard_cushion_exact_boundaries():
    cases = (
        (20_250_000, 20_000_000, 0, MATCHING_CUSHION, False),
        (20_250_001, 20_000_000, 0, MATCHING_CUSHION, True),
        (20_000_000, 20_000_000, 0, 0, False),
        (20_000_001, 20_000_000, 0, 0, True),
        (30_250_000, 20_000_000, 10_000_000, MATCHING_CUSHION, False),
        (30_250_001, 20_000_000, 10_000_000, MATCHING_CUSHION, True),
    )
    for incoming, outgoing, room, cushion, expected in cases:
        actual = _expanded_matching_use(
            [incoming], incoming, outgoing, room, [], 0, cushion)
        oracle = _expected_expanded_matching(
            [incoming], incoming, outgoing, room, [], 0, cushion)
        assert oracle == expected
        assert actual == expected, (
            f"incoming={incoming!r} outgoing={outgoing!r} room={room!r} "
            f"cushion={cushion!r} actual={actual!r} expected={expected!r}")


def _elective_oracle(salaries, first_capacity, capacities):
    if _assignment_oracle(salaries, [first_capacity], 0):
        return (), True
    for size in range(1, len(capacities) + 1):
        for combo in combinations(range(len(capacities)), size):
            bins = [capacities[index] for index in combo]
            required = sum(1 << (position + 1) for position in range(len(bins)))
            if _assignment_oracle(salaries, [first_capacity] + bins, required):
                return combo, True
    return None, False


def test_evaluate_team_generated_inputs_keep_matching_and_hard_caps_in_sync():
    rng = random.Random(SEED + 3)
    distribution = Counter()
    for _ in range(CASES):
        side, salaries, team_tpes, cash_moves, cash_out = _integration_input(rng)
        row, issues = _evaluate_team(
            "BOS", side, [], cash_moves, team_tpes, None, None, 0, 2026,
            dict(CAP))
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
        if side["out_total"]:
            distribution["positive_outgoing"] += 1
        elif side["in_total"] <= 0:
            distribution["zero_outgoing_no_incoming"] += 1
        elif room_before > 0:
            distribution["zero_outgoing_cap_room"] += 1
        elif team_tpes:
            distribution["zero_outgoing_declared_tpe"] += 1
        else:
            distribution["zero_outgoing_no_available_structure"] += 1
        expected_allow, expected_band_rule = _expected_allowed_incoming(
            side["out_total"], expected_over_apron1, room_before)
        first_capacity = _oracle_first_capacity(
            side["out_total"], expected_allow, room_before)
        combo, elected_fit = _elective_oracle(
            salaries, first_capacity, expected_capacities)
        expected_fit = elected_fit
        elected_capacities = ([expected_capacities[index] for index in combo]
                              if combo else [])
        if combo is None and expected_capacities:
            oracle_capacities = expected_capacities
        else:
            oracle_capacities = elected_capacities
        oracle_required = sum(
            1 << (index + 1) for index in range(len(oracle_capacities)))
        cushion = 0 if expected_over_apron1 else MATCHING_CUSHION
        expected_expanded = _expected_expanded_matching(
            salaries, side["in_total"], side["out_total"], room_before,
            oracle_capacities, oracle_required, cushion)
        tpe_in_structure = (bool(combo)
                            or (combo is None and bool(expected_capacities)))
        expected_election = _expected_matching_election(
            side["in_total"], side["out_total"], room_before, cushion,
            len(side["out_names"]), expected_expanded, tpe_in_structure)
        expected_match_rule = _expected_operative_match_rule(
            expected_band_rule, expected_election)
        elected_rows = ([team_tpes[index] for index in combo]
                        if combo else [])
        expected_aprons = set()
        if len(side["out_names"]) > 1 or cash_out or any(
                item["kind"] == "sign_and_trade" for item in elected_rows):
            expected_aprons.add("second apron")
        if expected_expanded or any(
                item["status"] == "prior_year" for item in elected_rows):
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
        assert row["matching_structure"] == (
            expected_election["matching_structure"]), case
        assert row["matching_mechanisms"] == (
            expected_election["matching_mechanisms"]), case
        assert row["expanded_required"] == expected_expanded, case
        assert row["match_rule"] == expected_match_rule, case
        assert actual_aprons == expected_aprons, case
        assert (("would exceed the first apron" in joined_issues
                 and "transaction is prohibited" in joined_issues)
                == first_violation), case
        assert (("would exceed the second apron" in joined_issues
                 and "transaction is prohibited" in joined_issues)
                == second_violation), case
    assert distribution["positive_outgoing"] > 0, dict(distribution)
    assert distribution["zero_outgoing_declared_tpe"] > 0, dict(distribution)
    assert distribution["zero_outgoing_no_available_structure"] > 0, (
        dict(distribution))


def _vector_side(pay_before, outgoing, incoming_salaries, outgoing_count=1):
    in_rows = [{"player": f"Incoming {index}", "salary": salary}
               for index, salary in enumerate(incoming_salaries, 1)]
    return {"out_names": [f"Outgoing {index}"
                          for index in range(outgoing_count, 0, -1)],
            "out_total": outgoing,
            "in_names": [row["player"] for row in in_rows],
            "in_rows": in_rows,
            "in_total": sum(incoming_salaries),
            "pay_before": pay_before}


def _evaluate_vector(pay_before, outgoing, incoming_salaries, outgoing_count=1,
                     team_tpes=None):
    side = _vector_side(pay_before, outgoing, incoming_salaries,
                        outgoing_count)
    return _evaluate_team(
        "BOS", side, [], [], team_tpes or [], None, None, 0, 2026,
        dict(CAP))


def _active_tpe_vector(amount, status="current_year"):
    origin_year = 2026 if status == "current_year" else 2025
    return {"team": "BOS", "amount": amount, "kind": "ordinary",
            "origin_year": origin_year,
            "origin_season": f"{origin_year}-{(origin_year + 1) % 100:02d}",
            "status": status, "legacy_defaults": False,
            "timing_basis": "season_approximate", "as_of_date": None,
            "origin_date": None, "expiry_date": None,
            "effective_expiry_date": None, "expiry_date_derived": False}


def test_allowed_incoming_zero_outgoing_without_room_has_no_capacity():
    assert allowed_incoming(0, False, 0) == (0, NO_AVAILABLE_MATCH_RULE)
    assert allowed_incoming(0, True, 0) == (0, NO_AVAILABLE_MATCH_RULE)
    assert allowed_incoming(0, False, 1) == (250_001, CAP_ROOM_MATCH_RULE)
    assert allowed_incoming(1, False, 0) == (
        250_002, "200% plus $250k (below the first apron)")


def test_outgoing_needed_requires_positive_outgoing_without_room():
    assert _outgoing_needed(1, False, 0) == 1
    assert _outgoing_needed(250_000, False, 0) == 1
    assert _outgoing_needed(250_001, False, 0) == 1
    assert _outgoing_needed(250_002, False, 0) == 1
    assert _outgoing_needed(250_003, False, 0) == 2
    assert _outgoing_needed(250_000, False, 1) == 0


def test_evaluate_team_zero_outgoing_positive_incoming_has_no_matching_capacity():
    for incoming in (1, 250_000, 250_001):
        row, issues = _evaluate_vector(
            200_000_000, 0, [incoming], outgoing_count=0)
        joined_issues = "\n".join(issues)
        case = f"incoming={incoming!r} row={row!r} issues={issues!r}"
        assert row["allowed_incoming"] == 0, case
        assert row["matching_ok"] is False, case
        assert row["matching_structure"] == "no_available_structure", case
        assert row["matching_mechanisms"] == ["no_available_structure"], case
        assert row["match_rule"] == NO_AVAILABLE_MATCH_RULE, case
        assert row["expanded_required"] is False, case
        assert row["hard_cap"] == "", case
        assert "takes back too much" in joined_issues, case
        assert " vs $0 allowed under " in joined_issues, case


def test_evaluate_team_zero_outgoing_edge_mechanisms_remain_available():
    row, issues = _evaluate_vector(
        160_000_000, 0, [250_000], outgoing_count=0)
    case = f"cap_room row={row!r} issues={issues!r}"
    assert row["allowed_incoming"] == 5_211_000, case
    assert row["matching_ok"] is True, case
    assert row["matching_structure"] == "cap_room", case
    assert row["match_rule"] == CAP_ROOM_MATCH_RULE, case
    assert issues == [], case

    team_tpes = [_active_tpe_vector(2_000_000)]
    row, issues = _evaluate_vector(
        200_000_000, 0, [2_250_000], outgoing_count=0,
        team_tpes=team_tpes)
    case = f"declared_tpe row={row!r} issues={issues!r}"
    assert row["allowed_incoming"] == 0, case
    assert row["matching_ok"] is True, case
    assert row["matching_structure"] == "declared_tpe", case
    assert row["match_rule"] == DECLARED_TPE_MATCH_RULE, case
    assert issues == [], case

    row, issues = _evaluate_vector(
        200_000_000, 0, [2_250_001], outgoing_count=0,
        team_tpes=team_tpes)
    case = f"declared_tpe_over row={row!r} issues={issues!r}"
    assert row["matching_ok"] is False, case
    assert row["matching_structure"] == "declared_tpe", case
    assert any("traded player exceptions cannot be combined" in issue
               for issue in issues), case

    row, issues = _evaluate_vector(
        200_000_000, 0, [], outgoing_count=0)
    case = f"no_incoming row={row!r} issues={issues!r}"
    assert row["allowed_incoming"] == 0, case
    assert row["matching_ok"] is True, case
    assert row["matching_structure"] == "no_salary_matching", case
    assert row["match_rule"] == NO_SALARY_MATCH_RULE, case
    assert issues == [], case


def test_evaluate_team_outgoing_salary_presence_not_slot_count_controls_matching():
    row, issues = _evaluate_vector(
        200_000_000, 1_400_000, [1_500_000], outgoing_count=1)
    case = f"minimum row={row!r} issues={issues!r}"
    assert row["allowed_incoming"] == 3_050_000, case
    assert row["matching_ok"] is True, case
    assert row["matching_structure"] == "standard_simultaneous", case
    assert row["match_rule"] == STANDARD_MATCH_RULE, case

    row, issues = _evaluate_vector(
        200_000_000, 0, [1], outgoing_count=1)
    case = f"zero_salary_slot row={row!r} issues={issues!r}"
    assert row["allowed_incoming"] == 0, case
    assert row["matching_ok"] is False, case
    assert row["matching_structure"] == "no_available_structure", case
    assert row["match_rule"] == NO_AVAILABLE_MATCH_RULE, case


def test_evaluate_team_propagates_least_restrictive_rule_identity_vectors():
    cases = (
        (195_000_000, 20_000_000, [20_100_000], 1,
         "standard_simultaneous", STANDARD_MATCH_RULE, False, "", []),
        (195_000_000, 20_000_000, [20_250_000], 1,
         "standard_simultaneous", STANDARD_MATCH_RULE, False, "", []),
        (195_000_000, 20_000_000, [20_250_001], 1,
         "expanded", "outgoing salary plus $9.096M (below the first apron)",
         True, "first apron", []),
        (209_000_000, 20_000_000, [20_100_000], 1,
         "expanded", "100% (above the first apron)",
         True, "first apron", ["first apron"]),
        (209_100_000, 20_000_000, [20_000_000], 1,
         "standard_simultaneous", STANDARD_MATCH_RULE, False, "", []),
        (150_000_000, 20_000_000, [20_100_000], 1,
         "cap_room", CAP_ROOM_MATCH_RULE, False, "", []),
    )
    for (payroll, outgoing, incoming, outgoing_count, structure,
         match_rule, expanded, hard_cap, violations) in cases:
        row, issues = _evaluate_vector(
            payroll, outgoing, incoming, outgoing_count)
        case = (f"payroll={payroll!r} outgoing={outgoing!r} "
                f"incoming={incoming!r} row={row!r} issues={issues!r}")
        assert row["matching_structure"] == structure, case
        assert row["matching_mechanisms"] == [structure], case
        assert row["match_rule"] == match_rule, case
        assert row["expanded_required"] is expanded, case
        assert row["hard_cap"] == hard_cap, case
        assert row["hard_cap_violations"] == violations, case


def test_evaluate_team_first_apron_cushion_uses_strict_boundary_vectors():
    outgoing = 20_000_000
    cases = (
        (CAP["apron1"], MATCHING_CUSHION,
         "standard_simultaneous", False, "", []),
        (CAP["apron1"] + 1, MATCHING_CUSHION,
         "expanded", True, "first apron", ["first apron"]),
        (CAP["apron1"], MATCHING_CUSHION + 1,
         "expanded", True, "first apron", []),
        (CAP["apron1"] + 1, MATCHING_CUSHION + 1,
         "expanded", True, "first apron", ["first apron"]),
    )
    for (payroll_after, surplus, structure, expanded, hard_cap,
         violations) in cases:
        incoming = outgoing + surplus
        pay_before = payroll_after + outgoing - incoming
        row, issues = _evaluate_vector(pay_before, outgoing, [incoming])
        expected_over = payroll_after > CAP["apron1"]
        expected_cushion = 0 if expected_over else MATCHING_CUSHION
        expected_expanded = incoming > outgoing + expected_cushion
        case = (f"payroll_after={payroll_after!r} outgoing={outgoing!r} "
                f"incoming={incoming!r} row={row!r} issues={issues!r}")
        assert expected_expanded is expanded, case
        assert row["payroll_after"] == payroll_after, case
        assert row["over_apron1"] is expected_over, case
        assert row["matching_structure"] == structure, case
        assert row["matching_mechanisms"] == [structure], case
        assert row["expanded_required"] is expected_expanded, case
        assert row["hard_cap"] == hard_cap, case
        assert row["hard_cap_violations"] == violations, case
        assert any("Expanded Traded Player Exception" in issue
                   and "transaction is prohibited" in issue
                   for issue in issues) == bool(violations), case


def test_evaluate_team_aggregated_standard_is_only_second_apron_trigger():
    row, issues = _evaluate_vector(
        195_000_000, 20_000_000, [20_100_000], outgoing_count=2)
    assert row["matching_structure"] == "aggregated_standard"
    assert row["matching_mechanisms"] == ["aggregated_standard"]
    assert row["match_rule"] == AGGREGATED_STANDARD_MATCH_RULE
    assert row["expanded_required"] is False
    assert row["hard_cap"] == "second apron"
    assert row["hard_cap_causes"] == {"second apron": ["aggregation"]}
    assert row["hard_cap_violations"] == []
    assert not any("first apron" in issue for issue in issues)


def test_evaluate_team_cap_room_precedes_aggregated_standard_but_aggregation_remains():
    row, issues = _evaluate_vector(
        150_000_000, 20_000_000, [20_100_000], outgoing_count=2)
    assert row["matching_structure"] == "cap_room"
    assert row["matching_mechanisms"] == ["cap_room"]
    assert row["match_rule"] == CAP_ROOM_MATCH_RULE
    assert row["expanded_required"] is False
    assert row["hard_cap"] == "second apron"
    assert row["hard_cap_causes"] == {"second apron": ["aggregation"]}
    assert row["hard_cap_violations"] == []
    assert not any("first apron" in issue for issue in issues)
