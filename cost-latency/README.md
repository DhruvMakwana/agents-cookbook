# Cost and Latency

Two real repros of documented agent cost mechanics: quadratic transcript growth in naive tool loops, and confidence-based model routing. Concept write-up: [Cost and Latency](https://dhruvmakwana.github.io/agents-deep-dive/cost-latency/).

No framework — the raw Anthropic client throughout. Needs an Anthropic key. Demo 1 uses Haiku 4.5 (cheap, mechanical task). Demo 2 compares Haiku 4.5 against Sonnet 5 directly.

## The two demos

- **Quadratic transcript growth** (`quadratic_growth_demo`): a real 6-file sequential tool-reading task, run two ways — `naive` (the full accumulating transcript is resent every turn) and `windowed_last_2` (only the 2 most recent tool results are sent in full; older ones are replaced with a placeholder). Real cumulative `input_tokens` measured turn by turn from the API's own `usage` field.
- **Confidence-based routing** (`routing_demo`): 10 real questions — some trivial, some genuinely tricky (a classic bat-and-ball problem, a box-relabeling logic puzzle, a compound-discount trap, a "strawberry" spelling trap) — answered two ways: `always_sonnet` (every question goes straight to Sonnet 5) and `routed` (Haiku 4.5 answers first with a self-reported, explicitly-calibrated confidence field; a `low` reading escalates to Sonnet 5). Real token counts, real dollar cost (current published per-model pricing), and real correctness measured for both.

## What actually happened, run against Claude Haiku 4.5 / Sonnet 5

**Quadratic growth reproduced cleanly, and windowing measurably flattened it.** `naive`'s per-turn input tokens: `665, 1290, 1921, 2552, 3183, 3814, 4445` — each turn costs about 631 tokens more than the last, a constant per-turn *increase*, which is exactly what makes the cumulative total grow quadratically rather than linearly. Real cumulative total: **17,870 input tokens** across 7 turns. `windowed_last_2`'s per-turn tokens: `665, 1300, 1934, 2051, 2168, 2285, 2406` — nearly identical for the first 3 turns (the window hasn't started dropping anything yet), then flattening sharply once older tool results start getting replaced with a placeholder — by the last turn the per-turn *increase* is only ~121 tokens, not ~631. Real cumulative total: **12,809 input tokens** — a real **28.3% reduction**, and the gap widens every additional turn, exactly matching the shape of the real, documented `N(N+1)/2` triangular-number cost trap in naive agent loops.

**Confidence-based routing: a real, honest, two-sided result.** On real cost: `always_sonnet` spent **$0.026866** for **9/10** correct; `routed` (which, on this run, never actually escalated — see below) spent **$0.011843** for the identical **9/10** correct — Haiku 4.5 alone matched Sonnet 5's accuracy on this batch at **~44% of the real dollar cost**. That's a genuine, positive routing-adjacent finding: the cheap model was fully adequate here, not a downgrade.

But the escalation *mechanism* itself didn't do its job. `escalated_count: 0` — Haiku reported `confidence: "high"` on all 10 questions, including the one it got wrong (the "strawberry" spelling trap — Haiku confidently answered "Yes" both times it was asked, real and unforced, matching Sonnet's own real miss on the identical question). This held even after one deliberate, well-motivated adjustment to make the test fairer: two additional genuinely hard multi-step questions were added, and the tool's own description was rewritten to explicitly instruct calibrated self-assessment ("mark confidence as low whenever the question involves multi-step arithmetic... not just when you're unsure of a fact"). Confidence stayed `"high"` across the board regardless.

The real, sharper finding is in that null result, not despite it: self-reported natural-language confidence is not a reliable routing signal for catching a model's own mistakes, because a model that's about to be wrong isn't reliably aware that it's about to be wrong. That's a real, concrete reason production routing methods (e.g. STEER's confidence-guided routing, arXiv 2511.06190) use a different signal — model-internal confidence derived from the smaller model's own output-token probabilities — rather than asking the model to describe its own confidence in words. This recipe's self-report mechanism is the practical fallback available through a hosted chat-completions-style API that doesn't expose token-level logprobs the way some routing methods assume access to; the real result here is exactly why that gap matters.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** — this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python cost_latency.py
```

Runs both demos in sequence and prints each as JSON, including real per-turn token counts and real dollar costs.

## Files

| File | Role |
|---|---|
| `cost_latency.py` | Both demos and the CLI entry point — the file you actually run |
| `cost_latency_docs.py` | **Documentation only** — self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
