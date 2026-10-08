---
name: visual-choice
description: Choose whether an answer earns a visual, and which one, from the shape of the evidence rather than from habit.
---

# Visual choice

## When to use

Any answer whose evidence holds a shape a person can see: a series over games or seasons, a
comparison between two or three named subjects, a ranked list, a split. Also use it to decide
that a single number needs no visual at all.

## The decision

| The evidence is | Declare |
| --- | --- |
| One number answering one question | nothing |
| The same output measured repeatedly over time, per game, or over an ordered set | chart |
| Two or three named subjects measured on the same outputs | chart, one series per subject |
| A ranked list of ten or more | nothing; the prose already ranks |
| A ranked list the reader will want to scan rather than read | table |
| Numbers that only matter as a set, with no axis | nothing |

## Key insights

- A visual earns its place by making a relationship visible that prose states badly. If the
  answer is one number, a chart is decoration and the reader has to skip past it.
- Never chart a single point. One point is a table row and reads as a broken chart.
- Series only join one chart when they share an x axis and an output. Two subjects on the same
  scale read together; a subject measured in points next to one measured in minutes does not,
  even if both have ten games.
- Prefer the fewest series that show the point. Three lines already cross; eight is a smear.
- Every point must name an output_id a claim in the same answer publishes. That is what makes
  the number citable, and a point you cannot bind is a point that silently disappears.
- Name the series exactly as the evidence names the subject. A display name that does not
  match the published subject resolves to nothing.
- Order the x axis the way the question reads: oldest to newest, or narrowest to broadest.
  A chart whose axis is alphabetical is a table wearing a costume.

## Failure modes

- Declaring a chart for a question the evidence answers with one number, which is the most
  common way this goes wrong.
- Declaring points for outputs no claim publishes, which renders an empty chart and reads as a
  broken product rather than as a missing binding.
- Stating a trend the series does not support, for example calling a flat line a steady climb.

## Stop condition

Declare at most one artifact per claim. If you are about to declare a second visual for the
same answer, the answer is carrying more than one idea and should be split or trimmed.