# Storyboard-First Method — Cross-Channel Test

Status: **test in progress**. Next episode on each channel is produced this way.

Channels in the test: **Dex**, **Turnstile**, **Time Travel**, **RI**.

---

## The method

Instead of going script → shot list → generate 40 individual images, we generate
**storyboard sheets**: one image containing 8 numbered panels in a 2×4 grid, each
panel captioned. Then each panel is used as the visual reference for the shot that
gets animated.

Why this is worth testing:

1. **Style locks across panels.** All 8 panels are rendered in one pass, so
   lighting, palette, character design and line weight are consistent by
   construction rather than by prompt-wrangling. This is the main hypothesis.
2. **Continuity is visible.** You can see the whole sequence read left-to-right
   before committing to animation, so pacing and repetition problems surface
   early and cheap.
3. **The caption is the script.** The panel caption and the VO line are written
   together, so the picture and the words can't drift apart.
4. **One artifact to review.** A sequence is approved or rejected as a sheet, not
   as 8 separate files.

The risk being tested against: panels come out small, so per-panel detail is lower
than a dedicated full-frame generation, and a single bad panel means re-rolling the
whole sheet.

## Sheet format (locked — do not vary between channels)

Deviating on format would confound the test. Every channel uses:

- **2 rows × 4 columns = 8 panels**, ~1536×1024 sheet.
- **Numbered badge** top-left of each panel: circled/boxed numeral, 1–8.
- **Caption bar** under each panel: `TITLE` in caps, then 2–3 lines of sentence
  case body copy, centred.
- **Timecode chip** top-left beside the number (`0:00-0:08`). The Vox reference
  sheet does this; adopt it everywhere — it makes the sheet double as a timing doc.
- **ACTION line** as the last line of the caption, in the accent colour:
  what moves, so the animation pass has a written instruction per panel.
- **One art style declared once** at the top of the prompt and never restated per
  panel.

## Episode maths

5:00 runtime = 300s = **5 sheets × 8 panels = 40 beats @ ~7.5s each**.

One sheet = one sequence = ~60s. Sheets are approved sequence by sequence, so a
rejected sheet costs 60s of work, not the episode.

## Production order

1. Write VO to 40 beats, ~17 words per beat (≈700 words @ 140wpm).
2. Write the 5 sheet prompts, each carrying the same style block verbatim.
3. Generate sheet, review as a whole, re-roll the sheet if any panel fails.
4. Slice panels to `NN.png`, upscale each to full frame.
5. Animate per the ACTION line.
6. VO + mix.

## What to measure (fill in per channel after publish)

Record these so the four channels are comparable. Baseline = that channel's
previous episode, produced the old way.

| Metric | How to capture |
| --- | --- |
| Time to locked visuals | Hours from script-final to all frames approved |
| Re-roll count | Total generations / 40 |
| Style drift | Subjective 1–5, judged across the full episode |
| Continuity errors | Count caught in edit |
| Retention @ 30s / @ 50% | Channel analytics, vs. previous 3 episodes |
| AVD | Channel analytics, vs. previous 3 episodes |

Confounder to watch: don't also change topic format, thumbnail style, or upload
time on the test episode. Storyboard method is the only variable.

| Channel | Episode | Sheets | Status |
| --- | --- | --- | --- |
| Dex | "Where Does the Internet Actually Live?" | 5 | script + prompts ready |
| Turnstile | TBC | 5 | not started |
| Time Travel | TBC | 5 | not started |
| RI | EP02 | 5 | assets in progress (`RI_EP02_row02_v6.png`) |
