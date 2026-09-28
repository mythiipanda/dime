---
name: odds-lines
description: Read NBA spreads and totals as market prices, explain what line movement does and does not imply, and compare market prices against modeled estimates.
---
# Odds lines

## Frame the question

A spread or total is a market price, not a bookmaker's prediction. It reflects model output, reported news, and the need to balance action on both sides. Most user questions are really one of three: what does this line imply about the teams, why did the line move, or does the market agree with my read. Answer the actual one.

Never give betting advice. Never say "take" a side. Explaining what a price implies is analysis; telling someone to bet it is not this skill's job.

## Gather the market evidence

Get the opener and the current number, the direction and size of the move, and the timing of the move. A line that moves 3 points minutes after injury news has a different meaning than one that drifts half a point over two days.

Pull the implied read from the numbers: the spread implies a central margin, the total implies a pace and efficiency expectation. Compare the current line to the opener to name what changed, not just that something did.

Use `game_prediction` for the independent modeled estimate, `team_ratings` and `competitive_ratings` for each team's baseline quality, and `injuries` plus `roster` for the concrete news that usually drives moves. For availability, trade, or rotation claims behind a move, run a `web_search` -> `web_fetch` evidence branch. Search snippets are discovery only.

## Read movement honestly

Line movement usually means one of three things: new information reached the market (injury, rest decision, lineup change), books are balancing one-sided action, or the opening number was soft and got corrected by early respected money. Name which one the evidence supports. A move without a news trigger is a guess about the trigger, label it that way.

Movement does not mean the market "knows" the outcome. It means opinions or money shifted the price. A spread moving toward a team is evidence about pricing, not about the final score. Do not report steam or line moves as if they were inside information on the game itself.

When the modeled `game_prediction` disagrees with the market, investigate the gap: is the model missing an injury, or is the market overreacting to narrative? A disagreement is a question to answer, not a pick to make.

## Pitfalls

Public-money narratives are fiction without handle data. Nobody watching one book move can see where the money is; treat "the public is on X" claims as stories.

Against-the-spread streaks under roughly 30 games are noise. A 4-0 ATS run changes nothing about the price's meaning.

The spread is not the predicted margin. It is the number that balanced the market. Confusing the two turns a pricing fact into a forecast fact.

Do not launder gambling content into analysis. "Sharp money is coming in" without a source is content, not evidence.

## Complete the answer

A complete answer has:

- opener, current line, move direction and size;
- the likely trigger, or an honest statement that the trigger is unknown;
- what the current price implies about margin and about pace;
- the independent modeled estimate and baseline ratings for both teams;
- where model and market disagree and the best explanation for the gap;
- a statement of uncertainty and what news would change the read.

Keep every claim tied to admitted evidence. Label projections as projections. Never close with a pick.
