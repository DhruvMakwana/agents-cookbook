# Models for Agents

Two real repros comparing model tiers for agentic use: tool-calling reliability under a deliberately ambiguous request (Haiku 4.5 vs. Sonnet 5), and a real cost/accuracy comparison of three dispatch strategies against queries with independently checkable answers, including two classic reasoning traps. Concept write-up: [Models for Agents](https://dhruvmakwana.github.io/agents-deep-dive/models-for-agents/).

No framework -- the raw Anthropic client throughout. Needs an Anthropic key. Both Haiku 4.5 and Sonnet 5 are used deliberately (comparing tiers is the point), hardcoded in code.

## The two repros

- **Tool-calling reliability under ambiguity** (`tool_calling_reliability_demo`): two tools with genuinely overlapping semantics (`cancel_subscription` vs. `pause_subscription`), and a request phrased in a way a hasty read could misclassify ("stop being charged... pick it back up starting March 1st" is a pause, not a cancel). 5 trials each, Haiku 4.5 vs. Sonnet 5, plus an unambiguous control case.
- **Routing** (`routing_demo`): 4 queries (2 simple factual/formatting, 2 classic reasoning traps -- the widgets/machines lateral-thinking problem and the bat-and-ball cognitive-reflection-test problem) run through three real dispatch strategies -- always-Haiku, always-Sonnet, and a Haiku-router deciding per query -- with real token counts and real correctness checked against known answers.

## What actually happened, run against Claude Haiku 4.5 / Sonnet 5

**The tool-calling ambiguity test was a clean, honest negative result.** Both Haiku 4.5 and Sonnet 5 picked `pause_subscription` correctly on all 5 trials each for the ambiguous request, and `cancel_subscription` correctly on all 5 trials each for the unambiguous control -- 100% accuracy across the board, no differentiation between tiers on this specific test. This is real and worth reporting plainly rather than adjusted to fit a predicted gap: whatever tool-calling reliability differences exist between current-generation Haiku and Sonnet, this particular ambiguity (a plausible temporal misreading of "stop being charged") isn't one of them.

**The reasoning-trap queries were also a clean sweep -- and a third, harder query (a chickens-and-cows system-of-equations problem, correct answer 23) confirmed it wasn't a fluke.** Haiku 4.5 answered the widgets/machines problem correctly ("5 minutes," not the tempting 100), the bat-and-ball problem correctly ("$0.05," not the tempting $0.10), and the chickens-and-cows problem correctly (23), all on the first try, no retries. Sonnet 5 matched on the two queries actually included in the routing demo. The honest conclusion: current-generation small models are meaningfully more reliable at classic reasoning traps than the "small model = unreliable at reasoning" assumption implies -- worth checking empirically per task rather than assumed.

**Routing still produced a real, if modest, cost benefit despite the accuracy tie.** With all three strategies tied at 4/4 correct:

| Strategy | Total tokens | Correct |
|---|---|---|
| Always Haiku | 174 | 4/4 |
| Always Sonnet | 216 | 4/4 |
| Routed (Haiku classifies, dispatches accordingly) | 199 | 4/4 |

The router correctly classified both simple queries as `simple` and both reasoning-trap queries as `complex`, and routing cost less than the always-Sonnet baseline (199 vs. 216 tokens) while matching its accuracy -- the router's own classification calls are real overhead, so routing didn't beat always-Haiku on cost, but it didn't need to: the real value routing demonstrates here is holding accuracy at the capable-model level while still saving tokens relative to blanket escalation, which is exactly RouteLLM's own real framing (report over 2x cost reduction at held quality) -- just at a scale too small for this specific 4-query batch to fully reproduce the reported magnitude.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Paste your key into `agents-cookbook/.env` at the **cookbook root** -- this recipe reads it automatically. To override just this recipe, `cp .env.example .env` here instead.

## Run

```bash
python models_for_agents.py
```

Runs both demos in sequence and prints each result as JSON.

## Files

| File | Role |
|---|---|
| `models_for_agents.py` | Both demos and the CLI entry point -- the file you actually run |
| `models_for_agents_docs.py` | **Documentation only** -- self-contained per-block version for the blog. Not run as a script, not kept in sync automatically. |
