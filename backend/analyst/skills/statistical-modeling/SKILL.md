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

---

## 4. Visual Artifact Guidelines for Modeling

When presenting modeling results:
- **ORAPM vs DRAPM**: Use `scatter` with `xMid: 0`, `yMid: 0`, `xLabel: "Offensive RAPM"`, `yLabel: "Defensive RAPM"`. Points in the upper-right quadrant represent two-way positive impact.
- **Player Rankings**: Use `table` with numeric alignment and source anchors linking to the specific queried rows.
