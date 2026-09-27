# Dime Design — Typography

Source of truth for type across the site. When in doubt, follow this file.

## Font

Inter (variable), loaded once via `next/font` in `app/layout.tsx` and applied
through `--font-body` / `--font-display`. Every surface uses the theme font —
no hardcoded font stacks anywhere.

## Weights

Three only: **400** (regular), **500** (medium), **600** (semibold).
No 700. No intermediate variable weights (520/550/570/650).

## Scale

| Size | Use |
| ---- | --- |
| 9px  | Micro labels: kbd hints, table units, command footer |
| 10px | Kickers, eyebrows |
| 11px | Captions, secondary labels |
| 12px | Small UI: buttons, chips, starters |
| 13px | UI body: fields, table cells, chat bubbles |
| 14px | Body base |
| 16px | Section titles |
| 18px | Large numbers (mobile stat size) |
| 20px | Panel titles (`.display`) |
| 22px | Stat numbers |
| 24px | Page titles (h1) |
| 32px+ | Hero only (chat welcome heading) |

Nothing outside this scale. If a size isn't here, pick the nearest one.

## Rules

- **Kickers** (uppercase labels): 600 weight, 10–12px, `.08em` tracking.
- **Headings**: 500 weight, tight tracking (`-.03em`; hero `-.04em`).
- **Numbers in tables/stats**: `font-variant-numeric: tabular-nums`.
- **Body**: 400 weight, `-.01em` tracking, 1.5 line-height.
- No ALL-CAPS outside kickers. No decorative letter-spacing elsewhere.
