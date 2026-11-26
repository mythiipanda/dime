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

- Fit the prior only on the specified reference cohort, then score the target cohort. Supply one row per eligible player with positive attempts and makes between zero and attempts, using the same shot population for both counts. `mu` comes from the same reference rows as the variance. For an attempt-weighted method of moments, run this helper:

```python
def eb_beta_binomial_mom(rows):
    # rows: list of (attempts, makes) for the reference cohort, one row per player
    k = len(rows)
    S = sum(n for n, _ in rows)
    mu = sum(x for _, x in rows) / S
    v = sum(n * (x / n - mu) ** 2 for n, x in rows) / S
    noise = k * mu * (1 - mu) / S
    tau2 = v - noise
    M = mu * (1 - mu) / tau2 - 1
    return mu, M
```

The noise subtraction is not optional: the observed attempt-weighted variance of shooting proportions includes binomial sampling noise `mu(1-mu)/n_i` per player, which under the same attempt weighting sums to `k * mu * (1 - mu) / S`. Without subtracting it, `M` comes out roughly half its true value and every player is over-shrunk toward the mean. Reference check on 2024-25 NBA 3P% (high-volume cohort FG3A >= 100): `mu = 0.3652`, `M = 348.57`. The naive variance-only solve gives 159 — if your M is near 159 on that cohort, the noise term was dropped. Shrunk rate per player: `(makes + M * mu) / (attempts + M)`.

In closed-form matrix notation:
$$\hat{\beta} = (X^T W X + \lambda I)^{-1} X^T W Y$$

- $X \in \mathbb{R}^{N \times P}$: Stint design matrix. For stint $i$, players on offense receive $+1$, players on defense receive $-1$, and unrepresented players receive $0$.
- $W \in \mathbb{R}^{N \times N}$: Diagonal weight matrix where $W_{ii} = \text{possessions}_i$.
- $Y \in \mathbb{R}^N$: Target net rating per stint, defined as $100 \times \frac{\text{PTS}_{\text{offense}} - \text{PTS}_{\text{defense}}}{\text{possessions}_i}$.
- $\lambda$: Ridge L2 penalty. Standard values:
  - Single-season stint data (15,000–30,000 stints): $\lambda \in [2000, 3500]$.
  - Multi-season stint data (3 seasons, ~75,000 stints): $\lambda \in [3000, 5000]$.

### Prior-Informed RAPM
When stint sample size is limited, incorporate informative box-score or tracking priors ($\mu_0$):
$$\hat{\beta} = (X^T W X + \Lambda)^{-1} (X^T W Y + \Lambda \mu_0)$$
where $\Lambda$ is a diagonal regularization matrix reflecting uncertainty in prior estimates.

### Querying Stint & RAPM Tables
`silver_rapm` carries one row per player-season: `player_id`, `name`, `rapm`, `possessions`, `_season` — there are no `player_name`, `season`, `orapm`, `drapm` or `war` columns; total RAPM is the single `rapm` field.
```sql
SELECT player_id, name, rapm, possessions
FROM silver_rapm
WHERE _season = '2025-26' AND possessions >= 1000
ORDER BY rapm DESC;
```
Join to names/teams through `silver_player_season` (`player_id`) — not through `name`, whose spelling varies across feeds.

---

## 2. In-Game Win Probability & Leverage Index

### Win Probability Formulation
Win probability $P(\text{Win} \mid \text{state})$ is estimated as a function of point differential ($\Delta$), seconds remaining ($t$), possession state, and pre-game team strength differential ($\Delta\text{Elo}$):

$$P(\text{Win}) = \sigma\left( \beta_0 + \beta_1 \cdot \frac{\Delta}{\sqrt{t + 1}} + \beta_2 \cdot \Delta + \beta_3 \cdot \frac{\Delta\text{Elo}}{100} + \beta_4 \cdot I_{\text{possession}} \right)$$

where $\sigma(z) = \frac{1}{1 + e^{-z}}$.

### Leverage Index (LI)
Leverage measures how much the outcome of the current possession swings win probability relative to an average possession:

$$LI(t, \Delta) = \frac{|P(\text{Win} \mid \text{Score}) - P(\text{Win} \mid \text{Stop})|}{\overline{\Delta P_{\text{league}}}}$$

- $LI > 3.0$: High leverage (clutch situations, final 3 minutes within 5 points).
- $0.7 \le LI \le 1.5$: Medium leverage (competitive game flow).
- $LI < 0.5$: Low leverage (blowout territory).

---

## 3. Bayesian Shrinkage on Low-Sample Shooting

For players with low attempt volume (e.g. rookies or reserve players with fewer than 150 three-point attempts), raw percentages exhibit high variance. Apply Beta-Binomial conjugate shrinkage:

$$\theta \sim \text{Beta}(\alpha_0, \beta_0)$$
$$\hat{\theta}_{\text{shrunk}} = \frac{\text{FGM} + \alpha_0}{\text{FGA} + \alpha_0 + \beta_0}$$

- League average 3P% prior ($\mu = 0.360$, effective sample size $M = 300$):
  - $\alpha_0 = 0.360 \times 300 = 108$
  - $\beta_0 = (1 - 0.360) \times 300 = 192$
  - A player shooting 15-for-30 ($50.0\%$) shrinks to $\frac{15 + 108}{30 + 300} = \frac{123}{330} \approx 37.3\%$.

### Estimating the Prior From the Warehouse (Method of Moments)

When a question asks for an empirical-Bayes estimate rather than a hand-picked prior, fit $\mu$ and $M$ from the warehouse instead of assuming them. On `silver_hist_shots` (3PA per player from `shot_value = 3` rows, `game_id LIKE '002%'` for the regular season):

1. Restrict the reference pool to high-volume shooters (e.g. `FG3A >= 100`, optionally joined to `silver_player_season` with `GP >= 20`) so MLE noise doesn't dominate the variance estimate.
2. Pooled mean: $\mu = \frac{\sum \text{FG3M}}{\sum \text{FG3A}}$ over that pool.
3. Attempt-weighted sample variance $s^2 = \frac{\sum n_i (p_i - \mu)^2}{\sum n_i}$; subtract the binomial sampling noise $\frac{\mu(1-\mu)}{\bar n}$ (with $\bar n$ the mean attempts) to get the true between-player variance $\tau^2 = s^2 - \mu(1-\mu)/\bar n$; then
$$M = \frac{\mu(1-\mu)}{\tau^2} - 1$$
A negative `tau^2` means the pool has less spread than binomial noise — fall back to the fixed prior above.
4. Shrink each player on the full qualifying cohort ($\text{FG3A} \ge 40$): $\hat\theta = \frac{\text{FG3M} + M\mu}{\text{FG3A} + M}$. Report the shift, not just the shrunk value — the biggest movers are the low-volume players, and stating who moved most carries more meaning than a re-sorted leaderboard.

---

## 4. Visual Artifact Guidelines for Modeling

When presenting modeling results:
- **ORAPM vs DRAPM**: Use `scatter` with `xMid: 0`, `yMid: 0`, `xLabel: "Offensive RAPM"`, `yLabel: "Defensive RAPM"`. Points in the upper-right quadrant represent two-way positive impact.
- **Player Rankings**: Use `table` with numeric alignment, and use answer-block source anchors linking to the specific queried rows.
- **Trend Progression**: Use `chart` with `unit` (e.g. `"Net Rtg"`, `"PPG"`) and `xLabels` to plot rolling metrics or multi-season arcs.

---

## 5. Ad-Hoc Modeling Execution via `run_python`

The analyst agent has direct access to the `run_python` tool equipped with preloaded:
- `con`: Read-only DuckDB connection connected directly to the analytical warehouse.
- `pl`: Polars library for high-speed tabular manipulation and aggregation.
- `np`: NumPy for vectorized modeling and resampling.
- `math` and `statistics`: Standard library mathematical algorithms.

By default every `run_python` call runs in a fresh namespace — variables, frames, and fitted objects do not persist between calls unless the host enables `DIME_PY_PERSIST_NS`. Without persistence, a call that re-reads `silver_hist_possessions` or another large table repays that full scan each time, so splitting load → aggregate → fit across calls multiplies the I/O cost by the number of calls and can exhaust the run budget. Keep the whole pipeline inside one call: run a `con.execute` GROUP BY that reduces raw rows to the modeling grain (stints, player-games, team-splits), convert that small frame to polars/NumPy, then fit. For RAPM-style fits, aggregate possessions to stint rows (GROUP BY lineup/off-def player set) before building the sparse design — the solve is over ~thousands of stints, not millions of possessions.

### Warehouse Grain for Shot-Row Modeling

- `silver_hist_shots` carries `person_id` and a display `player_name` (full names like "Michael Porter Jr."). Group by `person_id`, never `player_name` — names are not stable keys across feeds — and when naming a player in the answer, use the exact `player_name` value the warehouse returns rather than a shortened surname form.
- `silver_player_season` covers current/recent seasons rather than full history, with team-stint rows possible in a season. For earlier seasons join `silver_hist_player_seasons` on `player_id`; its counting stats are per-game, so cohort thresholds like `FG3A >= 40` come from `COUNT(*)` over shot rows, not the season row.

### Example: Fitting Bayesian Shrinkage Over Warehouse Rows
```python
def fit_beta_prior(makes, attempts):
    k = np.asarray(makes, dtype=float)
    n = np.asarray(attempts, dtype=float)
    mu = k.sum() / n.sum()
    observed_var = np.average((k / n - mu) ** 2, weights=n)
    noise_var = np.average(mu * (1 - mu) / n, weights=n)
    latent_var = observed_var - noise_var
    strength = mu * (1 - mu) / latent_var - 1 if latent_var > 0 else None
    return {"mu": mu, "M": strength, "observed_var": observed_var, "noise_var": noise_var, "latent_var": latent_var, "players": len(n), "attempts": n.sum()}
```

- `mu*(1-mu)/observed_var` is not `M`: it treats binomial noise as skill spread and omits the `- 1`, so the prior is too weak. The Beta shape parameters are `M*mu` and `M*(1-mu)`. If `M` is `None`, report that these moments don't identify a finite strength; disclose any requested floor, cap, or fallback. A supplied fixed prior is not a fitted empirical prior.
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
The output can then be directly cited in `submit_answer` and visualized in a `table` or `scatter` artifact.

---

## 6. Cluster Bootstrap With Reproducible Seeds

Shots within a game are correlated, so resample the **game cluster**, not the shot row, when the statistic involves shot outcomes from `silver_hist_shots`.

1. Aggregate each cluster first (per `game_id`: corner-3 makes/attempts, arc-3 makes/attempts, or whatever the statistic needs — corner 3s are `shot_value = 3 AND ABS(x_legacy) >= 220 AND y_legacy <= 92.5`).
2. Pick a seed and a generator and say which you used: the legacy `np.random.seed(seed)` stream and `np.random.default_rng(seed)` produce different draws, so the two are not interchangeable when someone re-runs your numbers.
3. For each of `B` resamples (1000 is conventional), sum the resampled cluster aggregates and compute the statistic on the pooled totals (e.g. `1.5 * corner_3pm/corner_3pa - 1.5 * arc_3pm/arc_3pa`).
4. Report `std(ddof=1)` as the standard error and `np.percentile(stats, [2.5, 97.5])` as the 95% CI.

State the cluster unit, the seed, the generator, and `B` alongside the estimate so the number is reproducible.

---

## 7. Correlation, Simple Regression, and Honest Null Results

For "does X relate to Y" and "how tightly does X explain Y" asks:

1. Compute the coefficient in SQL with `CORR(x, y)` over a qualified cohort — apply minute/game/possession floors in the WHERE clause, never after. Report the coefficient to three decimals with the pool size.
2. A near-zero coefficient is a valid answer, not a failed analysis. When the data contradicts the classic claim (e.g. high-usage scorers are not less efficient — the usage/efficiency correlation across qualified player-seasons is near zero), report the measured coefficient and interpret the null. Never force the expected sign.
3. Distinguish correlation from the causal claim explicitly: a null correlation does not prove volume is free, and a strong one does not prove direction.

For simple linear fits (`y ~ x` over a small cohort such as 30 team-seasons):

```python
import statistics
xs = [float(r[0]) for r in rows]
ys = [float(r[1]) for r in rows]
mx, my = statistics.mean(xs), statistics.mean(ys)
slope = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)
intercept = my - slope*mx
residuals = sorted(((name, y - (slope*x + intercept)) for name, x, y in rows), key=lambda t: t[1])
out = {"slope": slope, "intercept": intercept, "largest_positive": residuals[-1], "largest_negative": residuals[0]}
```

Interpret residuals as outperformance/underperformance relative to the fitted line — they reflect luck, clutch performance, noise, and roster context, not proof of coaching or chemistry. Say what would change the interpretation.

## 8. Aging Curves and Cohort Profiles

For "how does production change with age / experience" asks, `silver_hist_player_seasons` is per-player-season rate stats (`pts`, `min`, `usg_pct`, `ts_pct`) keyed by integer end-year `season`:

```sql
SELECT CAST(age AS INT) AS a, COUNT(*) AS n, ROUND(AVG(pts), 2) AS avg_pts
FROM silver_hist_player_seasons
WHERE season >= 2015 AND min >= 20 AND gp >= 41
GROUP BY a HAVING COUNT(*) >= 30
ORDER BY a
```

1. Use rate-stat floors (`min >= 20` per game, `gp >= 41`) so the curve is not distorted by injury fill-ins, and require a minimum pool size per age bucket (`HAVING COUNT(*) >= 30`) so thin ages at the tails don't dominate.
2. Pool several seasons (10 is standard) — a single season's curve is noise plus roster churn.
3. `usg_pct` is a fraction (0.25 means 25%) in the sportsdataverse-backed rows used by this `season >= 2015` recipe.
4. Report the peak age, the level at the peak, and the slope on both sides — then connect the shape to the decision (contract length, development timeline). Do not read individual player trajectories off a league-average curve.
