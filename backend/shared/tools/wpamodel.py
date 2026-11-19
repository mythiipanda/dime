
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
    sec = max(0.0, float(sec_remaining))
    return _sigmoid(B0 + B1 * float(home_lead) / math.sqrt(sec + SMOOTH))

def win_probability_from_scores(
    score_home: object, score_away: object, clock: object, period: object,
) -> float | None:
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
