---
name: tracking-and-synergy
description: Analyze Second Spectrum optical tracking metrics, Synergy play types, contest quality, and spatial player movement.
---

# Optical Tracking & Synergy Analytics Playbook

This playbook establishes methodology for analyzing camera-based optical tracking data (Second Spectrum), play type taxonomies (Synergy Sports), and defensive contest dynamics.

## 1. Synergy Play Type Classifications

Basketball possessions are classified into standard play types:

- **Pick-and-Roll Ball Handler (PnR BH)**: Primary ball handler initiating out of an on-ball screen. Benchmark elite efficiency: $> 0.95 \text{ PPP}$.
- **Pick-and-Roll Roll Man (PnR RM)**: Screen setter rolling, popping, or slipping. Benchmark elite efficiency: $> 1.25 \text{ PPP}$.
- **Isolation (ISO)**: 1-on-1 offensive creation with minimal off-ball motion. Benchmark elite efficiency: $> 1.05 \text{ PPP}$.
- **Post-Up**: Traditional interior back-to-the-basket or mid-post creation. Benchmark elite efficiency: $> 1.00 \text{ PPP}$.
- **Spot-Up**: Stationary catch-and-shoot or catch-and-drive against a rotated defense. Benchmark elite efficiency: $> 1.10 \text{ PPP}$.
- **Hand-off (DHO)**: Dribble hand-off exchange, common in modern motion offenses. Benchmark elite efficiency: $> 1.00 \text{ PPP}$.
- **Cut**: Off-ball baseline or 45-degree flash toward the basket. Highest raw efficiency play type: $> 1.30 \text{ PPP}$.
- **Off-Screen**: Off-ball shooter curling, flaring, or fading around pindown screens. Benchmark elite efficiency: $> 1.05 \text{ PPP}$.
- **Transition**: Fast break offense starting before defense sets. Benchmark elite efficiency: $> 1.15 \text{ PPP}$.

---

## 2. Optical Tracking Dimensions

Optical tracking captures fine-grained physical movement:

### Speed & Distance
- **Average Speed**: Miles per hour on offense vs defense.
- **Distance Traveled**: Total miles run per 48 minutes of game time.

### Touch Profile
- **Touch Time**: Average seconds of possession per touch.
  - Quick-decision connector: $< 2.0\text{s}$ per touch.
  - Primary initiator: $> 5.5\text{s}$ per touch.
- **Dribbles per Touch**: Distribution of 0-dribble, 1-dribble, and 2+ dribble scoring attempts.

### Defensive Contest Tracking
- **Closest Defender Distance**:
  - Very Tight: $0 - 2\text{ ft}$.
  - Tight: $2 - 4\text{ ft}$.
  - Open: $4 - 6\text{ ft}$.
  - Wide Open: $> 6\text{ ft}$.
- **Defensive Field Goal % (DFG%) Differential**: Delta between shooter's expected FG% and actual FG% when guarded by the focal defender.
