"""In-game win probability for WPA. Logistic P(home win) on lead and clock.

get_win_prob in league.py is a pre-game ELO engine with no clock or score
input, so it cannot price plays. This module prices the game state instead:
P(home win) = sigmoid(B0 + B1 * lead / sqrt(seconds_remaining + SMOOTH)),
with lead = home score minus away score. WPA takes the difference of this
value before and after a play. At tipoff (lead 0, full clock) the model
returns about 0.54, the average home edge, so the pre-game ELO prior keeps
ownership of team strength and this model only moves the price once the
score moves.

Warehouse findings (silver_hist_pbp, 3.2M events, 2020-21 to 2024-25):
- One row per event detail, ordered per game by action_number. Numbers skip
  (400, 402, ...) and repeat for paired details (a turnover and its steal
  share one action_number), so analysis dedups to DISTINCT on
  (game_id, action_number) first.
- clock is an ISO duration such as PT07M49.00S counting down the period.
  Periods 1-4 start at PT12M00.00S. Overtime periods (5 and up, seen up to
  7) start at PT05M00.00S.
- score_home and score_away are VARCHAR and empty unless that event changed
  the score. Game state comes from forward-filling per game in
  action_number order. The final outcome is the last non-empty pair.
- location is h, v, or empty for neutral rows such as period markers.
  team_tricode names the acting team. action_type values include Made Shot,
  Missed Shot, Free Throw, Rebound, Turnover, Foul, Jump Ball, Timeout,
  Substitution, Violation, Ejection, and empty detail rows.
- The table holds no 2025-26 rows, so no 2025-26 data is involved anywhere.

Fit recipe (deterministic, stdlib only):
- Train on 2020-21 to 2023-24 events, one row per (game_id, action_number)
  with forward-filled lead, seconds remaining, and the final home-win flag.
  Deterministic sample: abs(hash(game_id || action_number)) % 10 == 0
  (about 244k rows). Newton iterations (IRLS) by hand, see fit_logistic.
- SMOOTH = 360.0 picked from {120, 240, 360, 600, 900} on the 2024-25
  holdout; 360 is the round middle value, not an extreme.
- Hold out all of 2024-25 (630,310 events). Decile calibration table:
  bucket 0: n=58986 pred=0.0389 actual=0.0278 err=0.0111
  bucket 1: n=37678 pred=0.1497 actual=0.1416 err=0.0081
  bucket 2: n=44430 pred=0.2512 actual=0.2666 err=0.0154
  bucket 3: n=53195 pred=0.3509 actual=0.3701 err=0.0192
  bucket 4: n=66625 pred=0.4512 actual=0.4668 err=0.0156
  bucket 5: n=85546 pred=0.5509 actual=0.5693 err=0.0184
  bucket 6: n=72731 pred=0.6495 actual=0.6495 err=0.0001
  bucket 7: n=61521 pred=0.7492 actual=0.7447 err=0.0045
  bucket 8: n=57368 pred=0.8504 actual=0.8423 err=0.0081
  bucket 9: n=92230 pred=0.9628 actual=0.9756 err=0.0128
  Max error 0.0192, under the 0.03 gate.
"""

import math

B0 = 0.159694
B1 = 5.853395
SMOOTH = 360.0
TIPOFF_SEC = 2880.0


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def parse_clock(clock: object) -> float | None:
    """Seconds left in the period for PT12M00.00S-style clocks, else None."""
    try:
        s = str(clock)
        if not s.startswith("PT") or not s.endswith("S"):
            return None
        m = s.index("M")
        minutes = int(s[2:m])
        seconds = float(s[m + 1:-1])
        total = minutes * 60.0 + seconds
        if total < 0 or minutes > 15:
            return None
        return total
    except (ValueError, AttributeError):
        return None


def seconds_remaining(clock: object, period: object) -> float | None:
    """Seconds left in the game. Overtime counts its own clock only."""
    left = parse_clock(clock)
    if left is None:
        return None
    try:
        p = int(period)
    except (TypeError, ValueError):
        return None
    if p < 1:
        return None
    if p <= 4:
        return left + 720.0 * (4 - p)
    return left


def win_probability(home_lead: float, sec_remaining: float) -> float:
    """P(home eventually wins) for a lead with sec_remaining left."""
    sec = max(0.0, float(sec_remaining))
    return _sigmoid(B0 + B1 * float(home_lead) / math.sqrt(sec + SMOOTH))


def win_probability_from_scores(
    score_home: object, score_away: object, clock: object, period: object,
) -> float | None:
    """Scoreboard strings plus clock to a probability. None when unknown."""
    try:
        lead = int(str(score_home)) - int(str(score_away))
    except (TypeError, ValueError):
        return None
    sec = seconds_remaining(clock, period)
    if sec is None:
        return None
    return win_probability(lead, sec)


def fit_logistic(
    rows: list, iters: int = 25,
) -> tuple:
    """IRLS fit of (B0, B1) on (lead, seconds, home_won) rows. Deterministic.

    Same input rows always give the same coefficients. Mirrors the offline
    fit recipe so tests can prove determinism without touching the warehouse.
    """
    b0, b1 = 0.0, 0.0
    xs = [(1.0, float(lead) / math.sqrt(max(0.0, float(sec)) + SMOOTH))
          for lead, sec, _ in rows]
    ys = [float(won) for _, _, won in rows]
    for _ in range(max(1, iters)):
        g0 = g1 = 0.0
        h00 = h01 = h11 = 0.0
        ll = 0.0
        for (x0, x1), y in zip(xs, ys):
            p = _sigmoid(b0 * x0 + b1 * x1)
            ll += y * math.log(p + 1e-15) + (1 - y) * math.log(1 - p + 1e-15)
            r = y - p
            w = p * (1 - p)
            g0 += r * x0
            g1 += r * x1
            h00 += w * x0 * x0
            h01 += w * x0 * x1
            h11 += w * x1 * x1
        det = h00 * h11 - h01 * h01 or 1e-12
        d0 = (h11 * g0 - h01 * g1) / det
        d1 = (h00 * g1 - h01 * g0) / det
        step = 1.0
        for _ in range(12):
            n0, n1 = b0 + step * d0, b1 + step * d1
            nll = 0.0
            for (x0, x1), y in zip(xs, ys):
                p = _sigmoid(n0 * x0 + n1 * x1)
                nll += y * math.log(p + 1e-15) + (1 - y) * math.log(1 - p + 1e-15)
            if nll > ll:
                b0, b1 = n0, n1
                break
            step *= 0.5
    return (b0, b1)
