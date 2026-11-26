import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SKILL = Path(__file__).resolve().parent.parent / "analyst" / "skills" / "statistical-modeling" / "SKILL.md"

def _extract_helper():
    text = SKILL.read_text()
    m = re.search(r"```python\n(def eb_beta_binomial_mom.*?)```", text, re.S)
    assert m, "eb_beta_binomial_mom helper missing from statistical-modeling SKILL.md"
    ns = {}
    exec(m.group(1), ns)
    return ns["eb_beta_binomial_mom"]

def test_helper_present_and_callable():
    fn = _extract_helper()
    mu, M = fn([(100, 36), (200, 74), (150, 55)])
    assert 0 < mu < 1
    assert M != 0

def test_helper_recovers_known_prior_strength():
    import random
    random.seed(7)
    fn = _extract_helper()
    true_mu, true_M = 0.36, 350.0
    rows = []
    for _ in range(280):
        n = random.randint(100, 800)
        a = true_mu * true_M
        b = (1 - true_mu) * true_M
        p = random.betavariate(a, b)
        x = sum(1 for _ in range(n) if random.random() < p)
        rows.append((n, x))
    mu, M = fn(rows)
    assert abs(mu - true_mu) < 0.02
    assert abs(M - true_M) / true_M < 0.35

def test_naive_variance_without_noise_subtraction_underestimates_M():
    import random
    random.seed(11)
    fn = _extract_helper()
    true_mu, true_M = 0.36, 350.0
    rows = []
    for _ in range(280):
        n = random.randint(100, 800)
        p = random.betavariate(true_mu * true_M, (1 - true_mu) * true_M)
        x = sum(1 for _ in range(n) if random.random() < p)
        rows.append((n, x))
    _, M_correct = fn(rows)
    k = len(rows)
    S = sum(n for n, _ in rows)
    mu = sum(x for _, x in rows) / S
    v = sum(n * (x / n - mu) ** 2 for n, x in rows) / S
    M_naive = mu * (1 - mu) / v - 1
    assert M_naive < M_correct

def test_no_duplicate_sections_in_any_skill():
    import glob as _glob
    for path in _glob.glob(str(SKILL.parent.parent / "*" / "SKILL.md")):
        text = Path(path).read_text()
        import re as _re
        heads = [h.strip().lower() for h in _re.findall(r"^#{2,4}\s+(.*)$", text, _re.M)]
        dupes = {h for h in heads if heads.count(h) > 1}
        assert not dupes, f"{path}: duplicate sections {dupes}"
