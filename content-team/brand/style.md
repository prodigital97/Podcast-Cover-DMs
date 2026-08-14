# Locked brand style

The Designer reads this before any layout work and rejects briefs that would
break it. Locked means locked: changing a token here is a deliberate rebrand,
not a per-post decision.

Fill every `TODO` before the first carousel. An unfilled token is why AI design
looks like AI design — the model picks something reasonable and different every
time, and nothing accumulates into a brand.

## Palette

| token | hex | used for |
| --- | --- | --- |
| ink | TODO | body text |
| paper | TODO | slide background |
| accent | TODO | one highlight per slide, never two |
| muted | TODO | captions, footers, slide numbers |

## Type stack

| token | family | weight | size | tracking |
| --- | --- | --- | --- | --- |
| display | TODO | TODO | TODO | TODO |
| body | TODO | TODO | TODO | TODO |
| caption | TODO | TODO | TODO | TODO |

Two families maximum. If display and body are the same family, say so — that is
a valid choice, not an omission.

## Grid

- Canvas: 1080 x 1350 (carousel), 1080 x 1920 (story / reel cover)
- Margin: TODO px on all sides — text never crosses it
- Columns: TODO
- Baseline: TODO px

## Rules that survive every brief

- One accent element per slide.
- Footer (handle plus slide number) on every slide except the cover.
- Never centre body text that runs longer than two lines.
- No drop shadows, no gradients on type, no stroke on text.
- Cover text must be legible at 140 px wide — that is the feed thumbnail size.

## Layout audit

Run on the exported image, not the markup:

- [ ] Nothing overlaps
- [ ] All text inside the margin
- [ ] Footer present and unclipped
- [ ] Accent appears exactly once
- [ ] Cover readable at 140 px wide
