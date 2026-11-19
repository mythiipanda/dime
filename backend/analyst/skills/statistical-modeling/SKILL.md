---
name: statistical-modeling
description: Fit, validate, and interpret NBA statistical estimates, including RAPM, shrinkage, weighted regression, clustered uncertainty, and win probability. Use when the decision depends on whether an observed difference is trustworthy.
---

# Statistical modeling and uncertainty

## Specify the comparison before fitting

1. Define the estimand, eligible cohort, date range, observation grain, weights, and units. Honor the requested method and seed. Verify schema and join keys; compare counts and distinct keys before and after joins and state material exclusions. Uniform duplication inflates totals but cancels in a rate; uneven duplication can bias both. Keep unavailable values separate from zeroes.
2. Use SQL to prepare the cohort at the right grain and Python to fit or resample it. In `run_python`, `con` is read-only and `np` is NumPy. Aggregate sufficient statistics in SQL when possible; keep full-precision values until display. Assign a compact dict or list of dicts to `out` with estimates, denominators, and diagnostics. Check that the computation succeeded before citing it.
3. Give the point estimate and a relevant comparator. Show the sample size (including independent clusters when applicable). If inference is warranted, give the interval and its meaning at zero and at the decision threshold. If uncertainty was not estimated, call the gap descriptive; don't imply significance or causality. Identify the specific bias or coverage limit most likely to change the recommendation.

## Shooting rates: empirical Bayes shrinkage

- Fit the prior in the specified reference cohort, then score the target cohort. Count makes `k_i` and attempts `n_i` at the same player and shot-population grain. For an attempt-weighted method of moments, use `mu = sum(k) / sum(n)`, `s2 = average((k/n - mu)**2, weights=n)`, and approximate the binomial noise with `average(mu*(1-mu)/n, weights=n)`. Use the same weighting for both variance terms.
- Subtract noise from `s2` to estimate latent variance `tau2`. For a finite Beta prior, `M = mu*(1-mu)/tau2 - 1`, with shape parameters `M*mu` and `M*(1-mu)`. If latent variance is nonpositive, report that these moments don't identify a finite strength; disclose any requested floor, cap, or fallback. A supplied fixed prior is not a fitted empirical prior.
- The posterior mean is `(k + M*mu)/(n + M)`. Report raw and shrunk rates, attempts, and signed `shrunk - raw` in percentage points when ranking shifts. Low-volume rates move more toward the prior; a raw leaderboard is not a reliable ranking of underlying skill.

## Cluster bootstrap: differences of rates

Use whole games or the requested independent unit when events within it are dependent. Build a NumPy array with one row per cluster in stable key order and columns `[a_num, a_den, b_num, b_den]`. Sample the same number of clusters with replacement, retaining repeated draws and both groups from each draw. Recompute the difference of pooled rates, not the mean of the per-cluster percentages. For eFG%, use `FGM + 0.5*3PM` as the numerator.

```python
def bootstrap_rate_gap(counts, seed, draws):
    n_clusters = len(counts)
    if n_clusters < 2:
        raise ValueError("At least two clusters are required")
    rng = np.random.default_rng(seed)
    gaps = []
    for _ in range(draws):
        a_num, a_den, b_num, b_den = counts[rng.integers(n_clusters, size=n_clusters)].sum(axis=0)
        if a_den > 0 and b_den > 0:
            gaps.append(a_num / a_den - b_num / b_den)
    if len(gaps) < 2:
        raise ValueError("Too few draws with both groups represented")
    return np.std(gaps, ddof=1), np.percentile(gaps, [2.5, 97.5]).tolist(), len(gaps)
```

Compute the observed gap on original totals. Report the seed, cluster count, requested and usable draws, bootstrap SE, and percentile interval. If many draws lack a denominator, flag the sparse comparison rather than treating the interval as robust. An interval excluding zero need not imply a decision-relevant difference.

## Regularized adjusted plus-minus

- Use the requested exposure and target: possession-level points and stint-level net ratings are not interchangeable. Encode player participation at that grain, keeping rows that contain players outside the fitted cohort unless the specification excludes them. Verify the response center and scale, offense/defense sign convention, exposure weights, and ridge penalty.
- Use a linear solve for `(X.T @ W @ X + lambda * I) beta = X.T @ W @ y`, not a matrix inverse. With unit weights omit `W`; with a prior mean add `lambda * prior_mean` to the right side. If fitting an intercept, leave it unpenalized. Use a sparse design or accumulate cross-products for large possession sets.
- Ridge stabilizes estimates from teammates who share most of their minutes, at the cost of shrinking coefficients. Report the row and player counts and the penalty. Compare correlation and rank overlap with a reference on the same matched player population and season; differences in samples, targets, and regularization can affect agreement. Do not present the coefficients as causal effects.

## Weighted regressions and forecasts

- Fit WLS by multiplying the design (including its intercept) and response by `sqrt(w)`, then using least squares. Compute weighted R² as `1 - sum(w*(y-yhat)**2) / sum(w*(y-weighted_mean(y))**2)` when the denominator is positive. For a quadratic, the slope at `x` is `b1 + 2*b2*x`; the vertex `-b1/(2*b2)` is a peak only if `b2 < 0` and is not supported outside the observed range.
- Distinguish a cross-sectional aging curve from within-player decline. Older players who still clear availability and minutes filters are selected survivors; weighting by minutes further emphasizes players still earning rotation roles. This can flatten apparent late-career decline. Don't use the cohort curve as a player-specific forecast without further checks.
- For win probability, use only time, score, possession and pregame information available at prediction time. Evaluate chronologically against a simple baseline; for probabilities, check calibration and Brier score. Quantify possession leverage as the change between explicitly defined scoring and stopping scenarios, not as a causal player contribution.

## Explain what changes the decision

- For lineup and on/off gaps, compare possession counts and note teammate, opponent, and game-state mix. A small sample or a different rotation assignment can reverse the apparent ranking. Before recommending a rotation change, distinguish a testable adjustment such as staggering creators from a claim that the raw split proves it would work.
- For shot mix and trends, separate changes in opportunity share from conversion within each group. Describe the most material phase or inflection, not just the endpoints. A threshold or quadrant partitions the observed cohort; it isn't evidence of a natural cutoff.
- State the most useful next check when it would alter the decision: a wider sample, a matched comparison, or sensitivity to a plausible filter or model choice. Don't add a model to a descriptive request merely to produce an interval.
