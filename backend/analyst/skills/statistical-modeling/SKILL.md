---
name: statistical-modeling
description: Formulate and fit custom NBA analytical models including Regularized Adjusted Plus-Minus (RAPM), ridge regression shrinkage, win probability, in-game leverage, and Bayesian priors.
---

# Statistical Modeling & Quantitative Analytics Playbook

This playbook provides foundational mathematics, algorithms, and implementation procedures for executing advanced quantitative basketball models in Dime's analytical workspace.

## 1. Regularized Adjusted Plus-Minus (RAPM)

### Mathematical Formulation
RAPM isolates individual player contributions per 100 possessions by controlling for all 9 other players on the court, home court advantage, and stint duration.

$$\hat{\beta} = \arg\min_{\beta} \sum_{i=1}^{N} w_i \left( y_i - X_i \beta \right)^2 + \lambda \|\beta\|_2^2$$

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
```sql
SELECT player_id, player_name, season, orapm, drapm, rapm, possessions
FROM silver_rapm
WHERE season = '2025-26' AND possessions >= 1000
ORDER BY rapm DESC;
```

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
3. Attempt-weighted sample variance $s^2 = \frac{\sum n_i (p_i - \mu)^2}{\sum n_i}$ with $\bar n$ the mean attempts; then
$$M = \frac{\mu(1-\mu) - s^2}{s^2 - \mu(1-\mu)/\bar n}$$
A negative numerator means the pool has less spread than binomial noise — fall back to the fixed prior above.
4. Shrink each player on the full qualifying cohort ($\text{FG3A} \ge 40$): $\hat\theta = \frac{\text{FG3M} + M\mu}{\text{FG3A} + M}$. Report the shift, not just the shrunk value — the biggest movers are the low-volume players, and stating who moved most carries more meaning than a re-sorted leaderboard.

---

## 4. Visual Artifact Guidelines for Modeling

When presenting modeling results:
- **ORAPM vs DRAPM**: Use `scatter` with `xMid: 0`, `yMid: 0`, `xLabel: "Offensive RAPM"`, `yLabel: "Defensive RAPM"`. Points in the upper-right quadrant represent two-way positive impact.
- **Player Rankings**: Use `table` with numeric alignment and source anchors linking to the specific queried rows.
- **Trend Progression**: Use `chart` with `unit` (e.g. `"Net Rtg"`, `"PPG"`) and `xLabels` to plot rolling metrics or multi-season arcs.

---

## 5. Ad-Hoc Modeling Execution via `run_python`

The analyst agent has direct access to the `run_python` tool equipped with preloaded:
- `con`: Read-only DuckDB connection connected directly to the analytical warehouse.
- `pl`: Polars library for high-speed tabular manipulation and aggregation.
- `math` and `statistics`: Standard library mathematical algorithms.

### Example: Fitting Bayesian Shrinkage Over Warehouse Rows
```python
# Query players with low attempt counts
rows = con.execute("""
    SELECT player, fg3m, fg3a 
    FROM silver_leaders_pts 
    WHERE fg3a BETWEEN 10 AND 50
""").fetchall()

alpha_0 = 108.0
beta_0 = 192.0

shrunk = []
for p, fg3m, fg3a in rows:
    raw_pct = (fg3m / fg3a) * 100.0 if fg3a > 0 else 0.0
    shrunk_pct = ((fg3m + alpha_0) / (fg3a + alpha_0 + beta_0)) * 100.0
    shrunk.append({
        "player": p,
        "fg3m": fg3m,
        "fg3a": fg3a,
        "raw_pct": round(raw_pct, 1),
        "shrunk_pct": round(shrunk_pct, 1)
    })

# Assigning to out converts directly into structured rows with columns
out = pl.DataFrame(shrunk)
```
The output can then be directly cited in `submit_answer` and visualized in a `table` or `scatter` artifact.

---

## 6. Cluster Bootstrap With Reproducible Seeds

Shots within a game are correlated, so resample the **game cluster**, not the shot row, when the statistic involves shot outcomes from `silver_hist_shots`.

1. Aggregate each cluster first (per `game_id`: corner-3 makes/attempts, arc-3 makes/attempts, or whatever the statistic needs — corner 3s are `ABS(x_legacy) >= 220 AND y_legacy <= 92.5`).
2. Pick a seed and a generator and say which you used: the legacy `np.random.seed(seed)` stream and `np.random.default_rng(seed)` produce different draws, so the two are not interchangeable when someone re-runs your numbers.
3. For each of `B` resamples (1000 is conventional), sum the resampled cluster aggregates and compute the statistic on the pooled totals (e.g. `1.5 * corner_3pm/corner_3pa - 1.5 * arc_3pm/arc_3pa`).
4. Report `std(ddof=1)` as the standard error and `np.percentile(stats, [2.5, 97.5])` as the 95% CI.

State the cluster unit, the seed, the generator, and `B` alongside the estimate so the number is reproducible.
